import sys
import psutil
from governor import config as cfg

IS_WIN = sys.platform.startswith('win')

def ladder():
    if IS_WIN:
        return [psutil.NORMAL_PRIORITY_CLASS, psutil.BELOW_NORMAL_PRIORITY_CLASS,
                psutil.IDLE_PRIORITY_CLASS]
    return cfg.LADDER_MAC

def move(p, level):
    old = p.nice()
    new = ladder()[level]
    if not cfg.DRY_RUN:
        p.nice(new)
    return old, new
