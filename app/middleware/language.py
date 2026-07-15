"""Language detection middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from packages.core.i18n import (
    get_current_language,
    reset_current_language,
    set_current_language,
)


class LanguageMiddleware(BaseHTTPMiddleware):
    """Detect request language from headers and expose it through i18n context."""

    async def dispatch(self, request: Request, call_next):
        language_header = (
            request.headers.get("accept-language")
            or request.headers.get("accept-lang")
        )
        token = set_current_language(language_header)
        request.state.language = get_current_language()

        try:
            response = await call_next(request)
        except Exception:
            reset_current_language(token)
            raise

        response.headers["Content-Language"] = request.state.language
        vary = response.headers.get("Vary")
        if not vary:
            response.headers["Vary"] = "Accept-Language"
        elif "accept-language" not in vary.lower():
            response.headers["Vary"] = f"{vary}, Accept-Language"

        reset_current_language(token)
        return response
