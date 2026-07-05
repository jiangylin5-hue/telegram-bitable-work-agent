from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from app.adapters.providers_mock import MockRechargeProvider
from app.models.audit import OpsAuditEvent
from app.models.outbox import OutboxEvent
from app.models.recharge import CollectionRecord, RechargeRecord
from app.models.service import ExecutionLog, ExecutionTicket, ServiceRecord
from app.services.audit import record_audit_event
from app.services.execution_tickets import use_execution_ticket


class RechargeStateError(RuntimeError):
    pass


class RechargeUnitOfWork(Protocol):
    def get_collection_record(self, collection_id: UUID) -> CollectionRecord | None:
        pass

    def get_recharge_record(self, recharge_id: UUID) -> RechargeRecord | None:
        pass

    def get_service_record(self, service_record_id: UUID) -> ServiceRecord | None:
        pass

    def get_execution_ticket(self, ticket_id: UUID) -> ExecutionTicket | None:
        pass

    def add_execution_log(self, execution_log: ExecutionLog) -> None:
        pass

    def add_recharge_record(self, recharge_record: RechargeRecord) -> None:
        pass

    def add_collection_record(self, collection_record: CollectionRecord) -> None:
        pass

    def add_outbox_event(self, event: OutboxEvent) -> None:
        pass

    def add(self, value: object) -> None:
        pass


class InMemoryRechargeUnitOfWork:
    def __init__(
        self,
        *,
        service_records: list[ServiceRecord] | None = None,
        execution_tickets: list[ExecutionTicket] | None = None,
        recharge_records: list[RechargeRecord] | None = None,
        collection_records: list[CollectionRecord] | None = None,
    ) -> None:
        self.service_records = list(service_records or [])
        self.execution_tickets = list(execution_tickets or [])
        self.recharge_records = list(recharge_records or [])
        self.collection_records = list(collection_records or [])
        self.execution_logs: list[ExecutionLog] = []
        self.outbox_events: list[OutboxEvent] = []
        self.audit_events: list[object] = []

    def get_collection_record(self, collection_id: UUID) -> CollectionRecord | None:
        return next(
            (record for record in self.collection_records if record.id == collection_id),
            None,
        )

    def get_recharge_record(self, recharge_id: UUID) -> RechargeRecord | None:
        return next(
            (record for record in self.recharge_records if record.id == recharge_id),
            None,
        )

    def get_service_record(self, service_record_id: UUID) -> ServiceRecord | None:
        return next(
            (
                record
                for record in self.service_records
                if record.id == service_record_id
            ),
            None,
        )

    def get_execution_ticket(self, ticket_id: UUID) -> ExecutionTicket | None:
        return next(
            (ticket for ticket in self.execution_tickets if ticket.id == ticket_id),
            None,
        )

    def add_execution_log(self, execution_log: ExecutionLog) -> None:
        self.execution_logs.append(execution_log)

    def add_recharge_record(self, recharge_record: RechargeRecord) -> None:
        self.recharge_records.append(recharge_record)

    def add_collection_record(self, collection_record: CollectionRecord) -> None:
        self.collection_records.append(collection_record)

    def add_outbox_event(self, event: OutboxEvent) -> None:
        self.outbox_events.append(event)

    def add(self, value: object) -> None:
        self.audit_events.append(value)


def confirm_collection(
    uow: RechargeUnitOfWork,
    collection_id: UUID,
    *,
    confirmed_by_user_id: UUID,
) -> None:
    collection = uow.get_collection_record(collection_id)
    if collection is None:
        raise RechargeStateError(f"Collection not found: {collection_id}")
    if collection.recharge_record_id is None:
        raise RechargeStateError("Collection is not linked to recharge")
    recharge = uow.get_recharge_record(collection.recharge_record_id)
    if recharge is None:
        raise RechargeStateError(f"Recharge not found: {collection.recharge_record_id}")

    before_state = {
        "collection_status": collection.collection_status,
        "recharge_collection_status": recharge.collection_status,
        "recharge_execution_status": recharge.execution_status,
    }
    collection.collection_status = "confirmed"
    collection.confirmed_by_user_id = confirmed_by_user_id
    collection.confirmed_at = datetime.now(timezone.utc)
    recharge.collection_record_id = collection.id
    recharge.collection_status = "confirmed"
    record_audit_event(
        uow,
        trace_id=collection.trace_id,
        actor_type="user",
        actor_id=str(confirmed_by_user_id),
        event_type="collection_confirmed",
        entity_type="collection_record",
        entity_id=collection.id,
        before_state=before_state,
        after_state={
            "collection_status": collection.collection_status,
            "recharge_collection_status": recharge.collection_status,
            "recharge_execution_status": recharge.execution_status,
            "recharge_record_id": str(recharge.id),
        },
    )


