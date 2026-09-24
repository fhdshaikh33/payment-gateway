from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.merchants import router as merchants_router
from app.api.v1.orders import router as orders_router
from app.api.v1.payments import router as payments_router
from app.api.v1.switch import router as switch_router
from app.api.v1.ledger import router as ledger_router
from app.api.v1.webhooks import router as webhooks_router

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
api_router.include_router(
    payments_router, prefix="/payments", tags=["Payments"]
)
api_router.include_router(
    switch_router, prefix="/switch", tags=["Bank Switch"]
)
api_router.include_router(
    ledger_router, prefix="/ledger", tags=["Ledger"]
)
api_router.include_router(
    webhooks_router, prefix="/webhooks", tags=["Webhooks"]
)

