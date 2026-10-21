import os, sqlite3, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
con = sqlite3.connect(os.path.join(ROOT, 'data', 'governor.db'))
rows = con.execute("SELECT ts, pid, key, action, note FROM events "
                   "WHERE action LIKE 'throttle_L%' OR action IN "
                   "('promote','boost','class_set','promote_failed','boost_failed') "
                   "ORDER BY pid, ts").fetchall()
cur = None
for ts, pid, key, action, note in rows:
    if pid != cur:
        cur = pid
        print('\n%s (PID %d)' % (key, pid))
    print('  %s  %-16s %s' % (time.strftime('%H:%M:%S', time.localtime(ts)), action, note))