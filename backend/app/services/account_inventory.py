from datetime import datetime, timezone
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounts import (
    AccountAssignment,
    AccountInventory,
    AccountStatusEvent,
)
from app.services.audit import record_audit_event
from app.services.permissions import Actor, assert_action_allowed
from app.services.permissions import assert_auto_mark_account_exception_allowed

ALLOWED_AUTOMATIC_EXCEPTION_STATUSES = frozenset(
    {"blocked", "disabled", "risk_controlled"}
)
ALLOWED_AUTOMATIC_EXCEPTION_RISK_FLAGS = frozenset(
    {
        "account_blocked_reported",
        "account_disabled_reported",
        "risk_control_confirmed",
    }
)
MIN_EXCEPTION_CONFIDENCE = Decimal("0.9000")


class InventoryStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountExceptionMarkResult:
    account: AccountInventory
    event: AccountStatusEvent | None
    changed: bool


class AccountInventoryUnitOfWork(Protocol):
    def add_inventory_account(self, account: AccountInventory) -> None:
        pass

    def add_status_event(self, event: AccountStatusEvent) -> None:
        pass

    def add_assignment(self, assignment: AccountAssignment) -> None:
        pass

    def get_inventory_account(self, account_id: UUID) -> AccountInventory | None:
        pass

    def get_assignment(self, assignment_id: UUID) -> AccountAssignment | None:
        pass

    def list_inventory_accounts(self) -> list[AccountInventory]:
        pass

    def add(self, value: object) -> None:
        pass


class InMemoryAccountInventoryUnitOfWork:
    def __init__(
        self,
        *,
        inventory_accounts: list[AccountInventory] | None = None,
        assignments: list[AccountAssignment] | None = None,
        status_events: list[AccountStatusEvent] | None = None,
    ) -> None:
        self.inventory_accounts = list(inventory_accounts or [])
        self.assignments = list(assignments or [])
        self.status_events = list(status_events or [])
        self.audit_events: list[object] = []

    def add_inventory_account(self, account: AccountInventory) -> None:
        self.inventory_accounts.append(account)

    def add_status_event(self, event: AccountStatusEvent) -> None:
        self.status_events.append(event)

    def add_assignment(self, assignment: AccountAssignment) -> None:
        self.assignments.append(assignment)

    def get_inventory_account(self, account_id: UUID) -> AccountInventory | None:
        return next(
            (account for account in self.inventory_accounts if account.id == account_id),
            None,
        )

    def get_assignment(self, assignment_id: UUID) -> AccountAssignment | None:
        return next(
            (assignment for assignment in self.assignments if assignment.id == assignment_id),
            None,
        )

    def list_inventory_accounts(self) -> list[AccountInventory]:
        return list(self.inventory_accounts)

    def add(self, value: object) -> None:
        self.audit_events.append(value)


class SqlAlchemyAccountInventoryUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_inventory_account(self, account: AccountInventory) -> None:
        self.session.add(account)
        self.session.flush()

    def add_status_event(self, event: AccountStatusEvent) -> None:
        self.session.add(event)
        self.session.flush()

    def add_assignment(self, assignment: AccountAssignment) -> None:
        self.session.add(assignment)
        self.session.flush()

    def get_inventory_account(self, account_id: UUID) -> AccountInventory | None:
        return self.session.get(AccountInventory, account_id)

    def get_assignment(self, assignment_id: UUID) -> AccountAssignment | None:
        return self.session.get(AccountAssignment, assignment_id)

    def list_inventory_accounts(self) -> list[AccountInventory]:
        return list(self.session.scalars(select(AccountInventory)))

    def add(self, value: object) -> None:
        self.session.add(value)


def create_inventory_account(
    uow: AccountInventoryUnitOfWork,
    *,
    actor: Actor,
    platform: str,
    external_account_id: str,
    production_batch_id: str | None = None,
) -> AccountInventory:
    assert_action_allowed(
        actor,
        "create_inventory_account",
        session=uow,
        trace_id=f"inventory:{external_account_id}",
        entity_type="account_inventory",
    )
    account = AccountInventory(
        id=uuid4(),
        platform=platform,
        external_account_id=external_account_id,
        inventory_status="unused",
        production_batch_id=production_batch_id,
        produced_by_user_id=UUID(actor.actor_id),
    )
    uow.add_inventory_account(account)
    uow.add_status_event(
        _status_event(
            account=account,
            event_type="produced",
            before_status=None,
            after_status="unused",
            actor=actor,
            reason="inventory account produced",
        )
    )
    record_audit_event(
        uow,
        trace_id=f"inventory:{external_account_id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="inventory_account_created",
        entity_type="account_inventory",
        entity_id=account.id,
        after_state={
            "platform": platform,
            "inventory_status": account.inventory_status,
            "production_batch_id": production_batch_id,
        },
    )
    return account


