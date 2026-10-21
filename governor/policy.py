import json, os
from governor import config as cfg

class Policy:
    def __init__(self):
        self.data, self.mtime = {'default': {}, 'programs': {}}, 0
        self.reload()

    def reload(self):
        try:
            m = os.path.getmtime(cfg.POLICY_PATH)
            if m == self.mtime:
                return
            with open(cfg.POLICY_PATH) as f:
                self.data = json.load(f)
            self.mtime = m
        except (OSError, ValueError):
            pass

    def get(self, key, field, fallback):
        for src in (self.data.get('programs', {}).get(key, {}), self.data.get('default', {})):
            if src.get(field) is not None:
                return src[field]
        return fallback
