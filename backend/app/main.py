from fastapi import FastAPI

from app.api.routes.confirmations import router as confirmations_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.mock_telegram import router as mock_telegram_router
from app.api.routes.reports import router as reports_router
from app.api.routes.service_drafts import router as service_drafts_router
from app.api.routes.views import router as views_router
from app.core.config import get_settings, validate_runtime_settings


def create_app() -> FastAPI:
    settings = get_settings()
    validate_runtime_settings(settings)
    app = FastAPI(title=settings.app_name)
    app.include_router(confirmations_router)
    app.include_router(health_router)
    app.include_router(inventory_router)
    app.include_router(mock_telegram_router)
    app.include_router(reports_router)
    app.include_router(service_drafts_router)
    app.include_router(views_router)
    return app


app = create_app()
