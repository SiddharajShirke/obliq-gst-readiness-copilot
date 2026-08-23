from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.middleware import UnhandledExceptionBoundaryMiddleware, UploadTokenRedactionFilter
from app.services.rag.embeddings import warm_embedding_provider

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logging.getLogger("uvicorn.access").addFilter(UploadTokenRedactionFilter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.getLogger(__name__).info(
        "Starting OBLIQ environment=%s database=%s whatsapp=%s ai=%s embedding=%s",
        settings.app_env,
        "memory" if settings.use_in_memory_db else "supabase",
        settings.whatsapp_provider,
        settings.ai_mode,
        settings.embedding_provider,
    )
    if settings.ai_mode == "live" and settings.embedding_provider != "mock":
        started = time.perf_counter()
        try:
            await warm_embedding_provider(settings)
            logging.getLogger(__name__).info(
                "RAG embedding provider warmed in %.2fs", time.perf_counter() - started
            )
        except Exception as exc:
            logging.getLogger(__name__).error(
                "RAG embedding warmup failed: %s", type(exc).__name__
            )
    yield

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Prototype API for GST document collection, extraction, validation, "
        "GSTR-2B reconciliation, RAG assistance and WhatsApp workflows."
    ),
    lifespan=lifespan,
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
