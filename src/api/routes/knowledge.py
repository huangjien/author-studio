from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
_service = KnowledgeService()


@router.post("")
async def create_knowledge_entry(payload: Dict[str, Any]):
    title = payload.get("title")
    content = payload.get("content")
    if not title or not content:
        raise HTTPException(status_code=400, detail="Missing required fields: title, content")
    author = payload.get("author")
    tags = payload.get("tags") or []
    if tags and not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="tags must be a list of strings")
    try:
        entry = await _service.create_entry(title=title, content=content, author=author, tags=tags)
        return {"status": "ok", "entry": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_knowledge(q: str, top_n: int = 5, min_score: float = 0.0):
    try:
        results = await _service.search(query=q, top_n=top_n, min_score=min_score)
        return {"status": "ok", "query": q, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
