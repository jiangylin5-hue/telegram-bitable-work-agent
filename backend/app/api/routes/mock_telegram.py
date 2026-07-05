from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.schemas.telegram import (
    MockTelegramIngestionResponse,
    MockTelegramUpdate,
)
from app.services.telegram_ingestion import (
    SqlAlchemyTelegramIngestionUnitOfWork,
    TelegramIngestionUnitOfWork,
    ingest_mock_telegram_update,
)

router = APIRouter(prefix="/mock/telegram", tags=["mock-telegram"])


def get_telegram_ingestion_uow(
    session: Session = Depends(get_session),
) -> TelegramIngestionUnitOfWork:
    return SqlAlchemyTelegramIngestionUnitOfWork(session)


@router.post("/updates", response_model=MockTelegramIngestionResponse)
def receive_mock_telegram_update(
    update: MockTelegramUpdate,
    uow: TelegramIngestionUnitOfWork = Depends(get_telegram_ingestion_uow),
) -> MockTelegramIngestionResponse:
    result = ingest_mock_telegram_update(update, uow)
    uow.commit()
    return MockTelegramIngestionResponse(
        status=result.status,
        message_id=result.message_id,
        trace_id=result.trace_id,
    )
