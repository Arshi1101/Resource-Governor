import os, sqlite3, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mins = float(sys.argv[1]) if len(sys.argv) > 1 else 60
since = time.time() - mins * 60
con = sqlite3.connect(os.path.join(ROOT, 'data', 'governor.db'))
rows = con.execute('SELECT ts, pid, key, metric, value, z, action, old_prio, new_prio, note '
                   'FROM events WHERE ts >= ? ORDER BY ts', (since,)).fetchall()
by = con.execute('SELECT key, COUNT(*) FROM events WHERE ts >= ? GROUP BY key ORDER BY 2 DESC', (since,)).fetchall()

lines = ['# Incident report (last %g minutes)' % mins, '', 'Total events: %d' % len(rows), '',
         '## By program', '']
lines += ['- %s: %d' % (k, n) for k, n in by]
lines += ['', '## Timeline', '']
for ts, pid, key, metric, val, z, action, old, new, note in rows:
    when = time.strftime('%H:%M:%S', time.localtime(ts))
    what = '%s (PID %d) reached %.0f%s' % (key, pid, val, '% CPU' if metric == 'cpu' else ' MB RAM')
    why = ', %.1f standard deviations above its learned baseline' % z if z > 0 else ''
    act = '; priority %s to %s' % (old, new) if old is not None else ''
    lines.append('- **%s** %s%s. Action: `%s`%s. %s' % (when, what, why, action, act, note or ''))

out = os.path.join(ROOT, 'data', 'incident_report.md')
with open(out, 'w') as f:
    f.write(chr(10).join(lines) + chr(10))
print('Wrote', out)