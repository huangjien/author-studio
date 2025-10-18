import os
from src.services.persistence import FileStore


def test_file_store_save_and_load(tmp_path):
    base = os.path.join(str(tmp_path), ".data")
    store = FileStore(base_dir=base)

    payload = {"hello": "world", "n": 1}
    store.save("test", payload)
    loaded = store.load("test")
    assert loaded == payload


def test_file_store_load_missing_returns_none(tmp_path):
    base = os.path.join(str(tmp_path), ".data")
    store = FileStore(base_dir=base)
    assert store.load("missing") is None