def list_unused_inventory_accounts(
    uow: AccountInventoryUnitOfWork,
) -> list[AccountInventory]:
    return list_inventory_accounts_by_status(uow, status="unused")


def list_inventory_accounts_by_status(
    uow: AccountInventoryUnitOfWork,
    *,
    status: str | None = None,
    customer_id: UUID | None = None,
) -> list[AccountInventory]:
    accounts = uow.list_inventory_accounts()
    if status is not None:
        accounts = [
            account
            for account in accounts
            if account.inventory_status == status
        ]
    if customer_id is not None:
        accounts = [
            account
            for account in accounts
            if account.assigned_customer_id == customer_id
        ]
    return accounts


def propose_account_assignment(
    uow: AccountInventoryUnitOfWork,
    *,
    actor: Actor,
    account_inventory_id: UUID,
    customer_id: UUID,
) -> AccountAssignment:
    assert_action_allowed(
        actor,
        "propose_account_assignment",
        session=uow,
        trace_id=f"assignment:{account_inventory_id}",
        entity_type="account_assignment",
    )
    account = _require_account(uow, account_inventory_id)
    if account.inventory_status != "unused":
        raise InventoryStateError(f"Account is not assignable: {account.inventory_status}")
    assignment = AccountAssignment(
        id=uuid4(),
        account_inventory_id=account.id,
        customer_id=customer_id,
        assigned_by_user_id=_actor_uuid_or_none(actor),
        assignment_status="proposed",
        assigned_at=datetime.now(timezone.utc),
        trace_id=f"assignment:{account.id}:{customer_id}",
    )
    uow.add_assignment(assignment)
    return assignment


def confirm_account_assignment(
    uow: AccountInventoryUnitOfWork,
    *,
    actor: Actor,
    assignment_id: UUID,
) -> AccountAssignment:
    assignment = _require_assignment(uow, assignment_id)
    assert_action_allowed(
        actor,
        "confirm_account_assignment",
        session=uow,
        trace_id=assignment.trace_id,
        entity_type="account_assignment",
        entity_id=assignment.id,
    )
    account = _require_account(uow, assignment.account_inventory_id)
    if assignment.assignment_status != "proposed":
        raise InventoryStateError(
            f"Assignment is not confirmable: {assignment.assignment_status}"
        )
    before_status = account.inventory_status
    assignment.assignment_status = "confirmed"
    assignment.confirmed_by_user_id = UUID(actor.actor_id)
    account.inventory_status = "allocated"
    account.assigned_customer_id = assignment.customer_id
    account.assigned_user_id = UUID(actor.actor_id)
    account.assigned_at = datetime.now(timezone.utc)
    uow.add_status_event(
        _status_event(
            account=account,
            event_type="assigned",
            before_status=before_status,
            after_status="allocated",
            actor=actor,
            customer_id=assignment.customer_id,
            source_entity_type="account_assignment",
            source_entity_id=assignment.id,
        )
    )
    record_audit_event(
        uow,
        trace_id=assignment.trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="inventory_account_assigned",
        entity_type="account_inventory",
        entity_id=account.id,
        before_state={"inventory_status": before_status},
        after_state={
            "inventory_status": account.inventory_status,
            "assigned_customer_id": str(assignment.customer_id),
            "assignment_id": str(assignment.id),
        },
    )
    return assignment


