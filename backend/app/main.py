from fastapi import FastAPI

from app.api.routes.confirmations import router as confirmations_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.mock_telegram import router as mock_telegram_router
from app.api.routes.reports import router as reports_router
from app.api.routes.service_drafts import router as service_drafts_router
from app.api.routes.stage06_platform import router as stage06_platform_router
from app.api.routes.stage06_runtime import router as stage06_runtime_router
from app.api.routes.stage06_templates import router as stage06_templates_router
from app.api.routes.stage07_governance import router as stage07_governance_router
from app.api.routes.stage07_governance_write import (
    router as stage07_governance_write_router,
)
from app.api.routes.stage07_draft_employee_hub import (
    router as stage07_draft_employee_hub_router,
)
from app.api.routes.stage07_digital_employee_management import (
    router as stage07_digital_employee_management_router,
)
from app.api.routes.stage07_team_bot_knowledge import (
    router as stage07_team_bot_knowledge_router,
)
from app.api.routes.stage07_telegram import router as stage07_telegram_router
from app.api.routes.stage08_collaboration import router as stage08_collaboration_router
from app.api.routes.stage08_runtime import router as stage08_runtime_router
from app.api.routes.stage08_memory import router as stage08_memory_router
from app.api.routes.stage08_retrieval import router as stage08_retrieval_router
from app.api.routes.telegram_bindings import router as telegram_bindings_router
from app.api.routes.telegram_send_requests import (
    router as telegram_send_requests_router,
)
from app.api.routes.telegram_webhook import router as telegram_webhook_router
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
    app.include_router(stage06_platform_router)
    app.include_router(stage06_runtime_router)
    app.include_router(stage06_templates_router)
    app.include_router(stage07_governance_router)
    app.include_router(stage07_governance_write_router)
    app.include_router(stage07_draft_employee_hub_router)
    app.include_router(stage07_digital_employee_management_router)
    app.include_router(stage07_team_bot_knowledge_router)
    app.include_router(stage07_telegram_router)
    app.include_router(stage08_collaboration_router)
    app.include_router(stage08_memory_router)
    app.include_router(stage08_retrieval_router)
    app.include_router(stage08_runtime_router)
    app.include_router(telegram_bindings_router)
    app.include_router(telegram_send_requests_router)
    app.include_router(telegram_webhook_router)
    app.include_router(views_router)
    return app


app = create_app()
