import subprocess, sys
import psutil

FOREGROUND_CACHE_SECONDS = 3

def foreground_pid():
    try:
        if sys.platform.startswith('win'):
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(pid))
            return pid.value or None
        if sys.platform == 'darwin':
            script = 'tell application "System Events" to get unix id of first process whose frontmost is true'
            out = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=2)
            return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:
        return None
    return None

class Foreground:
    def __init__(self):
        self.t, self.cache = 0.0, set()

    def pids(self, now):
        if now - self.t >= FOREGROUND_CACHE_SECONDS:
            self.t, s, pid = now, set(), foreground_pid()
            if pid:
                s.add(pid)
                try:
                    s.update(c.pid for c in psutil.Process(pid).children(recursive=True))
                except psutil.Error:
                    pass
            self.cache = s
        return self.cache
