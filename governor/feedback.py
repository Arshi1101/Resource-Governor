import json, os, sqlite3, time
from governor import config as cfg

SQL = 'CREATE TABLE IF NOT EXISTS feedback (ts REAL, key TEXT, verdict TEXT)'
PATH = os.path.join(cfg.ROOT, 'data', 'learned.json')

def submit(key, verdict):                
    con = sqlite3.connect(cfg.DB_PATH, timeout=10)
    con.execute(SQL)
    con.execute('INSERT INTO feedback VALUES (?,?,?)', (time.time(), key, verdict))
    con.commit()
    con.close()

class Learner:
    def __init__(self):
        self.bonus, self.seen = {}, 0.0
        try:
            with open(PATH) as f:
                d = json.load(f)
            self.bonus, self.seen = d['bonus'], d['seen']
        except (OSError, ValueError, KeyError):
            pass

    def poll(self):
        con = sqlite3.connect(cfg.DB_PATH, timeout=10)
        try:
            con.execute(SQL)
            rows = con.execute('SELECT ts, key, verdict FROM feedback WHERE ts > ? ORDER BY ts',
                               (self.seen,)).fetchall()
        finally:
            con.close()
        for ts, key, verdict in rows:
            b = self.bonus.get(key, 0.0)
            self.bonus[key] = min(b + 1.0, 4.0) if verdict == 'false_alarm' else max(b - 0.5, -1.0)
            self.seen = ts
        if rows:
            with open(PATH, 'w') as f:
                json.dump({'bonus': self.bonus, 'seen': self.seen}, f)

    def bonus_for(self, key):
        return self.bonus.get(key, 0.0)