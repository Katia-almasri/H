from fastapi import APIRouter
from app.modules.auth.router import router as auth_router

# Create main API v1 router
api_router = APIRouter(prefix="/api/v1")

# Register module routers
api_router.include_router(auth_router)

# Future module routers will be added here:
# api_router.include_router(user_router)
# api_router.include_router(property_router)
# api_router.include_router(investment_router)
