from typing import Callable, Any
from collections import OrderedDict

class SimpleLRUCache:
    def __init__(self, maxsize: int = 1024):
        self.maxsize = maxsize
        self._store = OrderedDict()

    def get(self, key: str) -> Any:
        if key in self._store:
            # Move to end to mark as recently used
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self.maxsize:
            # Evict least recently used (first item)
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

_cache = SimpleLRUCache(maxsize=1024)

def cache_get(key: str) -> Any:
    return _cache.get(key)

def cache_set(key: str, value: Any) -> None:
    _cache.set(key, value)

def cache_clear() -> None:
    _cache.clear()

def memoize(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
    def wrapper(*args, **kwargs):
        key = f"{func.__name__}:{args}:{tuple(sorted(kwargs.items()))}"
        val = cache_get(key)
        if val is not None:
            return val
        result = func(*args, **kwargs)
        cache_set(key, result)
        return result
    return wrapper