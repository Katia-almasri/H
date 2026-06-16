from fastapi import APIRouter
from app.modules.auth.router import router as auth_router
from app.modules.kyc.router import router as kyc_router
from app.modules.suitability_questionnaire.router import router as suitability_router

# Create main API v1 router
api_router = APIRouter(prefix="/api/v1")

# Register module routers
api_router.include_router(auth_router)
api_router.include_router(kyc_router)
api_router.include_router(suitability_router)

# Future module routers will be added here:
# api_router.include_router(property_router)
# api_router.include_router(investment_router)
