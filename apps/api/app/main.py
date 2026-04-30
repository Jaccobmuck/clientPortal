"""
InvoiceSaaS FastAPI application entrypoint.
P0 · bootstrap — no routes yet, just the app factory.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    # P2 will add: DB pool init, Redis ping
    yield
    # P2 will add: DB pool close, Redis close


def create_app() -> FastAPI:
    app = FastAPI(
        title="InvoiceSaaS API",
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Routers registered in P2+
    # from app.api.v1.router import api_router
    # app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
