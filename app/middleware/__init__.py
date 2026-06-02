"""Application middleware."""

from app.middleware.timeout import TimeoutMiddleware

__all__ = ["TimeoutMiddleware"]
