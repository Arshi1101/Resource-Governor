import json, subprocess, sys, threading, urllib.request
from governor import config as cfg

def _send(title, text):
    if cfg.DESKTOP_NOTIFY and sys.platform == 'darwin':
        safe = text.replace('"', "'")
        script = 'display notification "%s" with title "%s"' % (safe, title)
        subprocess.run(['osascript', '-e', script], timeout=5)
    if cfg.WEBHOOK_URL:
        body = json.dumps({'text': title + ': ' + text, 'content': title + ': ' + text}).encode()
        req = urllib.request.Request(cfg.WEBHOOK_URL, data=body, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=5)

def send(title, text):
    def run():
        try:
            _send(title, text)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()