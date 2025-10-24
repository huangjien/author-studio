from typing import Any, Dict, Optional

import httpx


def fetch(
    url: str,
    timeout: float = 5.0,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Minimal local fallback implementation of a 'fetch' tool using httpx.

    Returns a response shape compatible with ToolService expectations:
    {
      "tool": "fetch",
      "query": <url>,
      "results": [
        {
          "status": <status_code>,
          "body": <text_body>,
          "headers": <headers_dict>,
          "url": <final_url>,
          "content_type": <content_type_header>
        }
      ]
    }
    """
    url = str(url or "").strip()
    if not url:
        return {
            "tool": "fetch",
            "query": url,
            "results": [
                {
                    "status": 400,
                    "body": "",
                    "headers": {},
                    "url": url,
                    "content_type": "",
                }
            ],
        }
    headers = headers or {}
    try:
        with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout) as client:
            resp = client.get(url)
            body_text = resp.text if isinstance(resp.text, str) else str(resp.content)
            return {
                "tool": "fetch",
                "query": url,
                "results": [
                    {
                        "status": resp.status_code,
                        "body": body_text,
                        "headers": dict(resp.headers.items()),
                        "url": str(resp.url),
                        "content_type": resp.headers.get("Content-Type", ""),
                    }
                ],
            }
    except Exception as e:  # noqa: BLE001
        return {
            "tool": "fetch",
            "query": url,
            "results": [
                {
                    "status": 520,
                    "body": f"Local fetch error: {e}",
                    "headers": {},
                    "url": url,
                    "content_type": "",
                }
            ],
        }


# EOF
# tail