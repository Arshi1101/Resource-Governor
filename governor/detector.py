import json, time
from collections import deque
from governor import config as cfg
from governor.baseline import Baseline

class ProcState:
    def __init__(self, key):
        self.key = key
        self.streak = {'cpu': 0, 'mem': 0}
        self.level = 0
        self.orig = None
        self.last_action = 0.0
        self.calm = 0
        self.hist = deque(maxlen=cfg.LEAK_WINDOW)
        self.tick = 0
        self.leak_flag = False
        self.deferred = False
        self.cpu_before = 0.0
        self.verify_at = 0.0
        self.suspect_checked = False
        self.base = 0
        self.classed = False
        self.level_since = 0.0

class Detector:
    def __init__(self):
        self.base = {}

    def _get(self, key, metric):
        block = time.localtime().tm_hour // cfg.SEASON_BLOCK_HOURS if cfg.SEASONAL else 0
        k = (key, metric, block)
        if k not in self.base:
            b = Baseline(cfg.EWMA_ALPHA, cfg.WARMUP_SAMPLES)
            prior = next((v for (kk, mm, _), v in self.base.items()
                          if kk == key and mm == metric and v.ready), None)
            if prior:
                b.n, b.mean, b.m2, b.var = cfg.WARMUP_SAMPLES + 1, prior.mean, prior.m2, prior.var
            self.base[k] = b
        return self.base[k]

    def evaluate(self, key, metric, x, z_thr=None):
        """Return the anomaly flag and its z-score."""
        zt = z_thr if z_thr is not None else cfg.Z_THRESHOLD
        if cfg.MODE == 'static':
            limit = cfg.STATIC_CPU if metric == 'cpu' else cfg.STATIC_MEM_MB
            return x >= limit, 0.0
        b = self._get(key, metric)
        if not b.ready:
            b.update(x)
            return False, 0.0
        if metric == 'cpu':
            floor, min_std = cfg.CPU_FLOOR, cfg.MIN_STD_CPU
        else:
            floor, min_std = cfg.MEM_FLOOR_MB, cfg.MIN_STD_MEM
        z = (x - b.mean) / max(b.std, min_std)
        bad = z >= zt and x >= floor
        if not bad:
            b.update(x)
        return bad, z

    def save(self, path):
        rec = [[k[0], k[1], k[2], b.n, b.mean, b.m2, b.var] for k, b in self.base.items()]
        with open(path, 'w') as f:
            json.dump(rec, f)

    def load(self, path):
        try:
            with open(path) as f:
                rec = json.load(f)
        except (OSError, ValueError):
            return
        for key, metric, block, n, mean, m2, var in rec:
            b = Baseline(cfg.EWMA_ALPHA, cfg.WARMUP_SAMPLES)
            b.n, b.mean, b.m2, b.var = n, mean, m2, var
            self.base[(key, metric, block)] = b
