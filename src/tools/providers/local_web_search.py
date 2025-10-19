from typing import Any, Dict, List

# Deterministic local implementation of a 'web_search' MCP tool for offline tests.
# In a real MCP setup, this would forward the request to an external server.
# Here we return predictable content so tests can assert behavior without network.

MOCK_INDEX = {
    "hello": [
        {
            "title": "Hello World - Wikipedia",
            "url": "https://example.org/hello",
            "snippet": "Hello World examples across languages.",
        },
        {
            "title": "Greeting Etiquette",
            "url": "https://example.org/greetings",
            "snippet": "How to greet politely in many cultures.",
        },
    ],
    "alpha bot": [
        {
            "title": "Alpha Bot Docs",
            "url": "https://example.org/alpha-bot",
            "snippet": "User guide for Alpha Bot.",
        },
        {
            "title": "Author Studio",
            "url": "https://example.org/studio",
            "snippet": "Project overview and docs.",
        },
    ],
    "python": [
        {
            "title": "Python Official",
            "url": "https://example.org/python",
            "snippet": "Python language homepage.",
        },
        {
            "title": "Pydantic v2",
            "url": "https://example.org/pydantic",
            "snippet": "Data validation with Python types.",
        },
    ],
}


def web_search(query: str, top_n: int = 5, **kwargs: Any) -> Dict[str, Any]:
    # Normalize query key
    key = query.strip().lower()
    results: List[Dict[str, str]] = []
    if key in MOCK_INDEX:
        results = MOCK_INDEX[key][:top_n]
    else:
        # Fallback deterministic results
        results = [
            {
                "title": f"Result for: {query}",
                "url": f"https://example.org/search?q={query.replace(' ', '+')}",
                "snippet": f"Synthetic result for query '{query}'.",
            }
        ]
    return {"tool": "web_search", "query": query, "results": results}


# End of file
