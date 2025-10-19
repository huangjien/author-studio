import logging
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


def _wikipedia_search(query: str, top_n: int) -> List[Dict[str, Any]]:
    """
    Perform a simple real web search via Wikipedia's search API.

    This is a lightweight, dependency-free approach to demonstrate fetching
    real information from the web without relying on third-party SERP services.
    """
    if not query:
        return []
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": max(1, min(top_n, 5)),
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in (data.get("query", {}).get("search", []) or [])[:top_n]:
            title = item.get("title") or ""
            snippet = item.get("snippet") or ""
            # Construct a canonical Wikipedia article URL
            article_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            results.append(
                {
                    "title": title,
                    "url": article_url,
                    "snippet": snippet,
                }
            )
        return results
    except Exception as e:  # noqa: BLE001
        logger.warning("Real web search via Wikipedia failed: %s", e)
        return []


def web_search(query: str, top_n: int = 5) -> Dict[str, Any]:
    """
    Real web_search provider that returns live results.

    Response shape matches the local_web_search provider:
    {
      "tool": "web_search",
      "query": query,
      "results": [ {"title": str, "url": str, "snippet": str}, ... ]
    }
    """
    results = _wikipedia_search(query=query, top_n=top_n)
    return {
        "tool": "web_search",
        "query": query,
        "results": results,
    }
