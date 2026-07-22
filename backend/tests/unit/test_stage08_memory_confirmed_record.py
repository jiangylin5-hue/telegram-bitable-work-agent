from datetime import UTC, datetime
from uuid import uuid4

from app.models.stage06_runtime import RecordChangeDraft
from app.runtime.stage08_memory_contracts import MemoryScopeProjection
from app.services.permissions import Actor
from app.services.stage06_digital_employees import confirm_record_change_draft
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_memory import (
    enqueue_confirmed_record_memory_event,
    materialize_stage08_memory_outbox_event,
    read_memory_projection,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Memory", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Decisions", key="decisions")
    for key in ("customer", "project", "subject", "decision", "status", "hidden"):
        create_field(uow, table.id, name=key.title(), key=key, field_type="text")
    customer = create_record(
        uow, table.id, values={"customer": "Acme", "subject": "customer"}, actor=owner
    )
    project = create_record(
        uow, table.id, values={"customer": "Acme", "subject": "project"}, actor=owner
    )
    record = create_record(
        uow,
        table.id,
        values={
            "customer": str(customer.id),
            "project": str(project.id),
            "subject": "Renewal",
            "decision": "approved",
            "status": "open",
            "hidden": "never-materialized",
        },
        actor=owner,
    )
    table.settings = {
        "memory_policy": {
            "version": 1,
            "rules": [
                {
                    "memory_type": "decision",
                    "identity_field_keys": ["customer", "subject"],
                    "payload_field_keys": ["decision", "status"],
                    "scope_field_keys": {
                        "customer_record_id": "customer",
                        "project_record_id": "project",
                    },
                    "valid_for_days": 90,
                }
            ],
        }
    }
    draft = RecordChangeDraft(
        id=uuid4(),
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=record.id,
        draft_type="update_record",
        proposed_values={"decision": "approved"},
        before_values={"decision": "pending"},
        created_by_type="digital_employee",
        created_by_id="employee-1",
        status="confirmed",
        confirmation_policy={},
        trace_id="stage08:test",
        expected_version=record.version,
    )
    uow.add_record_change_draft(draft)
    return uow, owner, workspace, base, table, record, draft


def test_confirmed_record_enqueues_six_reference_only_keys_then_materializes_once(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, workspace, base, table, record, draft = _fixture()

    event = enqueue_confirmed_record_memory_event(
        uow, draft, record, confirmation_actor=owner, now=NOW
    )

    assert event is not None
    assert event.event_type == "stage08.memory.confirmed_record.v1"
    assert event.payload == {
        "workspace_id": str(workspace.id),
        "table_id": str(table.id),
        "record_id": str(record.id),
        "record_version": record.version,
        "policy_version": 1,
        "rule_index": 0,
    }
    assert set(event.payload) == {
        "workspace_id", "table_id", "record_id", "record_version", "policy_version", "rule_index"
    }
    assert "Renewal" not in str(event.payload)

    item = materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW)

    assert item is not None
    assert item.payload == {"decision": "approved", "status": "open"}
    assert item.valid_until == datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    assert event.status == "processed"
    assert MemoryScopeProjection.model_validate(item.scope).identity_token is not None
    assert "identity_token" not in str(event.payload)
    assert materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW) is None
    assert len(uow.memory_items) == 1


