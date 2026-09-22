from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.merchants import router as merchants_router
from app.api.v1.orders import router as orders_router

api_router = APIRouter()
api_router.include_router(
    auth_router, prefix="/auth", tags=["Auth"]
)
api_router.include_router(
    merchants_router, prefix="/merchants", tags=["Merchants"]
)
api_router.include_router(
    orders_router, prefix="/orders", tags=["Orders"]
)
