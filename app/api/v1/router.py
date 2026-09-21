from fastapi import APIRouter

from app.api.v1.merchants import router as merchants_router

api_router = APIRouter()
api_router.include_router(
    merchants_router, prefix="/merchants", tags=["Merchants"]
)
