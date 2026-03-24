import time
import threading


class TTLCache:
    def __init__(self):
        self._store: dict = {}
        self._lock = threading.Lock()

    async def put(self, key, value, ttl: float):
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    async def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    async def delete(self, key):
        with self._lock:
            self._store.pop(key, None)

    async def flush_expired(self):
        now = time.monotonic()
        with self._lock:
            dead = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in dead:
                del self._store[k]