def activate_inventory_account(
    uow: AccountInventoryUnitOfWork,
    *,
    actor: Actor,
    account_inventory_id: UUID,
    reason: str | None = None,
) -> AccountInventory:
    assert_action_allowed(
        actor,
        "activate_inventory_account",
        session=uow,
        trace_id=f"inventory:{account_inventory_id}",
        entity_type="account_inventory",
        entity_id=account_inventory_id,
    )
    account = _require_account(uow, account_inventory_id)
    if account.inventory_status != "allocated":
        raise InventoryStateError(
            f"Account is not activatable: {account.inventory_status}"
        )
    before_status = account.inventory_status
    account.inventory_status = "activated"
    account.status_reason = reason
    uow.add_status_event(
        _status_event(
            account=account,
            event_type="activated",
            before_status=before_status,
            after_status="activated",
            actor=actor,
            reason=reason,
            customer_id=account.assigned_customer_id,
        )
    )
    record_audit_event(
        uow,
        trace_id=f"inventory:{account_inventory_id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="inventory_account_activated",
        entity_type="account_inventory",
        entity_id=account.id,
        before_state={"inventory_status": before_status},
        after_state={
            "inventory_status": account.inventory_status,
            "assigned_customer_id": (
                str(account.assigned_customer_id)
                if account.assigned_customer_id is not None
                else None
            ),
            "status_reason": reason,
        },
    )
    return account


def mark_account_exception_from_agent(
    uow: AccountInventoryUnitOfWork,
    *,
    actor: Actor,
    account_inventory_id: UUID,
    target_status: str,
    confidence: Decimal,
    risk_flags: list[str],
    source_message_id: UUID,
    reason: str,
    trace_id: str,
) -> AccountExceptionMarkResult:
    assert_auto_mark_account_exception_allowed(
        actor,
        session=uow,
        trace_id=trace_id,
        entity_type="account_inventory",
        entity_id=account_inventory_id,
    )
    if target_status not in ALLOWED_AUTOMATIC_EXCEPTION_STATUSES:
        raise InventoryStateError(
            f"Automatic account exception status is not allowed: {target_status}"
        )
    if confidence < MIN_EXCEPTION_CONFIDENCE:
        raise InventoryStateError(
            f"Automatic account exception confidence is too low: {confidence}"
        )
    if not (set(risk_flags) & ALLOWED_AUTOMATIC_EXCEPTION_RISK_FLAGS):
        raise InventoryStateError("Automatic account exception risk flag is not allowed")

    account = _require_account(uow, account_inventory_id)
    if account.inventory_status == target_status:
        return AccountExceptionMarkResult(account=account, event=None, changed=False)

    before_status = account.inventory_status
    account.inventory_status = target_status
    account.status_reason = reason
    event = _status_event(
        account=account,
        event_type=target_status,
        before_status=before_status,
        after_status=target_status,
        actor=actor,
        reason=reason,
        customer_id=account.assigned_customer_id,
        source_entity_type="message",
        source_entity_id=source_message_id,
        confidence=confidence,
        risk_flags=risk_flags,
    )
    uow.add_status_event(event)
    record_audit_event(
        uow,
        trace_id=trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="account.exception_marked",
        entity_type="account_inventory",
        entity_id=account.id,
        before_state={"inventory_status": before_status},
        after_state={
            "inventory_status": target_status,
            "confidence": str(confidence),
            "risk_flags": list(risk_flags),
            "source_message_id": str(source_message_id),
            "replacement_action": "none",
        },
    )
    return AccountExceptionMarkResult(account=account, event=event, changed=True)


def _require_account(
    uow: AccountInventoryUnitOfWork,
    account_id: UUID,
) -> AccountInventory:
    account = uow.get_inventory_account(account_id)
    if account is None:
        raise InventoryStateError(f"Inventory account not found: {account_id}")
    return account


def _require_assignment(
    uow: AccountInventoryUnitOfWork,
    assignment_id: UUID,
) -> AccountAssignment:
    assignment = uow.get_assignment(assignment_id)
    if assignment is None:
        raise InventoryStateError(f"Assignment not found: {assignment_id}")
    return assignment


def _actor_uuid_or_none(actor: Actor) -> UUID | None:
    try:
        return UUID(actor.actor_id)
    except ValueError:
        return None


def _status_event(
    *,
    account: AccountInventory,
    event_type: str,
    before_status: str | None,
    after_status: str | None,
    actor: Actor,
    reason: str | None = None,
    customer_id: UUID | None = None,
    source_entity_type: str | None = None,
    source_entity_id: UUID | None = None,
    confidence: Decimal | None = None,
    risk_flags: list[str] | None = None,
) -> AccountStatusEvent:
    return AccountStatusEvent(
        id=uuid4(),
        account_inventory_id=account.id,
        customer_id=customer_id,
        event_type=event_type,
        before_status=before_status,
        after_status=after_status,
        reason=reason,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        confidence=confidence,
        risk_flags=risk_flags,
        created_at=datetime.now(timezone.utc),
    )
