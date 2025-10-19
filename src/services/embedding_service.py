import os
from typing import List, Optional

import httpx


class EmbeddingService:
    """Simple Ollama embedding client for generating vector representations."""

    def __init__(
        self, host: Optional[str] = None, model: Optional[str] = None, timeout: float = 10.0
    ) -> None:
        # Resolve host from argument or environment, falling back to default if empty
        raw_host = host if host is not None else os.getenv("OLLAMA_HOST", "http://localhost:11434")
        if not raw_host or not str(raw_host).strip():
            raw_host = "http://localhost:11434"
        # Ensure scheme is present
        if not str(raw_host).startswith(("http://", "https://")):
            raw_host = "http://" + str(raw_host).lstrip("/")
        self.host = raw_host

        raw_model = (
            model
            if model is not None
            else os.getenv("OLLAMA_EMBED_MODEL", "Qwen3-Embedding:latest")
        )
        self.model = (
            raw_model if (raw_model and str(raw_model).strip()) else "Qwen3-Embedding:latest"
        )
        self.timeout = timeout

    async def embed(self, text: str) -> List[float]:
        url = f"{self.host.rstrip('/')}/api/embeddings"
        payload = {
            "model": self.model,
            "prompt": text,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Ollama returns { "embedding": [floats...] }
            vec = data.get("embedding") or data.get("embeddings")
            if not isinstance(vec, list):
                raise ValueError("Invalid embedding response structure")
            # Ensure floats
            return [float(x) for x in vec]
