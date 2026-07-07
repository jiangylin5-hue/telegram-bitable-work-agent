from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import OpsAuditEvent
from app.models.customers import Customer
from app.models.telegram import TelegramCustomerBinding
from app.schemas.telegram_bindings import TelegramBindingCreate
from app.services.audit import record_audit_event
from app.services.permissions import Actor, assert_action_allowed


class TelegramBindingConflict(ValueError):
    pass


class TelegramBindingNotFound(LookupError):
    pass


class TelegramBindingCustomerNotFound(LookupError):
    pass


@dataclass(frozen=True)
class TelegramBindingFilters:
    customer_id: UUID | None = None
    telegram_chat_id: str | None = None
    telegram_user_id: str | None = None
    status: str | None = None


class TelegramBindingUnitOfWork(Protocol):
    audit_session: object

    def add_binding(self, binding: TelegramCustomerBinding) -> None:
        ...

    def get_binding(self, binding_id: UUID) -> TelegramCustomerBinding | None:
        ...

    def customer_exists(self, customer_id: UUID) -> bool:
        ...

    def active_conflict_exists(
        self,
        *,
        binding_scope: str,
        telegram_chat_id: str | None,
        telegram_user_id: str | None,
    ) -> bool:
        ...

    def list_bindings(
        self,
        filters: TelegramBindingFilters | None = None,
    ) -> list[TelegramCustomerBinding]:
        ...

    def flush(self) -> None:
        ...

    def commit(self) -> None:
        ...


class InMemoryTelegramBindingUnitOfWork:
    def __init__(
        self,
        *,
        bindings: Iterable[TelegramCustomerBinding] | None = None,
        customer_ids: set[UUID] | None = None,
    ) -> None:
        self.bindings = list(bindings or [])
        self.customer_ids = set(customer_ids or set())
        self.audit_events: list[OpsAuditEvent] = []
        self.committed = False
        self.flushed = False
        self.audit_session = self

    def add(self, value: object) -> None:
        if isinstance(value, OpsAuditEvent):
            self.audit_events.append(value)
            return
        raise TypeError(f"Unsupported in-memory value: {type(value)!r}")

    def add_binding(self, binding: TelegramCustomerBinding) -> None:
        self.bindings.append(binding)

    def get_binding(self, binding_id: UUID) -> TelegramCustomerBinding | None:
        return next(
            (binding for binding in self.bindings if binding.id == binding_id),
            None,
        )

    def customer_exists(self, customer_id: UUID) -> bool:
        return customer_id in self.customer_ids

    def active_conflict_exists(
        self,
        *,
        binding_scope: str,
        telegram_chat_id: str | None,
        telegram_user_id: str | None,
    ) -> bool:
        return any(
            _binding_matches_conflict(
                binding,
                binding_scope=binding_scope,
                telegram_chat_id=telegram_chat_id,
                telegram_user_id=telegram_user_id,
            )
            for binding in self.bindings
        )

    def list_bindings(
        self,
        filters: TelegramBindingFilters | None = None,
    ) -> list[TelegramCustomerBinding]:
        filters = filters or TelegramBindingFilters()
        return [
            binding
            for binding in self.bindings
            if _binding_matches_filters(binding, filters)
        ]

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True


class SqlAlchemyTelegramBindingUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit_session = session

    def add_binding(self, binding: TelegramCustomerBinding) -> None:
        self.session.add(binding)

    def get_binding(self, binding_id: UUID) -> TelegramCustomerBinding | None:
        return self.session.get(TelegramCustomerBinding, binding_id)

    def customer_exists(self, customer_id: UUID) -> bool:
        return self.session.get(Customer, customer_id) is not None

    def active_conflict_exists(
        self,
        *,
        binding_scope: str,
        telegram_chat_id: str | None,
        telegram_user_id: str | None,
    ) -> bool:
        statement = select(TelegramCustomerBinding).where(
            TelegramCustomerBinding.status == "active",
            TelegramCustomerBinding.binding_scope == binding_scope,
        )
        if binding_scope in {"chat", "chat_user"}:
            statement = statement.where(
                TelegramCustomerBinding.telegram_chat_id == telegram_chat_id
            )
        if binding_scope in {"user", "chat_user"}:
            statement = statement.where(
                TelegramCustomerBinding.telegram_user_id == telegram_user_id
            )
        return self.session.scalars(statement).first() is not None

    def list_bindings(
        self,
        filters: TelegramBindingFilters | None = None,
    ) -> list[TelegramCustomerBinding]:
        filters = filters or TelegramBindingFilters()
        statement = select(TelegramCustomerBinding).order_by(
            TelegramCustomerBinding.created_at.desc()
        )
        if filters.customer_id is not None:
            statement = statement.where(
                TelegramCustomerBinding.customer_id == filters.customer_id
            )
        if filters.telegram_chat_id is not None:
            statement = statement.where(
                TelegramCustomerBinding.telegram_chat_id == filters.telegram_chat_id
            )
        if filters.telegram_user_id is not None:
            statement = statement.where(
                TelegramCustomerBinding.telegram_user_id == filters.telegram_user_id
            )
        if filters.status is not None:
            statement = statement.where(TelegramCustomerBinding.status == filters.status)
        return list(self.session.scalars(statement))

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()


