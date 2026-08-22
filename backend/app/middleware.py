"""Application middleware that keeps unexpected API failures safe and observable."""

from __future__ import annotations

import logging
import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)
_UPLOAD_TOKEN_PATH = re.compile(
    r"((?:/api/v1/public)?/upload/)[A-Za-z0-9_-]{43}(?=[/?#\s]|$)"
)


def redact_upload_token_path(value: str) -> str:
    return _UPLOAD_TOKEN_PATH.sub(r"\1[REDACTED]", value)


class UploadTokenRedactionFilter(logging.Filter):
    """Remove public upload capabilities from Uvicorn access-log arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_upload_token_path(value) if isinstance(value, str) else value
                for value in record.args
            )
        elif isinstance(record.args, dict):
            record.args = {
                key: redact_upload_token_path(value)
                if isinstance(value, str)
                else value
                for key, value in record.args.items()
            }
        return True


class UnhandledExceptionBoundaryMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception:
            logger.exception(
                "Unhandled API exception: method=%s path=%s",
                scope.get("method", "UNKNOWN"),
                redact_upload_token_path(scope.get("path", "")),
            )
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
            await response(scope, receive, send)