def test_unconfirmed_or_invalid_policy_events_fail_closed_without_memory(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, table, record, draft = _fixture()
    draft.status = "pending_confirmation"

    assert enqueue_confirmed_record_memory_event(
        uow, draft, record, confirmation_actor=owner, now=NOW
    ) is None
    assert uow.outbox_events == []

    draft.status = "confirmed"
    table.settings = {"memory_policy": {"version": 2, "rules": []}}
    assert enqueue_confirmed_record_memory_event(
        uow, draft, record, confirmation_actor=owner, now=NOW
    ) is None
    assert uow.outbox_events == []


def test_identity_field_keys_distinguish_same_scope_facts(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, table, record, draft = _fixture()
    first_event = enqueue_confirmed_record_memory_event(
        uow, draft, record, confirmation_actor=owner, now=NOW
    )
    assert first_event is not None
    first = materialize_stage08_memory_outbox_event(uow, first_event.id, actor=owner, now=NOW)
    assert first is not None

    record.record_values["subject"] = "Different renewal"
    record.version += 1
    next_draft = RecordChangeDraft(
        id=uuid4(), workspace_id=draft.workspace_id, base_id=draft.base_id,
        table_id=table.id, record_id=record.id, draft_type="update_record",
        proposed_values={"subject": "Different renewal"}, before_values={},
        created_by_type="digital_employee", created_by_id="employee-1", status="confirmed",
        confirmation_policy={}, trace_id="stage08:test:next", expected_version=record.version,
    )
    uow.add_record_change_draft(next_draft)
    next_event = enqueue_confirmed_record_memory_event(
        uow, next_draft, record, confirmation_actor=owner, now=NOW
    )
    assert next_event is not None
    second = materialize_stage08_memory_outbox_event(uow, next_event.id, actor=owner, now=NOW)

    assert second is not None
    assert first.status == "active"
    assert second.status == "active"
    assert len(uow.memory_items) == 2


def test_confirmation_hook_enqueues_only_after_confirmation_audit(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, _table, record, draft = _fixture()
    draft.status = "pending_confirmation"
    draft.expected_version = record.version
    audit_count = len(uow.audit_events)

    confirmed = confirm_record_change_draft(uow, draft.id, actor=owner)

    assert confirmed.status == "confirmed"
    assert len(uow.audit_events) > audit_count
    assert uow.audit_events[-1].event_type == "stage06.record_change_draft_confirmed"
    assert len(uow.outbox_events) == 1
    assert uow.outbox_events[0].payload["record_version"] == record.version


def test_materializer_never_returns_server_identity_token(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, _table, record, draft = _fixture()
    event = enqueue_confirmed_record_memory_event(
        uow, draft, record, confirmation_actor=owner, now=NOW
    )
    assert event is not None
    item = materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW)
    assert item is not None

    safe_projection = read_memory_projection(uow, item.id, actor=owner, now=NOW)

    assert safe_projection is not None
    assert "identity_token" not in safe_projection["scope"]


def test_processed_event_replay_fails_closed_after_membership_revocation(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, workspace, _base, _table, record, draft = _fixture()
    event = enqueue_confirmed_record_memory_event(
        uow, draft, record, confirmation_actor=owner, now=NOW
    )
    assert event is not None
    assert materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW)
    next(member for member in uow.workspace_members if member.workspace_id == workspace.id).status = "disabled"

    assert materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW) is None


def test_two_valid_policy_rules_fail_closed_without_an_event(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, table, record, draft = _fixture()
    table.settings["memory_policy"]["rules"].append(
        dict(table.settings["memory_policy"]["rules"][0])
    )

    assert enqueue_confirmed_record_memory_event(
        uow, draft, record, confirmation_actor=owner, now=NOW
    ) is None
    assert uow.outbox_events == []


def test_create_draft_confirmation_hook_enqueues_one_reference_event(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, workspace, base, table, _record, _draft = _fixture()
    customer, project = uow.records[:2]
    draft = RecordChangeDraft(
        id=uuid4(), workspace_id=workspace.id, base_id=base.id, table_id=table.id,
        record_id=None, draft_type="create_record",
        proposed_values={"customer": str(customer.id), "project": str(project.id), "subject": "New", "decision": "approved", "status": "open", "hidden": "x"},
        before_values=None, created_by_type="digital_employee", created_by_id="employee-1",
        status="pending_confirmation", confirmation_policy={}, trace_id="stage08:create", expected_version=1,
    )
    uow.add_record_change_draft(draft)

    confirmed = confirm_record_change_draft(uow, draft.id, actor=owner)

    assert confirmed.record_id is not None
    assert len(uow.outbox_events) == 1
    assert uow.outbox_events[0].payload["record_id"] == str(confirmed.record_id)
    item = materialize_stage08_memory_outbox_event(
        uow, uow.outbox_events[0].id, actor=owner, now=NOW
    )
    assert item is not None
    assert item.payload == {"decision": "approved", "status": "open"}
    assert uow.outbox_events[0].status == "processed"


def test_rejected_or_failed_draft_never_enqueues(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, _table, record, draft = _fixture()
    for status in ("rejected", "failed"):
        draft.status = status
        assert enqueue_confirmed_record_memory_event(
            uow, draft, record, confirmation_actor=owner, now=NOW
        ) is None
    assert uow.outbox_events == []


def test_unconfigured_removed_or_unreadable_policy_fields_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, table, record, draft = _fixture()
    table.settings = {}
    assert enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW) is None
    table.settings = _fixture()[4].settings
    next(field for field in uow.fields if field.key == "decision").status = "deleted"
    assert enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW) is None
    next(field for field in uow.fields if field.key == "decision").status = "active"
    next(field for field in uow.fields if field.key == "decision").permission_policy = {"owner": "hidden"}
    assert enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW) is None


def test_stale_invalid_scope_inactive_resource_and_missing_hmac_never_process(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, base, table, record, draft = _fixture()
    event = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)
    assert event is not None
    record.version += 1
    assert materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW) is None
    assert event.status == "pending"

    uow, owner, _workspace, _base, _table, record, draft = _fixture()
    record.record_values["customer"] = "not-a-uuid"
    assert enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW) is None
    uow, owner, _workspace, base, _table, record, draft = _fixture()
    base.status = "inactive"
    assert enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW) is None

    uow, owner, _workspace, _base, _table, record, draft = _fixture()
    event = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)
    assert event is not None
    monkeypatch.delenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY")
    before_values, before_version = dict(record.values), record.version
    assert materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW) is None
    assert event.status == "pending"
    assert record.values == before_values
    assert record.version == before_version


