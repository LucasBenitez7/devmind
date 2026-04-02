import time
import uuid

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import DevMindException

log = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[operator]
        duration_ms = round((time.perf_counter() - start_time) * 1000)

        response.headers["X-Request-ID"] = request_id

        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response


async def devmind_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, DevMindException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.user_message},
        )

    log.error("unhandled.exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "Algo salió mal de nuestro lado. Ya fuimos notificados. Inténtalo de nuevo en unos minutos."
        },
    )
