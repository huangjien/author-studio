from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple


class SimpleLRUCache:
    def __init__(self, maxsize: int = 256):
        self.maxsize = maxsize
        self.cache: Dict[Tuple[Any, ...], Any] = {}
        self.order: list[Tuple[Any, ...]] = []

    def get(self, key: Tuple[Any, ...]) -> Optional[Any]:
        if key in self.cache:
            self.order.remove(key)
            self.order.append(key)
            return self.cache[key]
        return None

    def set(self, key: Tuple[Any, ...], value: Any) -> None:
        if key in self.cache:
            self.order.remove(key)
        elif len(self.order) >= self.maxsize:
            oldest = self.order.pop(0)
            del self.cache[oldest]
        self.cache[key] = value
        self.order.append(key)


_cache = SimpleLRUCache(maxsize=512)


def cache_get(*args: Any) -> Optional[Any]:
    return _cache.get(args)


def cache_set(*args: Any) -> None:
    # Accept a flexible calling convention: cache_set(key1, key2, ..., value)
    # The last argument is treated as the value; preceding arguments form the key tuple.
    if len(args) < 2:
        raise ValueError("cache_set requires at least one key and a value")
    key = tuple(args[:-1])
    value = args[-1]
    _cache.set(key, value)


def cache_clear() -> None:
    _cache.cache.clear()
    _cache.order.clear()


def memoize(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = args + tuple(sorted(kwargs.items()))
        cached = cache_get(*key)
        if cached is not None:
            return cached
        result = func(*args, **kwargs)
        cache_set(*key, result)
        return result

    return wrapper