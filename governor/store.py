import os, sqlite3
from governor import config as cfg

SCHEMA = '''
CREATE TABLE IF NOT EXISTS samples (ts REAL, pid INT, key TEXT, cpu REAL, mem_mb REAL, z_cpu REAL, z_mem REAL);
CREATE TABLE IF NOT EXISTS events (ts REAL, pid INT, key TEXT, metric TEXT, value REAL, z REAL,
                                   action TEXT, old_prio INT, new_prio INT, note TEXT);
CREATE TABLE IF NOT EXISTS meta (ts REAL, gov_cpu REAL, gov_rss_mb REAL, cycle_ms REAL, n_procs INT);
CREATE INDEX IF NOT EXISTS i_s ON samples(ts);
CREATE INDEX IF NOT EXISTS i_e ON events(ts);
CREATE INDEX IF NOT EXISTS i_m ON meta(ts);
'''

def connect():
    os.makedirs(os.path.dirname(cfg.DB_PATH), exist_ok=True)
    con = sqlite3.connect(cfg.DB_PATH, timeout=10)
    con.execute('PRAGMA journal_mode=WAL')
    return con

def init():
    con = connect()
    con.executescript(SCHEMA)
    con.close()

def write(con, samples, events, meta):
    con.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?,?)', samples)
    con.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)', events)
    con.execute('INSERT INTO meta VALUES (?,?,?,?,?)', meta)
    con.commit()
