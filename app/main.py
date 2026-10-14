from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.prices import router as prices_router
from app.core.config import Settings
from app.db.session import create_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory: every dependency is built here, nothing lives in module globals."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(
        title="Deribit Price Tracker",
        description="Index prices of BTC and ETH collected from Deribit every minute.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(prices_router, prefix="/api/v1")

    @app.get("/health", tags=["service"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