def create_recharge_record_from_confirmation(
    uow: RechargeUnitOfWork,
    *,
    service_record: ServiceRecord,
    ticket: ExecutionTicket,
    amount: Decimal,
    currency: str,
) -> RechargeRecord:
    recharge = RechargeRecord(
        id=uuid4(),
        service_record_id=service_record.id,
        customer_id=service_record.customer_id,
        account_asset_id=service_record.account_asset_id,
        amount=amount,
        currency=currency,
        collection_status="pending",
        execution_status="queued",
        readback_status="not_started",
        execution_ticket_id=ticket.id,
    )
    uow.add_recharge_record(recharge)
    record_audit_event(
        uow,
        trace_id=service_record.trace_id,
        actor_type="system",
        actor_id="recharge.service",
        event_type="recharge_record_created",
        entity_type="recharge_record",
        entity_id=recharge.id,
        after_state={
            "service_record_id": str(service_record.id),
            "customer_id": str(service_record.customer_id),
            "collection_status": recharge.collection_status,
            "execution_status": recharge.execution_status,
            "readback_status": recharge.readback_status,
        },
    )
    return recharge


def create_collection_record_for_recharge(
    uow: RechargeUnitOfWork,
    *,
    recharge: RechargeRecord,
    collection_method: str,
) -> CollectionRecord:
    collection = CollectionRecord(
        id=uuid4(),
        customer_id=recharge.customer_id,
        recharge_record_id=recharge.id,
        amount=recharge.amount,
        currency=recharge.currency,
        collection_method=collection_method,
        collection_status="pending",
        trace_id=f"collection:{recharge.id}",
    )
    uow.add_collection_record(collection)
    record_audit_event(
        uow,
        trace_id=collection.trace_id,
        actor_type="system",
        actor_id="recharge.service",
        event_type="collection_record_created",
        entity_type="collection_record",
        entity_id=collection.id,
        after_state={
            "recharge_record_id": str(recharge.id),
            "customer_id": str(recharge.customer_id),
            "collection_status": collection.collection_status,
        },
    )
    return collection


def execute_recharge_with_mock_provider(
    uow: RechargeUnitOfWork,
    recharge_id: UUID,
    *,
    provider: MockRechargeProvider | None = None,
) -> None:
    recharge = uow.get_recharge_record(recharge_id)
    if recharge is None:
        raise RechargeStateError(f"Recharge not found: {recharge_id}")
    if recharge.execution_ticket_id is None:
        raise RechargeStateError("Recharge has no execution ticket")
    ticket = uow.get_execution_ticket(recharge.execution_ticket_id)
    if ticket is None:
        raise RechargeStateError(f"Ticket not found: {recharge.execution_ticket_id}")
    service_record = uow.get_service_record(recharge.service_record_id)
    if service_record is None:
        raise RechargeStateError(f"Service not found: {recharge.service_record_id}")

    before_state = {
        "service_status": service_record.status,
        "ticket_status": ticket.status,
        "execution_status": recharge.execution_status,
        "readback_status": recharge.readback_status,
    }
    use_execution_ticket(ticket)
    provider = provider or MockRechargeProvider()
    result = provider.execute_recharge(
        recharge_id=str(recharge.id),
        amount=str(recharge.amount),
        currency=recharge.currency,
    )
    log = ExecutionLog(
        service_record_id=service_record.id,
        provider=provider.provider,
        provider_request_id=result.provider_request_id,
        provider_response_id=result.provider_response_id,
        execution_status="succeeded",
        request_summary=result.request_summary,
        response_summary=result.response_summary,
        trace_id=service_record.trace_id,
    )
    uow.add_execution_log(log)
    service_record.status = "succeeded"
    recharge.execution_status = "succeeded"
    recharge.readback_status = "pending"
    uow.add_outbox_event(
        OutboxEvent(
            event_type="readback.balance",
            payload={"recharge_id": str(recharge.id)},
            status="pending",
            attempts=0,
            max_attempts=3,
            idempotency_key=f"readback:{recharge.id}",
            trace_id=service_record.trace_id,
        )
    )
    record_audit_event(
        uow,
        trace_id=service_record.trace_id,
        actor_type="worker",
        actor_id="execution.recharge",
        event_type="recharge_execution_succeeded",
        entity_type="recharge_record",
        entity_id=recharge.id,
        before_state=before_state,
        after_state={
            "service_status": service_record.status,
            "ticket_status": ticket.status,
            "execution_status": recharge.execution_status,
            "readback_status": recharge.readback_status,
            "execution_log_count": 1,
        },
    )


def mark_readback_failed(
    uow: RechargeUnitOfWork,
    recharge_id: UUID,
    *,
    error_message: str,
) -> None:
    recharge = uow.get_recharge_record(recharge_id)
    if recharge is None:
        raise RechargeStateError(f"Recharge not found: {recharge_id}")
    recharge.readback_status = "failed"
    recharge.readback_at = datetime.now(timezone.utc)
    record_audit_event(
        uow,
        trace_id="readback",
        actor_type="worker",
        actor_id="readback.balance",
        event_type="readback_failed",
        entity_type="recharge_record",
        entity_id=recharge.id,
        after_state={
            "execution_status": recharge.execution_status,
            "readback_status": recharge.readback_status,
            "error_message": error_message,
        },
    )
