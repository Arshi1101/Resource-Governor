import time
import psutil

HINTS = ('/tmp/', '/temp/', '/downloads/', '/appdata/local/temp', '/var/folders/', '/library/caches/')

def _remote_ips(p):
    fn = getattr(p, 'net_connections', None) or p.connections
    return {c.raddr.ip for c in fn(kind='inet') if c.raddr and c.status == 'ESTABLISHED'}

def score(p, cpu, fg):
    pts, why = 0, []
    try:
        where = ((p.exe() or '') + ' ' + ' '.join(p.cmdline())).lower().replace(chr(92), '/')
        if any(h in where for h in HINTS):
            pts += 2
            why.append('runs from a temp or downloads folder')
    except psutil.AccessDenied:
        pass
    except psutil.Error:
        pts += 1
        why.append('executable path unreadable')
    try:
        if time.time() - p.create_time() < 600:
            pts += 1
            why.append('started in the last 10 minutes')
    except psutil.Error:
        pass
    if time.localtime().tm_hour < 6:
        pts += 1
        why.append('active between midnight and 6 am')
    if p.pid not in fg:
        pts += 1
        why.append('not the app in front of the user')
    if cpu >= 90:
        pts += 1
        why.append('pinning a core')
    try:
        if len(_remote_ips(p)) >= 3:
            pts += 2
            why.append('3 or more remote connections')
    except psutil.Error:
        pass                          
    return pts, why