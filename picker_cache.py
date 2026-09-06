"""Disposable, versioned picker responses; artwork is lazy-loaded, not embedded."""
import hashlib
import json
import os
import tempfile
import time


class PickerCache:
    def __init__(self, directory, max_age_days=7):
        self.directory = directory
        self.max_age = max_age_days * 86400

    def key(self, payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def get(self, key):
        path = os.path.join(self.directory, key + '.json')
        try:
            if time.time() - os.path.getmtime(path) > self.max_age:
                return None
            with open(path, encoding='utf-8') as source:
                return json.load(source)
        except (OSError, ValueError):
            return None

    def put(self, key, payload):
        os.makedirs(self.directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(payload, output)
            os.replace(temporary, os.path.join(self.directory, key + '.json'))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def clear(self):
        if os.path.isdir(self.directory):
            for name in os.listdir(self.directory):
                if name.endswith('.json'):
                    try:
                        os.unlink(os.path.join(self.directory, name))
                    except FileNotFoundError:
                        pass
