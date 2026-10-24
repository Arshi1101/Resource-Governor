import argparse, os, time
import psutil
from governor import config as cfg, store, actuator, notify, leak, suspect
from governor.context import Foreground
from governor.detector import Detector, ProcState
from governor.family import Family
from governor.feedback import Learner
from governor.policy import Policy

NOTIFY = {'throttle_L1', 'throttle_L2', 'leak_warning', 'verify_ineffective', 'suspicious'}

def proc_key(p):
    name = (p.name() or '?').lower()
    if name.startswith('python'):
        try:
            args = p.cmdline()
        except psutil.Error:
            return name
        for i, a in enumerate(args[1:], 1):
            if a == '-m' and i + 1 < len(args):
                return 'python:' + args[i + 1]
            if not a.startswith('-'):
                return 'python:' + os.path.basename(a)
    return name

def handle(p, st, cpu, mem, now, c):
    pid, key, ev, zs = p.pid, st.key, c['events'], {}
    pol = c['policy']
    if pol.get(key, 'never_touch', False):
        return
    zt = pol.get(key, 'z_threshold', cfg.Z_THRESHOLD) * (0.8 if c['battery'] else 1.0) + c['learn'].bonus_for(key)
    cls = cfg.CLASSES.get(pol.get(key, 'class', 'normal'), cfg.CLASSES['normal'])
    max_level = pol.get(key, 'max_level', cls['max'])
    if not st.classed:
        st.classed, st.level_since = True, now
        requested_base = cls['base']
        if st.level < requested_base:
            try:
                old, new = actuator.move(p, requested_base)
                st.orig, st.level, st.base = old, requested_base, requested_base
                ev.append((now, pid, key, 'cpu', cpu, 0.0, 'class_set', old, new,
                           'class %s, queue Q%d' % (pol.get(key, 'class', 'normal'), requested_base)))
            except (psutil.AccessDenied, PermissionError):
                st.base = st.level
        else:
            st.base = st.level
            ev.append((now, pid, key, 'cpu', cpu, 0.0, 'queue_state', st.orig, st.orig,
                       'current OS priority, queue Q%d' % st.level))

    for metric, x in (('cpu', cpu), ('mem', mem)):
        bad, z = c['det'].evaluate(key, metric, x, zt)
        zs[metric] = z
        if metric == 'cpu' and not bad:
            st.deferred = False
        st.streak[metric] = st.streak[metric] + 1 if bad else 0
        if st.streak[metric] < cfg.SUSTAIN_SAMPLES:
            continue
        if metric == 'mem':
            if st.streak['mem'] == cfg.SUSTAIN_SAMPLES:
                ev.append((now, pid, key, 'mem', x, z, 'flag', None, None,
                           'RAM anomaly - priority cannot reduce memory'))
        elif st.level < max_level and now - st.last_action >= cfg.COOLDOWN_SECONDS:
            if pid in c['fg']:
                if not st.deferred:
                    st.deferred = True
                    ev.append((now, pid, key, 'cpu', x, z, 'deferred_foreground', None, None,
                               'foreground app, left alone'))
                continue
            st.last_action = now
            try:
                old, new = actuator.move(p, st.level + 1)
                if st.orig is None:
                    st.orig = old
                st.level += 1
                st.level_since, st.calm = now, 0
                st.cpu_before, st.verify_at = x, now + cfg.VERIFY_AFTER
                ev.append((now, pid, key, 'cpu', x, z, 'throttle_L%d' % st.level, old, new,
                           'demote Q%d to Q%d%s' % (st.level - 1, st.level, ' (dry-run)' if cfg.DRY_RUN else '')))
            except (psutil.AccessDenied, PermissionError):
                ev.append((now, pid, key, 'cpu', x, z, 'throttle_failed', None, None, 'access denied'))

    if st.level and st.verify_at and now >= st.verify_at:
        st.verify_at = 0
        red = (st.cpu_before - cpu) / max(st.cpu_before, 1.0)
        if red >= 0.3:
            outcome = 'effective'
        elif c['sysload'] < 60:
            outcome = 'no_contention'
        else:
            outcome = 'ineffective'
            st.last_action = 0.0
        ev.append((now, pid, key, 'cpu', cpu, zs['cpu'], 'verify_' + outcome, None, None,
                   'cpu %.0f%% to %.0f%%, system load %.0f%%' % (st.cpu_before, cpu, c['sysload'])))

        if st.level and not st.suspect_checked:
         st.suspect_checked = True
         pts, why = suspect.score(p, cpu, c['fg'])
         if pts >= cfg.SUSPECT_SCORE:
            ev.append((now, pid, key, 'cpu', cpu, zs['cpu'], 'suspicious', None, None,
                       'score %d: %s' % (pts, '; '.join(why))))
    st.hist.append((now, mem))
    st.tick += 1
    if st.tick % 10 == 0 and len(st.hist) == st.hist.maxlen and not st.leak_flag:
        rate, r2, eta = leak.forecast(st.hist, c['avail'])
        if rate >= cfg.LEAK_MIN_MB_PER_MIN and r2 >= cfg.LEAK_MIN_R2:
            st.leak_flag = True
            when = '%.0f min' % eta if eta else 'n/a'
            ev.append((now, pid, key, 'mem', mem, 0.0, 'leak_warning', None, None,
                       '+%.0f MB/min, R2=%.2f, about %s until free RAM runs out' % (rate, r2, when)))

    if st.level > st.base:
        st.calm = st.calm + 1 if zs['cpu'] < cfg.RECOVER_Z else 0
        why = None
        if st.calm >= cfg.PROMOTE_AFTER_CALM:
            why = 'promote'
        elif now - st.level_since >= cfg.BOOST_SECONDS:
            why = 'boost'
        if why:
            try:
                old, new = actuator.move(p, st.level - 1)
                st.level -= 1
                st.level_since, st.calm = now, 0
                ev.append((now, pid, key, 'cpu', cpu, zs['cpu'], why, old, new,
                           'Q%d to Q%d' % (st.level + 1, st.level)))
            except (psutil.AccessDenied, PermissionError):
                st.base = st.level
                ev.append((now, pid, key, 'cpu', cpu, zs['cpu'], why + '_failed', None, None,
                           'needs sudo on macOS'))
    if cpu >= 1 or mem >= 200 or st.level:
        c['samples'].append((now, pid, key, cpu, mem, zs['cpu'], zs['mem']))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--mode', choices=['adaptive', 'static'])
    ap.add_argument('--interval', type=float)
    ap.add_argument('--no-foreground', action='store_true')
    a = ap.parse_args()
    if a.dry_run: cfg.DRY_RUN = True
    if a.mode: cfg.MODE = a.mode
    if a.interval: cfg.SAMPLE_INTERVAL = a.interval
    if a.no_foreground: cfg.PROTECT_FOREGROUND = False

    store.init()
    con = store.connect()
    det, states, fg, policy = Detector(), {}, Foreground(), Policy()
    fam, learn = Family(), Learner()
    det.load(cfg.BASELINE_PATH)
    me = psutil.Process(os.getpid())
    me.cpu_percent(None)
    psutil.cpu_percent(None)
    print('Governor v2 running: mode=%s dry_run=%s foreground_protection=%s. Ctrl+C to stop.'
          % (cfg.MODE, cfg.DRY_RUN, cfg.PROTECT_FOREGROUND))
    cycle = 0
    try:
        while True:
            t0 = time.time()
            cycle += 1
            if cycle % 10 == 0:
                policy.reload()
                learn.poll()
            if cycle % 300 == 0:
                det.save(cfg.BASELINE_PATH)
            samples, events, seen, groups = [], [], set(), {}
            batt = psutil.sensors_battery() if (cfg.BATTERY_AWARE and hasattr(psutil, 'sensors_battery')) else None
            c = {'learn': learn, 'det': det, 'policy': policy, 'events': events, 'samples': samples,
                 'fg': fg.pids(t0) if cfg.PROTECT_FOREGROUND else set(),
                 'battery': bool(batt and batt.power_plugged is False),
                 'sysload': psutil.cpu_percent(None),
                 'avail': psutil.virtual_memory().available / 1048576}
            for p in psutil.process_iter():
                try:
                    with p.oneshot():
                        pid = p.pid
                        seen.add(pid)
                        cpu = p.cpu_percent(None)
                        st = states.get(pid)
                        if st is None:
                            st = ProcState(proc_key(p))
                            try:
                                st.orig = p.nice()
                                st.level = actuator.level_for_priority(st.orig)
                                st.base = st.level
                            except (psutil.Error, PermissionError):
                                pass
                            states[pid] = st
                            continue
                        mem = p.memory_info().rss / 1048576
                    if pid == me.pid or st.key in cfg.PROTECTED:
                        continue
                    if not policy.get(st.key, 'never_touch', False):
                        groups.setdefault(st.key, []).append((cpu, mem, p, st))
                    handle(p, st, cpu, mem, t0, c)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            states = {k: v for k, v in states.items() if k in seen}
            fam.check(t0, groups, det, events, c['fg'])
            ts = time.time()
            meta = (ts, me.cpu_percent(None), me.memory_info().rss / 1048576, (ts - t0) * 1000, len(seen))
            store.write(con, samples, events, meta)
            for e in events:
                print(time.strftime('%H:%M:%S'), e[2], 'pid', e[1], e[6], '%.0f' % e[4], 'z=%.1f' % e[5])
                if e[6] in NOTIFY:
                    notify.send('Resource Governor', '%s %s (pid %d): %s' % (e[2], e[6], e[1], e[9] or 'cpu %.0f%%' % e[4]))
            time.sleep(max(0, cfg.SAMPLE_INTERVAL - (time.time() - t0)))
    except KeyboardInterrupt:
        print('Stopped.')
    finally:
        det.save(cfg.BASELINE_PATH)

if __name__ == '__main__':
    main()
