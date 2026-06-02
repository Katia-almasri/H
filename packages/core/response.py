"""Unified API response envelope."""

from typing import Any, Optional

from starlette.status import HTTP_200_OK


def api_response(
    message: str,
    data: Optional[Any] = None,
    code: int = HTTP_200_OK,
) -> dict:
    """Build a unified success response."""
    return {
        "success": True,
        "message": message,
        "code": code,
        "data": data,
    }
