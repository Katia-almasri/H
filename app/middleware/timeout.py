"""Request timeout middleware."""

import asyncio

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Enforces a maximum request processing time.
    Returns 503 if the handler exceeds the timeout.
    """

    def __init__(self, app, timeout_seconds: float = 30.0):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "message": f"Request timed out after {self.timeout_seconds}s",
                    "code": HTTP_503_SERVICE_UNAVAILABLE,
                    "data": None,
                },
            )
