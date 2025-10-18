import json
import os
import time
from typing import List, Optional, Set, Tuple

from fastapi import Header, HTTPException

# Simple TTL cache for allowed API keys
_KEYS_CACHE: Set[str] = set()
_CACHE_EXPIRES_AT: float = 0.0
_CACHE_FINGERPRINT: Optional[Tuple[str, str, str, float]] = None


def _now() -> float:
    return time.time()


def _parse_keys_from_file(path: str) -> List[str]:
    try:
        with open(path, "r") as f:
            content = f.read()
    except Exception:
        return []

    content = content.strip()
    if not content:
        return []

    # Try JSON first: support {"keys": [..]} or ["k1","k2"]
    try:
        data = json.loads(content)
        if isinstance(data, dict) and isinstance(data.get("keys"), list):
            return [str(k).strip() for k in data["keys"] if str(k).strip()]
        if isinstance(data, list):
            return [str(k).strip() for k in data if str(k).strip()]
    except Exception:
        # Fallback to newline-separated format
        pass

    return [line.strip() for line in content.splitlines() if line.strip()]


def _load_allowed_keys() -> Set[str]:
    keys: Set[str] = set()

    single = os.getenv("API_KEY", "").strip()
    if single:
        keys.add(single)

    multi = os.getenv("API_KEYS", "").strip()
    if multi:
        for k in multi.split(","):
            k = k.strip()
            if k:
                keys.add(k)

    file_path = os.getenv("API_KEYS_FILE", "").strip()
    if file_path:
        for k in _parse_keys_from_file(file_path):
            if k:
                keys.add(k)

    return keys


def _env_fingerprint() -> Tuple[str, str, str, float]:
    single = os.getenv("API_KEY", "").strip()
    multi = os.getenv("API_KEYS", "").strip()
    file_path = os.getenv("API_KEYS_FILE", "").strip()
    try:
        mtime = os.path.getmtime(file_path) if file_path else 0.0
    except Exception:
        mtime = 0.0
    return (single, multi, file_path, mtime)


def _get_allowed_keys() -> Set[str]:
    global _KEYS_CACHE, _CACHE_EXPIRES_AT, _CACHE_FINGERPRINT
    ttl = 10
    try:
        ttl = int(os.getenv("API_KEYS_TTL", "10"))
    except Exception:
        ttl = 10

    now = _now()
    fp = _env_fingerprint()
    # If env/file fingerprint changed, rebuild immediately, bypassing TTL
    if _CACHE_FINGERPRINT != fp:
        _KEYS_CACHE = _load_allowed_keys()
        _CACHE_EXPIRES_AT = now + max(ttl, 0)
        _CACHE_FINGERPRINT = fp
        return _KEYS_CACHE

    if ttl > 0 and now < _CACHE_EXPIRES_AT and _KEYS_CACHE:
        return _KEYS_CACHE

    # Rebuild cache after TTL expiry
    _KEYS_CACHE = _load_allowed_keys()
    _CACHE_EXPIRES_AT = now + max(ttl, 0)
    _CACHE_FINGERPRINT = fp
    return _KEYS_CACHE


# Read API key(s) per request with TTL cache to reflect runtime changes via file or env.
async def verify_api_key(x_api_key: str | None = Header(default=None)):
    """
    FastAPI dependency to enforce API key via `X-API-Key` header.
    Accepted keys are sourced from:
    - API_KEY (single key)
    - API_KEYS (comma-separated)
    - API_KEYS_FILE (JSON {"keys": [...]} or newline-separated)
    Uses a TTL cache (default 10s; configurable via API_KEYS_TTL) to reduce filesystem reads,
    but will immediately reload if environment variables or the keys file's mtime changes.
    If no keys are configured, requests are allowed (development convenience).
    """
    allowed = _get_allowed_keys()
    if not allowed:
        # If no keys configured, allow requests
        return
    if x_api_key in allowed:
        return
    raise HTTPException(status_code=401, detail="Invalid or missing API key")
