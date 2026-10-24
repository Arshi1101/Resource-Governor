import sys
import psutil
from governor import config as cfg

IS_WIN = sys.platform.startswith('win')

def ladder():
    if IS_WIN:
        return [psutil.NORMAL_PRIORITY_CLASS, psutil.BELOW_NORMAL_PRIORITY_CLASS,
                psutil.IDLE_PRIORITY_CLASS]
    return cfg.LADDER_MAC

def level_for_priority(priority):
    levels = ladder()
    try:
        return levels.index(priority)
    except ValueError:
        if IS_WIN or not isinstance(priority, (int, float)):
            return 0
        if priority <= levels[0]:
            return 0
        if priority <= levels[1]:
            return 1
        return 2

def move(p, level):
    old = p.nice()
    new = ladder()[level]
    if not cfg.DRY_RUN:
        p.nice(new)
    return old, new
