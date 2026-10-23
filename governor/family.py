import psutil
from governor import config as cfg, actuator

class Family:
    def __init__(self):
        self.streak, self.last = {}, {}

    def check(self, now, groups, det, ev, fg):
        if not cfg.FAMILY:
            return
        for key, mem in groups.items():
            if len(mem) < cfg.FAMILY_MIN_PROCS:
                continue
            total = sum(m[0] for m in mem)
            bad, z = det.evaluate('fam:' + key, 'cpu', total)
            bad = bad and total >= cfg.FAMILY_CPU_FLOOR
            self.streak[key] = self.streak.get(key, 0) + 1 if bad else 0
            if self.streak[key] < cfg.SUSTAIN_SAMPLES or now - self.last.get(key, 0) < cfg.COOLDOWN_SECONDS:
                continue
            moved = 0
            for cpu, _, p, st in sorted(mem, key=lambda m: -m[0])[:cfg.FAMILY_TOP_N]:
                if st.level >= 2 or p.pid in fg:
                    continue
                try:
                    old, new = actuator.move(p, st.level + 1)
                except (psutil.Error, PermissionError):
                    continue
                if st.orig is None:
                    st.orig = old
                st.level += 1
                st.level_since, st.calm, st.last_action = now, 0, now
                st.cpu_before, st.verify_at = cpu, now + cfg.VERIFY_AFTER
                moved += 1
                ev.append((now, p.pid, key, 'cpu', cpu, z, 'throttle_L%d' % st.level, old, new,
                           'family %.0f%% across %d processes: demote Q%d to Q%d'
                           % (total, len(mem), st.level - 1, st.level)))
            if moved:
                self.last[key] = now