def test_pending_event_actor_revocation_fails_closed_without_terminal_mutation(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, workspace, _base, _table, record, draft = _fixture()
    event = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)
    assert event is not None
    next(member for member in uow.workspace_members if member.workspace_id == workspace.id).status = "disabled"

    assert materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW) is None
    assert event.status == "pending"
    assert uow.memory_items == []


def test_field_visibility_drift_after_enqueue_fails_closed_and_leaves_pending(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, _table, record, draft = _fixture()
    event = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)
    assert event is not None
    next(field for field in uow.fields if field.key == "decision").permission_policy = {"owner": "hidden"}

    assert materialize_stage08_memory_outbox_event(uow, event.id, actor=owner, now=NOW) is None
    assert event.status == "pending"
    assert uow.memory_items == []


def test_same_identity_unchanged_payload_supersedes_to_next_source_version(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, table, record, draft = _fixture()
    first_event = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)
    assert first_event is not None
    first = materialize_stage08_memory_outbox_event(uow, first_event.id, actor=owner, now=NOW)
    assert first is not None
    record.version += 1
    next_draft = RecordChangeDraft(
        id=uuid4(), workspace_id=draft.workspace_id, base_id=draft.base_id,
        table_id=table.id, record_id=record.id, draft_type="update_record",
        proposed_values={"status": "open"}, before_values={"status": "open"},
        created_by_type="digital_employee", created_by_id="employee-1", status="confirmed",
        confirmation_policy={}, trace_id="stage08:same-identity", expected_version=record.version,
    )
    second_event = enqueue_confirmed_record_memory_event(
        uow, next_draft, record, confirmation_actor=owner, now=NOW
    )
    assert second_event is not None
    second = materialize_stage08_memory_outbox_event(uow, second_event.id, actor=owner, now=NOW)

    assert second is not None
    assert first.status == "superseded"
    assert second.status == "active"
    assert second.version == 2
    assert second.supersedes_id == first.id


def test_repeated_enqueue_for_same_six_references_reuses_one_outbox_event(monkeypatch) -> None:
    monkeypatch.setenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY", "test-only-identity-key")
    uow, owner, _workspace, _base, _table, record, draft = _fixture()
    first = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)
    second = enqueue_confirmed_record_memory_event(uow, draft, record, confirmation_actor=owner, now=NOW)

    assert first is not None
    assert second is first
    assert len(uow.outbox_events) == 1
