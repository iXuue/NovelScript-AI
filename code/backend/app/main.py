from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import conversations, evidence, exports, projects, runs, scene_plan, scripts, style_source, style_uploads, uploads

app = FastAPI(title="NovelScript AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(exc.detail), "details": {}}},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(projects.router)
app.include_router(uploads.router)
app.include_router(style_uploads.router)
app.include_router(style_source.router)
app.include_router(runs.router)
app.include_router(scene_plan.router)
app.include_router(scripts.router)
app.include_router(conversations.router)
app.include_router(evidence.router)
app.include_router(exports.router)

