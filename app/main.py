from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core import logger, settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Reserve application startup and shutdown hooks."""
    logger.info("Starting up %s in %s mode", settings.app_name, settings.environment)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
