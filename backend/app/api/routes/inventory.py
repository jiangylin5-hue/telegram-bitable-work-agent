from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.accounts import AccountInventory
from app.services.account_inventory import (
    AccountInventoryUnitOfWork,
    SqlAlchemyAccountInventoryUnitOfWork,
    list_inventory_accounts_by_status,
    list_unused_inventory_accounts,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryAccountRecord(BaseModel):
    id: str
    platform: str
    external_account_id: str
    inventory_status: str
    assigned_customer_id: str | None = None
    assigned_at: str | None = None
    status_reason: str | None = None


class InventoryAccountsResponse(BaseModel):
    records: list[InventoryAccountRecord]


def get_account_inventory_uow(
    session: Session = Depends(get_session),
) -> AccountInventoryUnitOfWork:
    return SqlAlchemyAccountInventoryUnitOfWork(session)


@router.get("/accounts", response_model=InventoryAccountsResponse)
def list_inventory_accounts(
    status: str | None = "unused",
    customer_id: UUID | None = None,
    uow: AccountInventoryUnitOfWork = Depends(get_account_inventory_uow),
) -> InventoryAccountsResponse:
    if status == "unused":
        accounts = list_unused_inventory_accounts(uow)
        if customer_id is not None:
            accounts = [
                account
                for account in accounts
                if account.assigned_customer_id == customer_id
            ]
    elif status == "all":
        accounts = list_inventory_accounts_by_status(uow, customer_id=customer_id)
    else:
        accounts = list_inventory_accounts_by_status(
            uow,
            status=status,
            customer_id=customer_id,
        )
    return InventoryAccountsResponse(
        records=[_to_record(account) for account in accounts],
    )


def _to_record(account: AccountInventory) -> InventoryAccountRecord:
    return InventoryAccountRecord(
        id=str(account.id),
        platform=account.platform,
        external_account_id=account.external_account_id,
        inventory_status=account.inventory_status,
        assigned_customer_id=(
            str(account.assigned_customer_id)
            if account.assigned_customer_id is not None
            else None
        ),
        assigned_at=(
            account.assigned_at.isoformat()
            if account.assigned_at is not None
            else None
        ),
        status_reason=account.status_reason,
    )
