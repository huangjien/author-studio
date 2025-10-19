import pytest

from src.services.cache import SimpleLRUCache, cache_clear, cache_set, memoize


def test_cache_set_invalid_args_raises_value_error():
    # Fewer than 2 args should raise (need at least one key and a value)
    with pytest.raises(ValueError):
        cache_set("only_one_arg")


def test_get_updates_lru_order_affecting_eviction():
    cache = SimpleLRUCache(maxsize=2)
    cache.set("A", 1)
    cache.set("B", 2)
    # Access A to mark it as most recently used
    assert cache.get("A") == 1
    # Now inserting C should evict B (the least recently used)
    cache.set("C", 3)
    assert cache.get("B") is None
    assert cache.get("A") == 1
    assert cache.get("C") == 3


def test_memoize_caches_results_with_kwargs():
    cache_clear()
    calls = {"count": 0}

    @memoize
    def combine(a, b=0, c=0):
        calls["count"] += 1
        return a + b + c

    # First call computes the result
    assert combine(1, b=2, c=3) == 6
    assert calls["count"] == 1
    # Second call with same args/kwargs should hit cache
    assert combine(1, b=2, c=3) == 6
    assert calls["count"] == 1
    # Different kwargs order yet same values should also hit cache
    assert combine(1, c=3, b=2) == 6
    assert calls["count"] == 1
