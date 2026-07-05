from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select

from app.models import metadata
from app.schemas.views import ViewRecord, ViewResponse
from app.services.permissions import (
    Actor,
    allowed_fields_for_actor,
    can_view_customer_record,
)

MASKED_VALUE = "[masked]"


class UnknownViewError(ValueError):
    pass


@dataclass(frozen=True)
class ViewDefinition:
    view_key: str
    table_name: str
    fields: tuple[str, ...]
    sensitive_fields: frozenset[str] = frozenset()


class BitableViewDataSource(Protocol):
    def list_records(self, table_name: str) -> list[dict[str, Any]]:
        pass


class EmptyBitableViewDataSource:
    def list_records(self, table_name: str) -> list[dict[str, Any]]:
        return []


class InMemoryBitableViewDataSource:
    def __init__(self) -> None:
        self.records_by_table: dict[str, list[dict[str, Any]]] = {}

    def add_record(
        self,
        table_name: str,
        *,
        record_id: str,
        fields: dict[str, Any],
    ) -> None:
        self.records_by_table.setdefault(table_name, []).append(
            {"id": record_id, "fields": dict(fields)}
        )

    def list_records(self, table_name: str) -> list[dict[str, Any]]:
        return list(self.records_by_table.get(table_name, []))


class SqlAlchemyBitableViewDataSource:
    def __init__(self, *, session: Any) -> None:
        self.session = session

    def list_records(self, table_name: str) -> list[dict[str, Any]]:
        table = metadata.tables.get(table_name)
        if table is None:
            return []
        rows = self.session.execute(select(table)).all()
        return [_row_to_record(row) for row in rows]


STAGE_02_VIEW_REGISTRY: dict[str, ViewDefinition] = {
    "telegram_inbox": ViewDefinition(
        view_key="telegram_inbox",
        table_name="messages",
        fields=(
            "telegram_chat_id",
            "telegram_message_id",
            "message_type",
            "intent_status",
            "intent_type",
            "received_at",
            "trace_id",
            "raw_text",
        ),
        sensitive_fields=frozenset({"raw_text"}),
    ),
    "ai_draft_queue": ViewDefinition(
        view_key="ai_draft_queue",
        table_name="service_drafts",
        fields=("status", "intent_type", "customer_id", "trace_id"),
    ),
    "recharge_view": ViewDefinition(
        view_key="recharge_view",
        table_name="recharge_records",
        fields=(
            "customer_id",
            "account_asset_id",
            "amount",
            "currency",
            "collection_status",
            "execution_status",
            "readback_status",
            "readback_at",
        ),
    ),
    "account_inventory": ViewDefinition(
        view_key="account_inventory",
        table_name="account_inventory",
        fields=(
            "platform",
            "external_account_id",
            "inventory_status",
            "assigned_customer_id",
            "assigned_at",
            "status_reason",
            "trace_id",
        ),
        sensitive_fields=frozenset({"external_account_id"}),
    ),
    "payment_profiles": ViewDefinition(
        view_key="payment_profiles",
        table_name="payment_profiles",
        fields=(
            "provider",
            "tokenized_profile_id",
            "masked_label",
            "last4",
            "brand",
            "status",
            "customer_id",
            "last_checked_at",
        ),
        sensitive_fields=frozenset({"tokenized_profile_id"}),
    ),
    "account_card_bindings": ViewDefinition(
        view_key="account_card_bindings",
        table_name="account_card_bindings",
        fields=(
            "account_asset_id",
            "payment_profile_id",
            "customer_id",
            "binding_status",
            "one_card_one_account_policy",
            "bound_at",
            "unbound_at",
            "failure_reason",
            "trace_id",
        ),
        sensitive_fields=frozenset({"payment_profile_id", "failure_reason"}),
    ),
    "customer_daily_reports": ViewDefinition(
        view_key="customer_daily_reports",
        table_name="customer_daily_reports",
        fields=(
            "customer_id",
            "report_date",
            "delivery_status",
            "report_payload",
            "visibility_scope",
            "trace_id",
        ),
    ),
    "company_daily_reports": ViewDefinition(
        view_key="company_daily_reports",
        table_name="company_daily_reports",
        fields=("report_date", "delivery_status", "report_payload", "trace_id"),
    ),
    "audit_view": ViewDefinition(
        view_key="audit_view",
        table_name="ops_audit_events",
        fields=("trace_id", "actor_type", "event_type", "entity_type", "created_at"),
    ),
}


def get_view_definition(view_key: str) -> ViewDefinition:
    try:
        return STAGE_02_VIEW_REGISTRY[view_key]
    except KeyError as exc:
        raise UnknownViewError(f"Unknown view: {view_key}") from exc


def mask_record_fields(
    record: dict[str, Any],
    allowed_fields: set[str],
) -> dict[str, Any]:
    fields = record.get("fields", {})
    return {
        "id": record["id"],
        "fields": {
            key: value if key in allowed_fields else MASKED_VALUE
            for key, value in fields.items()
        },
    }


def get_view_records(
    view_key: str,
    *,
    data_source: BitableViewDataSource | None = None,
    allowed_fields: set[str] | None = None,
    actor: Actor | None = None,
) -> ViewResponse:
    view = get_view_definition(view_key)
    data_source = data_source or EmptyBitableViewDataSource()
    allowed_fields = allowed_fields or _allowed_fields_for_view(view, actor)
    records = [
        to_view_record(mask_record_fields(_project_record(record, view), allowed_fields))
        for record in data_source.list_records(view.table_name)
        if _can_actor_view_record(actor, record)
    ]
    return ViewResponse(
        view_key=view.view_key,
        records=records,
        trace_id=f"view:{view.view_key}",
    )


def to_view_record(record: dict[str, Any]) -> ViewRecord:
    return ViewRecord(id=record["id"], fields=record.get("fields", {}))


def _project_record(
    record: dict[str, Any],
    view: ViewDefinition,
) -> dict[str, Any]:
    fields = record.get("fields", {})
    return {
        "id": record["id"],
        "fields": {
            field_name: fields[field_name]
            for field_name in view.fields
            if field_name in fields
        },
    }


def _allowed_fields_for_view(
    view: ViewDefinition,
    actor: Actor | None,
) -> set[str]:
    view_allowed_fields = set(view.fields) - set(view.sensitive_fields)
    if actor is None:
        return view_allowed_fields
    return view_allowed_fields & allowed_fields_for_actor(actor, set(view.fields))


def _can_actor_view_record(actor: Actor | None, record: dict[str, Any]) -> bool:
    if actor is None:
        return True
    return can_view_customer_record(actor, _record_customer_id(record))


def _record_customer_id(record: dict[str, Any]) -> Any:
    fields = record.get("fields", {})
    for field_name in ("customer_id", "assigned_customer_id"):
        if fields.get(field_name) is not None:
            return fields[field_name]
    return None


def _row_to_record(row: Any) -> dict[str, Any]:
    values = dict(row._mapping)
    record_id = values.pop("id")
    return {
        "id": str(record_id),
        "fields": values,
    }
