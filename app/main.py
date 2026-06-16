"""Harvest API — FastAPI application entry point."""

import sys
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from app.redis_client import init_redis, close_redis
from app.middleware import TimeoutMiddleware
from packages.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

# ── Windows event loop fix for psycopg async ──────────────────────────────────
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    print("✓ Redis connected")
    print("✓ Harvest API started")
    yield
    await close_redis()
    print("✓ Shutdown complete")


# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Harvest API",
    description=(
        "Fractional Real Estate Investment Platform — UAE.\n\n"
        "### How to authenticate\n"
        "1. Register or login to get an `access_token`\n"
        "2. Click the **Authorize 🔒** button\n"
        "3. Paste the raw token (without 'Bearer' prefix)\n"
        "4. Click **Authorize**, then **Close**"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "defaultModelsExpandDepth": -1,
        "docExpansion": "list",
        "filter": True,
    },
)


# ── Exception handlers (unified JSON envelope) ────────────────────────────────
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


# ── Middleware (order matters: first added = outermost) ───────────────────────
app.add_middleware(TimeoutMiddleware, timeout_seconds=30.0)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
from app.modules.auth.router import router as auth_router  # noqa: E402
from app.modules.kyc.router import router as kyc_router  # noqa: E402
from app.modules.suitability_questionnaire.router import router as suitability_router  # noqa: E402

app.include_router(auth_router, prefix="/api/v1")
app.include_router(kyc_router, prefix="/api/v1")
app.include_router(suitability_router, prefix="/api/v1")


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/", tags=["Health"], summary="Root")
async def root():
    return {"message": "Harvest API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["Health"], summary="Health check")
async def health_check():
    return {"status": "healthy", "service": "harvest-api", "version": "1.0.0"}
