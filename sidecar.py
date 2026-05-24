import json
import os


class Sidecar:
    def __init__(self, src_path):
        self.src = src_path
        self.path = src_path + '.json'
        self.data = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
        except Exception:
            self.data = {}

    def save(self):
        try:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass
