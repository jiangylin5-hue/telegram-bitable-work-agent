from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_system_actor
from app.core.database import get_session
from app.core.errors import error_detail
from app.schemas.views import ViewResponse
from app.services.bitable_views import (
    BitableViewDataSource,
    SqlAlchemyBitableViewDataSource,
    UnknownViewError,
    get_view_records,
)
from app.services.permissions import Actor

router = APIRouter(prefix="/views", tags=["views"])


def get_bitable_view_data_source(
    session: Session = Depends(get_session),
) -> BitableViewDataSource:
    return SqlAlchemyBitableViewDataSource(session=session)


@router.get("/{view_key}/records", response_model=ViewResponse)
def read_view_records(
    view_key: str,
    limit: int | None = Query(default=None, ge=1),
    data_source: BitableViewDataSource = Depends(get_bitable_view_data_source),
    actor: Actor = Depends(get_system_actor),
) -> ViewResponse:
    try:
        return get_view_records(
            view_key,
            data_source=data_source,
            actor=actor,
            limit=limit,
        )
    except UnknownViewError as exc:
        raise HTTPException(
            status_code=404,
            detail=error_detail("unknown_view", str(exc)),
        ) from exc
