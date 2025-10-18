from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .services.logging import init_logging
from src.api.routes.agents import router as agents_router

app = FastAPI(title="AI Agent Hosting Application", version="0.1.0")

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Basic JSON error handling
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={
        "error": "Internal Server Error",
        "message": str(exc),
    })

# Initialize logging and include routers
init_logging()
app.include_router(agents_router)