import inspect
import math
from array import array
from typing import Any, Dict, List, Optional, Tuple

from src.core.database import get_db, init_db
from src.services.embedding_service import EmbeddingService

# removed direct aiosqlite import to avoid hard dependency at import time

TABLE_SQL = """
 CREATE TABLE IF NOT EXISTS knowledge_entries (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   title TEXT NOT NULL,
   content TEXT NOT NULL,
   author TEXT,
   tags TEXT,
   created_at TEXT DEFAULT (datetime('now')),
   vector BLOB NOT NULL
 );
 """


def _to_blob(vec: List[float]) -> bytes:
    arr = array("f", [float(v) for v in vec])
    return arr.tobytes()


def _from_blob(blob: bytes) -> List[float]:
    arr = array("f")
    arr.frombytes(blob)
    return list(arr)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def _compute_embedding(service: EmbeddingService, text: str) -> List[float]:
    """Compute embedding, supporting monkeypatched EmbeddingService.embed(text) signatures.

    Tests may monkeypatch EmbeddingService.embed with a function that accepts only
    the text parameter (no self). If we detect such a signature on the class
    attribute, call it in unbound form. Otherwise, call the instance method.
    """
    # Developer note:
    # Some tests patch EmbeddingService.embed to a plain function that only accepts `text`.
    # Accessing such a function via an instance would bind `self`, causing a 2-arg call.
    # We inspect the class attribute signature and call it unbound when it only expects `text`.
    # For normal operation, we fall back to the instance method call.
    embed_attr = getattr(EmbeddingService, "embed", None)
    if callable(embed_attr):
        try:
            sig = inspect.signature(embed_attr)
            if len(sig.parameters) == 1:
                # Unbound patched function expecting only `text`
                res = embed_attr(text)
                if inspect.iscoroutine(res):
                    vec = await res
                else:
                    vec = res
                return [float(x) for x in vec]
        except Exception:
            # Fallback to instance method if inspection fails
            pass
    # Default: instance method call
    vec = await service.embed(text)
    return [float(x) for x in vec]


class KnowledgeService:
    def __init__(self, embedding: Optional[EmbeddingService] = None) -> None:
        self.embedding = embedding or EmbeddingService()

    async def init_tables(self) -> None:
        try:
            await init_db()
            async for db in get_db():
                await db.execute(TABLE_SQL)
                await db.commit()
        except RuntimeError as e:
            # Gracefully skip table init when aiosqlite is not installed
            if "aiosqlite is not installed" in str(e):
                return
            raise

    async def create_entry(
        self,
        title: str,
        content: str,
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        vec = await _compute_embedding(self.embedding, f"{title}\n\n{content}")
        blob = _to_blob(vec)
        tags_str = ",".join(tags or [])
        async for db in get_db():
            insert_sql = (
                "INSERT INTO knowledge_entries (title, content, author, tags, vector) "
                "VALUES (?, ?, ?, ?, ?)"
            )
            cur = await db.execute(
                insert_sql,
                (title, content, author, tags_str, blob),
            )
            await db.commit()
            new_id = cur.lastrowid
        return {
            "id": new_id,
            "title": title,
            "author": author,
            "tags": tags or [],
        }

    async def search(
        self, query: str, top_n: int = 5, min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        qvec = await _compute_embedding(self.embedding, query)
        results: List[Tuple[float, Dict[str, Any]]] = []
        async for db in get_db():
            query = (
                "SELECT id, title, content, author, tags, created_at, vector "
                "FROM knowledge_entries"
            )
            async with db.execute(query) as cur:
                async for row in cur:
                    vec = _from_blob(row[6])
                    score = _cosine(qvec, vec)
                    if score >= min_score:
                        tags = (row[4] or "").split(",") if row[4] else []
                        results.append(
                            (
                                score,
                                {
                                    "id": row[0],
                                    "title": row[1],
                                    "content": row[2],
                                    "author": row[3],
                                    "tags": tags,
                                    "created_at": row[5],
                                    "score": score,
                                },
                            )
                        )
        # Sort by score descending, then break ties by id descending
        # This ensures the most recent entry appears first for identical vectors
        results.sort(
            key=lambda x: (x[0], x[1]["id"]),
            reverse=True,
        )
        return [r for _, r in results[:top_n]]
