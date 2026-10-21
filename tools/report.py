import os, sqlite3, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mins = float(sys.argv[1]) if len(sys.argv) > 1 else 60
since = time.time() - mins * 60
con = sqlite3.connect(os.path.join(ROOT, 'data', 'governor.db'))

print('--- Anomaly episodes in last %g min (one row per program/PID/metric) ---' % mins)
rows = con.execute('SELECT key, pid, metric, COUNT(*) FROM events WHERE ts >= ? GROUP BY key, pid, metric',
                   (since,)).fetchall()
for r in rows:
    print(r)
print('Total episodes (false alarms if no stress was injected):', len(rows))

cpu, ram, cyc, mx = con.execute('SELECT AVG(gov_cpu), AVG(gov_rss_mb), AVG(cycle_ms), MAX(cycle_ms) '
                                'FROM meta WHERE ts >= ?', (since,)).fetchone()
print('Governor overhead: CPU %.2f%%, RAM %.1f MB, cycle %.0f ms avg / %.0f ms max' % (cpu, ram, cyc, mx))