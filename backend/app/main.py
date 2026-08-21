from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.middleware import UnhandledExceptionBoundaryMiddleware

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Prototype API for GST document collection, extraction, validation, "
        "GSTR-2B reconciliation, RAG assistance and WhatsApp workflows."
    ),
)
# Add the exception boundary first so CORS is the outer user middleware and
# therefore decorates sanitized 500 responses as well as successful responses.
app.add_middleware(UnhandledExceptionBoundaryMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }
