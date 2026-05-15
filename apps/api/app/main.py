from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.clients import router as clients_router
from app.api.v1.expenses import router as expenses_router
from app.api.v1.health import router as health_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.members import router as members_router
from app.api.v1.org import router as org_router
from app.api.v1.projects import router as projects_router
from app.api.v1.smoke import router as smoke_router
from app.api.internal.pdf import router as internal_pdf_router
from app.core.lifespan import lifespan
from app.core.settings import settings
from app.middleware.exception_handlers import register_exception_handlers
from app.middleware.request_id import RequestIDMiddleware


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
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(org_router, prefix="/api/v1")
    app.include_router(members_router, prefix="/api/v1")
    app.include_router(clients_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(expenses_router, prefix="/api/v1")
    app.include_router(invoices_router, prefix="/api/v1")
    app.include_router(smoke_router, prefix="/api/v1")
    app.include_router(internal_pdf_router)

    return app


app = create_app()
