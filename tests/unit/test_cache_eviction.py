from src.services.cache import SimpleLRUCache, cache_set, cache_get, cache_clear


def test_simple_lru_eviction_when_exceeding_maxsize():
    cache = SimpleLRUCache(maxsize=2)
    cache.set("A", 1)
    cache.set("B", 2)
    # Exceed capacity, should evict A
    cache.set("C", 3)
    assert cache.get("A") is None
    assert cache.get("B") == 2
    assert cache.get("C") == 3


def test_global_cache_clear_resets_state():
    cache_set("X", 42)
    assert cache_get("X") == 42
    cache_clear()
    assert cache_get("X") is None