def create_telegram_binding(
    uow: TelegramBindingUnitOfWork,
    *,
    actor: Actor,
    request: TelegramBindingCreate,
) -> TelegramCustomerBinding:
    trace_id = f"telegram-binding:create:{uuid4()}"
    assert_action_allowed(
        actor,
        "manage_telegram_binding",
        session=uow.audit_session,
        trace_id=trace_id,
        entity_type="telegram_customer_binding",
    )
    if not uow.customer_exists(request.customer_id):
        raise TelegramBindingCustomerNotFound(
            f"Customer {request.customer_id} does not exist"
        )
    if uow.active_conflict_exists(
        binding_scope=request.binding_scope,
        telegram_chat_id=request.telegram_chat_id,
        telegram_user_id=request.telegram_user_id,
    ):
        record_audit_event(
            uow.audit_session,
            trace_id=trace_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            event_type="telegram.binding.create_conflict",
            entity_type="telegram_customer_binding",
            after_state={
                "customer_id": str(request.customer_id),
                "binding_scope": request.binding_scope,
                "telegram_chat_id": request.telegram_chat_id,
                "telegram_user_id": request.telegram_user_id,
            },
        )
        raise TelegramBindingConflict("Active Telegram binding already exists")

    now = datetime.now(timezone.utc)
    binding = TelegramCustomerBinding(
        id=uuid4(),
        customer_id=request.customer_id,
        telegram_chat_id=request.telegram_chat_id,
        telegram_user_id=request.telegram_user_id,
        binding_scope=request.binding_scope,
        status="active",
        label=request.label,
        created_by=request.created_by or actor.actor_id,
        created_at=now,
        updated_at=now,
    )
    uow.add_binding(binding)
    uow.flush()
    record_audit_event(
        uow.audit_session,
        trace_id=trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="telegram.binding.created",
        entity_type="telegram_customer_binding",
        entity_id=binding.id,
        after_state=_binding_state(binding),
    )
    return binding


def list_telegram_bindings(
    uow: TelegramBindingUnitOfWork,
    *,
    actor: Actor,
    filters: TelegramBindingFilters | None = None,
) -> list[TelegramCustomerBinding]:
    assert_action_allowed(
        actor,
        "manage_telegram_binding",
        session=uow.audit_session,
        trace_id=f"telegram-binding:list:{uuid4()}",
        entity_type="telegram_customer_binding",
    )
    return uow.list_bindings(filters)


def disable_telegram_binding(
    uow: TelegramBindingUnitOfWork,
    *,
    actor: Actor,
    binding_id: UUID,
    reason: str | None = None,
) -> TelegramCustomerBinding:
    trace_id = f"telegram-binding:disable:{binding_id}"
    assert_action_allowed(
        actor,
        "manage_telegram_binding",
        session=uow.audit_session,
        trace_id=trace_id,
        entity_type="telegram_customer_binding",
        entity_id=binding_id,
    )
    binding = uow.get_binding(binding_id)
    if binding is None:
        raise TelegramBindingNotFound(f"Telegram binding {binding_id} not found")

    before_state = _binding_state(binding)
    binding.status = "inactive"
    binding.updated_at = datetime.now(timezone.utc)
    uow.flush()
    record_audit_event(
        uow.audit_session,
        trace_id=trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="telegram.binding.disabled",
        entity_type="telegram_customer_binding",
        entity_id=binding.id,
        before_state=before_state,
        after_state={**_binding_state(binding), "reason": reason},
    )
    return binding


def _binding_matches_conflict(
    binding: TelegramCustomerBinding,
    *,
    binding_scope: str,
    telegram_chat_id: str | None,
    telegram_user_id: str | None,
) -> bool:
    if binding.status != "active" or binding.binding_scope != binding_scope:
        return False
    if binding_scope == "chat":
        return binding.telegram_chat_id == telegram_chat_id
    if binding_scope == "user":
        return binding.telegram_user_id == telegram_user_id
    return (
        binding.telegram_chat_id == telegram_chat_id
        and binding.telegram_user_id == telegram_user_id
    )


def _binding_matches_filters(
    binding: TelegramCustomerBinding,
    filters: TelegramBindingFilters,
) -> bool:
    if filters.customer_id is not None and binding.customer_id != filters.customer_id:
        return False
    if (
        filters.telegram_chat_id is not None
        and binding.telegram_chat_id != filters.telegram_chat_id
    ):
        return False
    if (
        filters.telegram_user_id is not None
        and binding.telegram_user_id != filters.telegram_user_id
    ):
        return False
    if filters.status is not None and binding.status != filters.status:
        return False
    return True


def _binding_state(binding: TelegramCustomerBinding) -> dict[str, str | None]:
    return {
        "binding_id": str(binding.id),
        "customer_id": str(binding.customer_id),
        "binding_scope": binding.binding_scope,
        "telegram_chat_id": binding.telegram_chat_id,
        "telegram_user_id": binding.telegram_user_id,
        "status": binding.status,
        "label": binding.label,
    }
