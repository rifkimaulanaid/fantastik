"""Small shared cache of successfully parsed public article text only."""
from collections import OrderedDict
import threading
import time

_entries = OrderedDict()
_lock = threading.Lock()
MAX_CHARS = 8_000_000
TTL = 300


def get_content(key):
    with _lock:
        cached = _entries.get(key)
        if cached and time.monotonic() - cached[0] < TTL:
            _entries.move_to_end(key)
            return cached[1]
        _entries.pop(key, None)
    return None


def put_content(key, text):
    if not text or len(text) > MAX_CHARS:
        return
    with _lock:
        _entries[key] = (time.monotonic(), text)
        _entries.move_to_end(key)
        while len(_entries) > 64 or sum(len(item[1]) for item in _entries.values()) > MAX_CHARS:
            _entries.popitem(last=False)
