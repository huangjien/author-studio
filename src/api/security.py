import os
from fastapi import Header, HTTPException

# Read API key fresh per request to reflect runtime changes in tests/environments
async def verify_api_key(x_api_key: str | None = Header(default=None)):
    """
    FastAPI dependency to enforce API key via `X-API-Key` header.
    Expected value is read from the `API_KEY` environment variable.
    """
    expected = os.getenv("API_KEY", "")
    if not expected:
        # If no env var set, allow requests (development convenience)
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")