import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"

async def wait_for_health(timeout_ms: int = 5000) -> None:
    deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=2.0) as client:
        while True:
            try:
                resp = await client.get("/health")
                if resp.status_code == 200:
                    return
            except Exception:
                pass
            if asyncio.get_event_loop().time() > deadline:
                raise RuntimeError("Server health endpoint did not become ready in time")
            await asyncio.sleep(0.2)

async def run_smoke() -> None:
    await wait_for_health()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        # Create a knowledge entry
        payload = {
            "title": "FastAPI Tips",
            "content": "FastAPI is a modern, fast web framework for building APIs with Python.",
            "author": "demo",
            "tags": ["fastapi", "python", "api"],
        }
        resp = await client.post("/knowledge", json=payload)
        resp.raise_for_status()
        data = resp.json()
        assert data.get("status") == "ok", f"Unexpected create status: {data}"
        entry = data.get("entry")
        assert entry and "id" in entry, f"Missing entry id in response: {data}"
        print(f"Created entry id={entry['id']}, title={entry['title']}")

        # Search
        params = {"q": "FastAPI", "top_n": 5, "min_score": 0.0}
        resp = await client.get("/knowledge/search", params=params)
        resp.raise_for_status()
        search = resp.json()
        assert search.get("status") == "ok", f"Unexpected search status: {search}"
        results = search.get("results") or []
        assert len(results) >= 1, "Expected at least one search result"
        top = results[0]
        print(f"Top result id={top['id']} title={top['title']} score={top.get('score')}")

    print("Smoke test passed: create + search")

if __name__ == "__main__":
    asyncio.run(run_smoke())