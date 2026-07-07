from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select

from app.models import metadata
from app.schemas.views import ViewRecord, ViewResponse
from app.services.permissions import (
    Actor,
    GLOBAL_RECORD_ROLES,
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
    field_aliases: dict[str, str] | None = None
    sensitive_fields: frozenset[str] = frozenset()
    sensitive_fields_visible_to_global_roles: bool = False
    default_limit: int | None = None
    max_limit: int | None = None


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
            "message_id",
            "telegram_update_id",
            "telegram_chat_id",
            "telegram_message_id",
            "telegram_user_id",
            "customer_id",
            "binding_status",
            "message_type",
            "text_preview",
            "processing_status",
            "outbox_status",
            "last_error_code",
            "intent_status",
            "intent_type",
            "agent_status",
            "draft_count",
            "agent_last_error_code",
            "received_at",
            "processed_at",
            "trace_id",
        ),
        field_aliases={"message_id": "id", "text_preview": "normalized_text"},
        default_limit=100,
        max_limit=200,
    ),
    "ai_draft_queue": ViewDefinition(
        view_key="ai_draft_queue",
        table_name="service_drafts",
        fields=("status", "intent_type", "customer_id", "trace_id"),
        field_aliases={"intent_type": "draft_type"},
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
            "last_risk_signal_at",
            "last_risk_source",
            "trace_id",
        ),
        sensitive_fields=frozenset({"external_account_id"}),
        sensitive_fields_visible_to_global_roles=True,
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
    "telegram_bindings": ViewDefinition(
        view_key="telegram_bindings",
        table_name="telegram_customer_bindings",
        fields=(
            "binding_id",
            "customer_id",
            "binding_scope",
            "telegram_chat_id",
            "telegram_user_id",
            "status",
            "label",
            "created_by",
            "created_at",
            "updated_at",
        ),
        field_aliases={"binding_id": "id"},
        sensitive_fields=frozenset({"telegram_chat_id", "telegram_user_id"}),
        sensitive_fields_visible_to_global_roles=True,
    ),
    "telegram_send_requests": ViewDefinition(
        view_key="telegram_send_requests",
        table_name="telegram_send_requests",
        fields=(
            "request_id",
            "target_chat_id",
            "status",
            "requested_by_actor_id",
            "confirmed_by_actor_id",
            "telegram_response_summary",
            "last_error_code",
            "sent_at",
            "trace_id",
        ),
        field_aliases={"request_id": "id"},
        sensitive_fields=frozenset({"target_chat_id", "telegram_response_summary"}),
        sensitive_fields_visible_to_global_roles=True,
    ),
    "telegram_intent_queue": ViewDefinition(
        view_key="telegram_intent_queue",
        table_name="messages",
        fields=(
            "message_id",
            "customer_id",
            "binding_status",
            "intent_status",
            "intent_type",
            "processing_status",
            "received_at",
            "trace_id",
        ),
        field_aliases={"message_id": "id"},
    ),
    "service_drafts": ViewDefinition(
        view_key="service_drafts",
        table_name="service_drafts",
        fields=(
            "draft_id",
            "draft_type",
            "status",
            "customer_id",
            "source_message_id",
            "created_by_type",
            "created_by_id",
            "confidence",
            "missing_fields",
            "risk_flags",
            "payload_summary",
            "trace_id",
            "created_at",
        ),
        field_aliases={"draft_id": "id"},
    ),
    "agent_review_queue": ViewDefinition(
        view_key="agent_review_queue",
        table_name="agent_review_queue",
        fields=(
            "review_id",
            "review_source",
            "customer_id",
            "message_id",
            "draft_id",
            "agent_run_id",
            "reason",
            "risk_flags",
            "last_error_code",
            "trace_id",
            "created_at",
        ),
        field_aliases={"review_id": "id"},
        default_limit=100,
        max_limit=200,
    ),
    "pending_confirmation": ViewDefinition(
        view_key="pending_confirmation",
        table_name="service_drafts",
        fields=(
            "draft_id",
            "draft_type",
            "customer_id",
            "source_message_id",
            "confidence",
            "risk_flags",
            "confirm_action",
            "trace_id",
            "created_at",
        ),
        field_aliases={"draft_id": "id"},
        default_limit=100,
        max_limit=200,
    ),
    "customer_reply_send_requests": ViewDefinition(
        view_key="customer_reply_send_requests",
        table_name="telegram_send_requests",
        fields=(
            "request_id",
            "source_service_draft_id",
            "status",
            "requested_by_actor_id",
            "confirmed_by_actor_id",
            "telegram_response_summary",
            "last_error_code",
            "sent_at",
            "trace_id",
        ),
        field_aliases={"request_id": "id"},
        sensitive_fields=frozenset({"telegram_response_summary"}),
        sensitive_fields_visible_to_global_roles=True,
        default_limit=100,
        max_limit=200,
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
    limit: int | None = None,
) -> ViewResponse:
    view = get_view_definition(view_key)
    data_source = data_source or EmptyBitableViewDataSource()
    allowed_fields = allowed_fields or _allowed_fields_for_view(view, actor)
    raw_records = [
        record
        for record in _collect_view_records(view, data_source)
        if _can_actor_view_record(actor, record)
    ]
    raw_records = _apply_view_order_and_limit(raw_records, view, limit)
    records = [
        to_view_record(mask_record_fields(_project_record(record, view), allowed_fields))
        for record in raw_records
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
    aliases = view.field_aliases or {}
    return {
        "id": record["id"],
        "fields": {
            field_name: _project_field_value(
                record,
                fields,
                _source_field_name(field_name, fields, aliases),
            )
            for field_name in view.fields
            if _source_field_name(field_name, fields, aliases) in fields
            or _source_field_name(field_name, fields, aliases) == "id"
        },
    }


def _allowed_fields_for_view(
    view: ViewDefinition,
    actor: Actor | None,
) -> set[str]:
    view_allowed_fields = set(view.fields)
    if not _can_actor_view_sensitive_fields(view, actor):
        view_allowed_fields = view_allowed_fields - set(view.sensitive_fields)
    if actor is None:
        return view_allowed_fields
    return view_allowed_fields & allowed_fields_for_actor(actor, set(view.fields))


def _can_actor_view_sensitive_fields(
    view: ViewDefinition,
    actor: Actor | None,
) -> bool:
    return (
        view.sensitive_fields_visible_to_global_roles
        and actor is not None
        and actor.role in GLOBAL_RECORD_ROLES
    )


def _source_field_name(
    field_name: str,
    fields: dict[str, Any],
    aliases: dict[str, str],
) -> str:
    source_field = aliases.get(field_name, field_name)
    if source_field == "id":
        return source_field
    if source_field in fields:
        return source_field
    return field_name


def _project_field_value(
    record: dict[str, Any],
    fields: dict[str, Any],
    source_field: str,
) -> Any:
    if source_field == "id":
        return record["id"]
    return fields[source_field]


def _apply_view_order_and_limit(
    records: list[dict[str, Any]],
    view: ViewDefinition,
    limit: int | None,
) -> list[dict[str, Any]]:
    if view.view_key == "telegram_inbox":
        records = sorted(records, key=_telegram_inbox_sort_key)
    if view.view_key in {"agent_review_queue", "pending_confirmation"}:
        records = sorted(records, key=_created_at_sort_key)
    effective_limit = _effective_limit(view, limit)
    if effective_limit is None:
        return records
    return records[:effective_limit]


def _effective_limit(view: ViewDefinition, limit: int | None) -> int | None:
    effective = view.default_limit if limit is None else limit
    if effective is None:
        return None
    if view.max_limit is not None:
        return min(effective, view.max_limit)
    return effective


def _telegram_inbox_sort_key(record: dict[str, Any]) -> tuple[float, str]:
    fields = record.get("fields", {})
    return (-_timestamp(fields.get("received_at")), str(record["id"]))


def _created_at_sort_key(record: dict[str, Any]) -> tuple[float, str]:
    fields = record.get("fields", {})
    return (-_timestamp(fields.get("created_at")), str(record["id"]))


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


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


def _collect_view_records(
    view: ViewDefinition,
    data_source: BitableViewDataSource,
) -> list[dict[str, Any]]:
    if view.view_key == "telegram_inbox":
        return _telegram_inbox_records(data_source)
    if view.view_key == "account_inventory":
        return _account_inventory_records(data_source)
    if view.view_key == "pending_confirmation":
        return _pending_confirmation_records(data_source)
    if view.view_key == "customer_reply_send_requests":
        return _customer_reply_send_request_records(data_source)
    if view.view_key == "agent_review_queue":
        return _agent_review_queue_records(data_source)
    return data_source.list_records(view.table_name)


def _telegram_inbox_records(
    data_source: BitableViewDataSource,
) -> list[dict[str, Any]]:
    drafts_by_message = _count_records_by_field(
        data_source.list_records("service_drafts"),
        "source_message_id",
    )
    latest_run_by_message = _latest_record_by_field(
        data_source.list_records("agent_runs"),
        "message_id",
        "started_at",
    )
    records: list[dict[str, Any]] = []
    for message in data_source.list_records("messages"):
        message_id = _record_id(message)
        extra_fields: dict[str, Any] = {}
        draft_count = drafts_by_message.get(message_id, 0)
        if draft_count:
            extra_fields["draft_count"] = draft_count
        latest_run = latest_run_by_message.get(message_id)
        if latest_run is not None:
            run_fields = latest_run.get("fields", {})
            extra_fields["agent_status"] = run_fields.get("status")
            if run_fields.get("error_code") is not None:
                extra_fields["agent_last_error_code"] = run_fields["error_code"]
        records.append(_copy_record(message, extra_fields))
    return records


def _account_inventory_records(
    data_source: BitableViewDataSource,
) -> list[dict[str, Any]]:
    latest_event_by_inventory = _latest_record_by_field(
        data_source.list_records("account_status_events"),
        "account_inventory_id",
        "created_at",
    )
    records: list[dict[str, Any]] = []
    for account in data_source.list_records("account_inventory"):
        latest_event = latest_event_by_inventory.get(_record_id(account))
        extra_fields: dict[str, Any] = {}
        if latest_event is not None:
            event_fields = latest_event.get("fields", {})
            if event_fields.get("created_at") is not None:
                extra_fields["last_risk_signal_at"] = event_fields["created_at"]
            if event_fields.get("source_entity_type") is not None:
                extra_fields["last_risk_source"] = event_fields["source_entity_type"]
            elif event_fields.get("event_type") is not None:
                extra_fields["last_risk_source"] = event_fields["event_type"]
        records.append(_copy_record(account, extra_fields))
    return records


def _pending_confirmation_records(
    data_source: BitableViewDataSource,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for draft in data_source.list_records("service_drafts"):
        fields = draft.get("fields", {})
        if fields.get("status") != "pending_confirmation":
            continue
        if _has_values(fields.get("missing_fields")):
            continue
        if fields.get("customer_id") is None:
            continue
        records.append(
            _copy_record(
                draft,
                {"confirm_action": _confirm_action_for_draft(fields.get("draft_type"))},
            )
        )
    return records


def _customer_reply_send_request_records(
    data_source: BitableViewDataSource,
) -> list[dict[str, Any]]:
    draft_by_id = _index_by_record_id(data_source.list_records("service_drafts"))
    records: list[dict[str, Any]] = []
    for send_request in data_source.list_records("telegram_send_requests"):
        fields = send_request.get("fields", {})
        source_draft_id = _normalize_key(fields.get("source_service_draft_id"))
        if (
            fields.get("send_purpose") != "customer_reply_rehearsal"
            and source_draft_id is None
        ):
            continue
        extra_fields: dict[str, Any] = {}
        source_draft = draft_by_id.get(source_draft_id)
        if source_draft is not None:
            draft_fields = source_draft.get("fields", {})
            if draft_fields.get("customer_id") is not None:
                extra_fields["customer_id"] = draft_fields["customer_id"]
        records.append(_copy_record(send_request, extra_fields))
    return records


def _agent_review_queue_records(
    data_source: BitableViewDataSource,
) -> list[dict[str, Any]]:
    messages = data_source.list_records("messages")
    message_by_id = _index_by_record_id(messages)
    records: list[dict[str, Any]] = []
    records.extend(_message_review_records(messages))
    records.extend(_service_draft_review_records(data_source.list_records("service_drafts")))
    records.extend(
        _agent_run_review_records(
            data_source.list_records("agent_runs"),
            message_by_id,
        )
    )
    records.extend(
        _account_status_review_records(data_source.list_records("account_status_events"))
    )
    return records


def _message_review_records(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for message in messages:
        fields = message.get("fields", {})
        if fields.get("intent_status") not in {"manual_review", "agent_failed"}:
            continue
        message_id = _record_id(message)
        review_fields = {
            "review_source": "message",
            "customer_id": fields.get("customer_id"),
            "message_id": message_id,
            "reason": fields.get("last_error_code") or fields.get("intent_status"),
            "last_error_code": fields.get("last_error_code"),
            "trace_id": fields.get("trace_id"),
            "created_at": fields.get("received_at"),
        }
        if fields.get("risk_flags") is not None:
            review_fields["risk_flags"] = fields["risk_flags"]
        records.append(
            {
                "id": f"message:{message_id}",
                "fields": review_fields,
            }
        )
    return records


def _service_draft_review_records(
    drafts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for draft in drafts:
        fields = draft.get("fields", {})
        if fields.get("status") != "manual_review":
            continue
        draft_id = _record_id(draft)
        records.append(
            {
                "id": f"draft:{draft_id}",
                "fields": {
                    "review_source": "service_draft",
                    "customer_id": fields.get("customer_id"),
                    "message_id": fields.get("source_message_id"),
                    "draft_id": draft_id,
                    "reason": fields.get("review_reason") or "manual_review",
                    "risk_flags": fields.get("risk_flags"),
                    "trace_id": fields.get("trace_id"),
                    "created_at": fields.get("created_at"),
                },
            }
        )
    return records


def _agent_run_review_records(
    agent_runs: list[dict[str, Any]],
    message_by_id: dict[str | None, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for run in agent_runs:
        fields = run.get("fields", {})
        if fields.get("status") != "failed":
            continue
        run_id = _record_id(run)
        message_id = _normalize_key(fields.get("message_id"))
        message = message_by_id.get(message_id)
        message_fields = message.get("fields", {}) if message is not None else {}
        records.append(
            {
                "id": f"agent_run:{run_id}",
                "fields": {
                    "review_source": "agent_run",
                    "customer_id": message_fields.get("customer_id"),
                    "message_id": message_id,
                    "agent_run_id": run_id,
                    "reason": fields.get("error_message_redacted")
                    or fields.get("error_code")
                    or "failed",
                    "last_error_code": fields.get("error_code"),
                    "trace_id": fields.get("trace_id"),
                    "created_at": fields.get("started_at") or fields.get("created_at"),
                },
            }
        )
    return records


def _account_status_review_records(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for event in events:
        fields = event.get("fields", {})
        if not _is_account_status_review_event(fields):
            continue
        event_id = _record_id(event)
        records.append(
            {
                "id": f"account_status_event:{event_id}",
                "fields": {
                    "review_source": "account_status_event",
                    "customer_id": fields.get("customer_id"),
                    "reason": fields.get("reason") or fields.get("event_type"),
                    "risk_flags": fields.get("risk_flags"),
                    "trace_id": fields.get("trace_id"),
                    "created_at": fields.get("created_at"),
                },
            }
        )
    return records


def _is_account_status_review_event(fields: dict[str, Any]) -> bool:
    return (
        fields.get("requires_manual_review") is True
        or fields.get("event_type") in {"manual_review", "account_status_review"}
        or fields.get("after_status") == "manual_review"
    )


def _confirm_action_for_draft(draft_type: Any) -> str:
    if draft_type == "customer_reply":
        return "create_customer_reply_send_request"
    if draft_type == "account_assignment":
        return "confirm_account_assignment_draft"
    return "create_noop_service_evidence"


def _index_by_record_id(
    records: list[dict[str, Any]],
) -> dict[str | None, dict[str, Any]]:
    return {_record_id(record): record for record in records}


def _count_records_by_field(
    records: list[dict[str, Any]],
    field_name: str,
) -> dict[str | None, int]:
    counts: dict[str | None, int] = {}
    for record in records:
        key = _normalize_key(record.get("fields", {}).get(field_name))
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _latest_record_by_field(
    records: list[dict[str, Any]],
    field_name: str,
    timestamp_field: str,
) -> dict[str | None, dict[str, Any]]:
    latest: dict[str | None, dict[str, Any]] = {}
    for record in records:
        key = _normalize_key(record.get("fields", {}).get(field_name))
        if key is None:
            continue
        current = latest.get(key)
        if current is None or _timestamp(
            record.get("fields", {}).get(timestamp_field)
        ) >= _timestamp(current.get("fields", {}).get(timestamp_field)):
            latest[key] = record
    return latest


def _copy_record(
    record: dict[str, Any],
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fields = dict(record.get("fields", {}))
    if extra_fields:
        fields.update(extra_fields)
    return {"id": str(record["id"]), "fields": fields}


def _record_id(record: dict[str, Any]) -> str:
    return str(record["id"])


def _normalize_key(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _has_values(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value) > 0
    return True
