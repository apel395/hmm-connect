import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings


def _cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ]


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def journal_only_accounting_post(request: Request, call_next):
    """Prevent legacy module endpoints from bypassing the Journal workspace.

    Supplier Payment still keeps its historical /post route for API compatibility,
    but accounting posting is now exclusively performed by /journal-entries/{id}/post.
    """
    if request.method == "POST" and re.fullmatch(r"/api/v1/payments/\d+/post/?", request.url.path):
        return JSONResponse(
            status_code=409,
            content={"detail": "Post the related journal from the Journal page"},
        )
    return await call_next(request)


app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
