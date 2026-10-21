import csv, os, sqlite3, subprocess, sys, time
import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'data', 'governor.db')
MARK = os.path.join(ROOT, 'data', 'spike_marker.txt')
VLOG = os.path.join(ROOT, 'data', 'victim_log.csv')
CALM, SPIKE = 90, 90
tool = lambda name: os.path.join(ROOT, 'tools', name)

if os.path.exists(MARK):
    os.remove(MARK)
n = psutil.cpu_count(logical=True)
procs = [subprocess.Popen([sys.executable, tool('victim.py')])]
procs += [subprocess.Popen([sys.executable, tool('spike.py'), '--calm', str(CALM), '--spike', str(SPIKE)])
          for _ in range(n)]
print('Running %d spike processes for about %d s ...' % (n, CALM + SPIKE))
try:
    time.sleep(CALM + SPIKE + 5)
finally:
    for p in procs:
        p.terminate()

marker = float(open(MARK).read())
con = sqlite3.connect(DB)
first = con.execute('SELECT MIN(ts) FROM events WHERE ts >= ? AND action LIKE ?',
                    (marker, 'throttle_L%')).fetchone()[0]
if first is None:
    sys.exit('No throttle event found. Was the governor running in real (not dry-run) mode?')

def avg_cpu(a, b):
    r = con.execute('SELECT AVG(cpu) FROM samples WHERE key = ? AND ts BETWEEN ? AND ?',
                    ('python:spike.py', a, b)).fetchone()[0]
    return r or 0.0

rows = list(csv.DictReader(open(VLOG)))
def avg_ops(a, b):
    v = [float(r['ops']) for r in rows if a <= float(r['ts']) <= b]
    return sum(v) / len(v) if v else 0.0

before, after = avg_cpu(marker + 1, first), avg_cpu(first + 5, first + 25)
vb, va = avg_ops(marker + 1, first), avg_ops(first + 5, first + 25)
print('Detection time          : %.1f s' % (first - marker))
print('Hog CPU before / after  : %.0f%% / %.0f%%  (reduction %.0f%%)' % (before, after, 100 * (before - after) / max(before, 1)))
print('Victim ops/s before/after: %.0f / %.0f  (recovery x%.1f)' % (vb, va, va / max(vb, 1)))