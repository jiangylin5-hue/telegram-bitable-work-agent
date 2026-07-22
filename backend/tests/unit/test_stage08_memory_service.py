from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from uuid import UUID, uuid4

import pytest

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_memory import (
    Stage08MemoryExtractionCandidate,
    Stage08MemoryItem,
)
from app.runtime.stage08_memory_contracts import (
    GroupMemoryCandidateProjection,
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage08_group_memory_source import (
    TrustedGroupMessageInput,
    resolve_authorized_group_message_source,
)
from app.services.stage08_memory import (
    CandidateRevocationResult,
    create_group_memory_candidate,
    list_memory_projections,
    materialize_memory_from_projection,
    read_memory_projection,
    resolve_group_candidate,
    revoke_memory_candidate,
)


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Memory", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Customer", key="customer", field_type="text")
    create_field(uow, table.id, name="Decision", key="decision", field_type="text")
    record = create_record(
        uow,
        table.id,
        values={"customer": "Acme", "decision": "approved"},
        actor=owner,
    )
    return uow, owner, workspace, base, table, record


def _projection(
    workspace_id: UUID,
    base_id: UUID,
    table_id: UUID,
    record_id: UUID,
    record_version: int,
    *,
    decision: str = "approved",
    valid_until: datetime | None = None,
) -> MemoryMaterializationProjection:
    return MemoryMaterializationProjection(
        memory_type="decision",
        scope=MemoryScopeProjection(
            workspace_id=workspace_id,
            base_id=base_id,
            table_id=table_id,
        ),
        payload={"customer": "Acme", "decision": decision},
        source_refs=(
            MemorySourceRef(
                source_kind="platform_record",
                source_id=record_id,
                source_version=record_version,
                field_keys=("customer", "decision"),
            ),
        ),
        valid_until=valid_until,
    )


def test_same_source_fingerprint_returns_existing_item_unchanged() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    projection = _projection(workspace.id, base.id, table.id, record.id, record.version)

    created = materialize_memory_from_projection(uow, projection, actor=owner, now=NOW)
    reused = materialize_memory_from_projection(uow, projection, actor=owner, now=NOW)

    assert reused is created
    assert len(uow.memory_items) == 1


def test_equal_payload_with_same_identity_supersedes_existing_active_item() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    first = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW,
    )
    record.version += 1
    second = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW + timedelta(seconds=1),
    )

    assert first.status == "superseded"
    assert second.status == "active"
    assert second.supersedes_id == first.id
    assert second.version == 2


def test_conflicting_fact_creates_new_conflicted_version_without_overwriting_active_item() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    active = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW,
    )
    record.record_values["decision"] = "rejected"
    record.version += 1
    conflict = materialize_memory_from_projection(
        uow,
        _projection(
            workspace.id,
            base.id,
            table.id,
            record.id,
            record.version,
            decision="rejected",
        ),
        actor=owner,
        now=NOW + timedelta(seconds=1),
    )

    assert active.status == "active"
    assert conflict.status == "conflicted"
    assert conflict.supersedes_id is None
    assert conflict.version == 2


def test_materialization_denies_inactive_membership_and_scope_chain_mismatch() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    uow.workspace_members[0].status = "disabled"
    projection = _projection(workspace.id, base.id, table.id, record.id, record.version)

    with pytest.raises(PlatformValidationError, match="actor_not_workspace_member"):
        materialize_memory_from_projection(uow, projection, actor=owner, now=NOW)

    uow.workspace_members[0].status = "active"
    foreign_workspace = create_workspace(uow, name="Foreign", owner_user_id="owner-1")
    with pytest.raises(PlatformValidationError, match="memory_scope_invalid"):
        materialize_memory_from_projection(
            uow,
            _projection(foreign_workspace.id, base.id, table.id, record.id, record.version),
            actor=owner,
            now=NOW,
        )

    foreign_base = create_base(uow, foreign_workspace.id, name="Foreign CRM")
    foreign_table = create_table(uow, foreign_base.id, name="Foreign", key="foreign")
    create_field(uow, foreign_table.id, name="Customer", key="customer", field_type="text")
    foreign_record = create_record(
        uow,
        foreign_table.id,
        values={"customer": "Elsewhere"},
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    projection = _projection(workspace.id, base.id, table.id, record.id, record.version)
    projection.scope.customer_record_id = foreign_record.id
    with pytest.raises(PlatformValidationError, match="memory_scope_invalid"):
        materialize_memory_from_projection(uow, projection, actor=owner, now=NOW)


def test_read_transitions_expired_or_stale_source_to_terminal_and_refuses_payload() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    expiring = materialize_memory_from_projection(
        uow,
        _projection(
            workspace.id,
            base.id,
            table.id,
            record.id,
            record.version,
            valid_until=NOW - timedelta(seconds=1),
        ),
        actor=owner,
        now=NOW - timedelta(seconds=2),
    )

    assert read_memory_projection(uow, expiring.id, actor=owner, now=NOW) is None
    assert expiring.status == "expired"

    record.version += 1
    stale = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW,
    )
    record.version += 1

    assert read_memory_projection(uow, stale.id, actor=owner, now=NOW) is None
    assert stale.status == "deleted"


def test_read_only_projection_preserves_lifecycle_and_audit_on_ttl_or_source_drift() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    expiring = materialize_memory_from_projection(
        uow,
        _projection(
            workspace.id,
            base.id,
            table.id,
            record.id,
            record.version,
            valid_until=NOW - timedelta(seconds=1),
        ),
        actor=owner,
        now=NOW - timedelta(seconds=2),
    )
    audit_count = len(uow.audit_events)
    assert read_memory_projection(
        uow,
        expiring.id,
        actor=owner,
        now=NOW,
        lifecycle_mode="read_only",
    ) is None
    assert expiring.status == "active"
    assert len(uow.audit_events) == audit_count

    expiring.valid_until = None
    record.version += 1
    assert read_memory_projection(
        uow,
        expiring.id,
        actor=owner,
        now=NOW,
        lifecycle_mode="read_only",
    ) is None
    assert expiring.status == "active"
    assert len(uow.audit_events) == audit_count


def test_read_denies_hidden_source_field_and_safe_projection_and_audit_have_no_raw_content() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    item = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW,
    )
    response = read_memory_projection(uow, item.id, actor=owner, now=NOW)

    assert response == {
        "id": item.id,
        "memory_type": "decision",
        "version": 1,
        "scope": {"workspace_id": str(workspace.id), "base_id": str(base.id), "table_id": str(table.id)},
        "payload": {"customer": "Acme", "decision": "approved"},
        "valid_until": None,
    }
    assert "source_refs" not in response
    assert "approved" not in str(uow.audit_events)

    field = next(field for field in uow.fields if field.key == "decision")
    field.permission_policy = {"owner": "hidden"}
    assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
    assert item.status == "deleted"


def test_unsupported_draft_or_group_source_never_dereferences_or_materializes() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    projection = _projection(workspace.id, base.id, table.id, record.id, record.version)
    projection.source_refs = (
        MemorySourceRef(
            source_kind="record_change_draft",
            source_id=uuid4(),
            source_version=1,
            field_keys=("customer", "decision"),
        ),
    )
    with pytest.raises(PlatformValidationError, match="memory_source_not_supported"):
        materialize_memory_from_projection(uow, projection, actor=owner, now=NOW)

    projection.source_refs = (
        MemorySourceRef(
            source_kind="platform_record",
            source_id=record.id,
            source_version=record.version,
            field_keys=("customer", "decision"),
        ),
    )
    projection.scope.group_chat_ref = "safe-contract-but-unreadable"
    with pytest.raises(PlatformValidationError, match="memory_group_source_not_supported"):
        materialize_memory_from_projection(uow, projection, actor=owner, now=NOW)


def test_materialization_rejects_payload_that_does_not_match_current_readable_source() -> None:
    uow, owner, workspace, base, table, record = _fixture()

    with pytest.raises(PlatformValidationError, match="memory_source_invalid"):
        materialize_memory_from_projection(
            uow,
            _projection(
                workspace.id,
                base.id,
                table.id,
                record.id,
                record.version,
                decision="not-current",
            ),
            actor=owner,
            now=NOW,
        )


@pytest.mark.parametrize(
    "resource",
    ("workspace", "base", "table", "field", "source_record"),
)
def test_materialization_rejects_inactive_validity_chain(resource: str) -> None:
    uow, owner, workspace, base, table, record = _fixture()
    if resource == "workspace":
        workspace.status = "inactive"
    elif resource == "base":
        base.status = "inactive"
    elif resource == "table":
        table.status = "inactive"
    elif resource == "field":
        next(field for field in uow.fields if field.key == "decision").status = "inactive"
    else:
        record.record_status = "deleted"

    with pytest.raises(PlatformValidationError, match="memory_(scope|source)_invalid"):
        materialize_memory_from_projection(
            uow,
            _projection(workspace.id, base.id, table.id, record.id, record.version),
            actor=owner,
            now=NOW,
        )


@pytest.mark.parametrize("scope_field", ("customer_record_id", "project_record_id"))
def test_read_deletes_item_when_relation_scope_record_becomes_inactive(scope_field: str) -> None:
    uow, owner, workspace, base, table, record = _fixture()
    relation = create_record(
        uow,
        table.id,
        values={"customer": "Acme relation", "decision": "approved"},
        actor=owner,
    )
    projection = _projection(workspace.id, base.id, table.id, record.id, record.version)
    setattr(projection.scope, scope_field, relation.id)
    item = materialize_memory_from_projection(uow, projection, actor=owner, now=NOW)
    relation.record_status = "inactive"

    assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
    assert item.status == "deleted"


@pytest.mark.parametrize("resource", ("workspace", "base", "table", "field", "source_record"))
def test_read_deletes_item_when_validity_chain_becomes_inactive(resource: str) -> None:
    uow, owner, workspace, base, table, record = _fixture()
    item = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW,
    )
    if resource == "workspace":
        workspace.status = "inactive"
    elif resource == "base":
        base.status = "inactive"
    elif resource == "table":
        table.status = "inactive"
    elif resource == "field":
        next(field for field in uow.fields if field.key == "decision").status = "inactive"
    else:
        record.record_status = "deleted"

    assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
    assert item.status == "deleted"

def test_candidate_revocation_requires_manager_workspace_lock_and_exact_version() -> None:
    uow, owner, workspace, _base, _table, _record = _fixture()
    candidate = Stage08MemoryExtractionCandidate(
        id=uuid4(),
        workspace_id=workspace.id,
        candidate_type="decision",
        status="candidate",
        confidence=0.9,
        scope={"workspace_id": str(workspace.id)},
        normalized_payload={"decision": "approved"},
        source_refs=[{"source_kind": "platform_record", "source_id": str(uuid4())}],
        source_fingerprint=uuid4().hex,
        version=1,
    )
    uow.add_memory_extraction_candidate(candidate)

    with pytest.raises(PlatformValidationError, match="memory_candidate_version_conflict"):
        revoke_memory_candidate(uow, candidate.id, actor=owner, expected_version=2, now=NOW)
    viewer = Actor(actor_type="user", actor_id="owner-1", role="viewer")
    with pytest.raises(PlatformValidationError, match="memory_candidate_revoke_forbidden"):
        revoke_memory_candidate(uow, candidate.id, actor=viewer, expected_version=1, now=NOW)

    revoked = revoke_memory_candidate(uow, candidate.id, actor=owner, expected_version=1, now=NOW)
    assert revoked == CandidateRevocationResult("rejected", 2, None)
    assert candidate.status == "rejected"
    assert candidate.reviewed_at == NOW
    assert candidate.reviewed_by_user_id is None
    assert candidate.version == 2
    assert "approved" not in str(uow.audit_events)

    with pytest.raises(PlatformValidationError, match="memory_candidate_invalid_state"):
        revoke_memory_candidate(uow, candidate.id, actor=owner, expected_version=2, now=NOW)

    foreign_candidate = Stage08MemoryExtractionCandidate(
        id=uuid4(),
        workspace_id=workspace.id,
        candidate_type="decision",
        status="candidate",
        confidence=0.9,
        scope={"workspace_id": str(workspace.id)},
        normalized_payload={"decision": "approved"},
        source_refs=[{"source_kind": "platform_record", "source_id": str(uuid4())}],
        source_fingerprint=uuid4().hex,
        version=1,
    )
    uow.add_memory_extraction_candidate(foreign_candidate)
    foreign_actor = Actor(actor_type="user", actor_id="foreign-owner", role="owner")
    with pytest.raises(PlatformValidationError, match="memory_candidate_workspace_denied"):
        revoke_memory_candidate(
            uow,
            foreign_candidate.id,
            actor=foreign_actor,
            expected_version=1,
            now=NOW,
        )


@pytest.mark.parametrize("invalid_version", (None, "1", 1.0, True, 0, -1))
def test_candidate_revocation_rejects_non_positive_non_integer_versions(invalid_version: object) -> None:
    uow, owner, workspace, _base, _table, _record = _fixture()
    candidate = Stage08MemoryExtractionCandidate(
        id=uuid4(), workspace_id=workspace.id, candidate_type="decision", status="candidate",
        confidence=0.9, scope={"workspace_id": str(workspace.id)}, normalized_payload={},
        source_refs=[], source_fingerprint=uuid4().hex, version=1,
    )
    uow.add_memory_extraction_candidate(candidate)
    with pytest.raises(PlatformValidationError, match="memory_candidate_expected_version_invalid"):
        revoke_memory_candidate(uow, candidate.id, actor=owner, expected_version=invalid_version, now=NOW)  # type: ignore[arg-type]


def test_candidate_revocation_rejects_inactive_workspace_and_audit_has_no_role() -> None:
    uow, owner, workspace, _base, _table, _record = _fixture()
    candidate = Stage08MemoryExtractionCandidate(
        id=uuid4(), workspace_id=workspace.id, candidate_type="decision", status="candidate",
        confidence=0.9, scope={"workspace_id": str(workspace.id)}, normalized_payload={},
        source_refs=[], source_fingerprint=uuid4().hex, version=1,
    )
    uow.add_memory_extraction_candidate(candidate)
    workspace.status = "inactive"
    with pytest.raises(PlatformValidationError, match="memory_candidate_workspace_inactive"):
        revoke_memory_candidate(uow, candidate.id, actor=owner, expected_version=1, now=NOW)
    workspace.status = "active"
    revoke_memory_candidate(uow, candidate.id, actor=owner, expected_version=1, now=NOW)
    event = uow.audit_events[-1]
    assert event.permission_snapshot == {"action": "memory_candidate_revoked"}


def _group_fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Group Memory", owner_user_id=owner.actor_id)
    member = uow.workspace_members[0]
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="-100123456",
        telegram_user_id="998877",
        binding_type="chat_user",
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(binding)
    return uow, owner, workspace, member, binding


def _group_projection(uow, workspace, binding, *, decision="approved", message_id=None, valid_until=None):
    trusted = TrustedGroupMessageInput(
        message_id=uuid4() if message_id is None else message_id,
        chat_id=binding.telegram_chat_id,
        chat_type="supergroup",
        binding_id=binding.id,
    )
    source = resolve_authorized_group_message_source(uow, trusted)
    assert source is not None
    projection = GroupMemoryCandidateProjection(
        candidate_type="decision",
        confidence=Decimal("0.85"),
        scope=source.scope,
        normalized_payload={"decision": decision},
        source_refs=(source.source_ref,),
        valid_until=valid_until,
    )
    return projection, source


def test_group_candidate_persists_only_safe_projection_then_accepts_once() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)

    candidate = create_group_memory_candidate(
        uow,
        projection,
        source=source,
        actor=owner,
        now=NOW,
    )
    assert candidate.status == "candidate"
    assert candidate.version == 1
    persisted = json.dumps(candidate.normalized_payload, sort_keys=True)
    assert "GROUP_MEMORY_RAW_SENTINEL" not in persisted
    assert binding.telegram_chat_id not in json.dumps(candidate.scope)
    assert binding.telegram_user_id not in json.dumps(candidate.scope)

    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None
    assert item.status == "active"
    assert item.source_fingerprint == candidate.source_fingerprint
    assert candidate.status == "accepted"
    assert candidate.version == 2
    assert resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW) is None
    assert len(uow.memory_items) == 1
    assert "approved" not in str(uow.audit_events)
    assert binding.telegram_chat_id not in str(uow.audit_events)


def test_group_candidate_service_rechecks_threshold_before_any_persistence() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    bypassed_dto = projection.model_copy(
        update={"confidence": Decimal("0.8499")}
    )

    with pytest.raises(
        PlatformValidationError,
        match="memory_candidate_confidence_below_threshold",
    ):
        create_group_memory_candidate(
            uow,
            bypassed_dto,
            source=source,
            actor=owner,
            now=NOW,
        )

    assert uow.memory_extraction_candidates == []
    assert uow.memory_items == []
    assert uow.outbox_events == []


def test_group_candidate_service_revalidates_bypassed_identity_carrier_payload() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    bypassed_dto = projection.model_copy(
        update={
            "normalized_payload": {
                "decision": {"chat_id": "GROUP_SOURCE_IDENTITY_SENTINEL"}
            }
        }
    )

    with pytest.raises(
        PlatformValidationError,
        match="memory_group_source_invalid",
    ):
        create_group_memory_candidate(
            uow,
            bypassed_dto,
            source=source,
            actor=owner,
            now=NOW,
        )

    assert uow.memory_extraction_candidates == []
    assert uow.memory_items == []
    assert "GROUP_SOURCE_IDENTITY_SENTINEL" not in str(uow.audit_events)


@pytest.mark.parametrize(
    "carrier_key",
    ["telegram_chat_id", "telegram_message_id", "telegram_update_id"],
)
def test_group_candidate_service_rejects_bypassed_telegram_transport_before_persistence(
    carrier_key: str,
) -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    bypassed_dto = projection.model_copy(
        update={
            "normalized_payload": {
                "decision": {carrier_key: "GROUP_TELEGRAM_IDENTITY_SENTINEL"}
            }
        }
    )

    with pytest.raises(
        PlatformValidationError,
        match="memory_group_source_invalid",
    ):
        create_group_memory_candidate(
            uow,
            bypassed_dto,
            source=source,
            actor=owner,
            now=NOW,
        )

    assert uow.memory_extraction_candidates == []
    assert uow.memory_items == []
    assert list_memory_projections(uow, workspace.id, actor=owner, now=NOW) == []
    assert "GROUP_TELEGRAM_IDENTITY_SENTINEL" not in str(uow.audit_events)


def test_group_candidate_same_message_is_idempotent_and_conflict_never_overwrites_active_fact() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    first = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    replay = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW + timedelta(seconds=1)
    )
    assert replay is first
    assert len(uow.memory_extraction_candidates) == 1
    active = resolve_group_candidate(uow, first.id, actor=owner, now=NOW)
    assert active is not None and active.status == "active"

    conflicting_projection, conflicting_source = _group_projection(
        uow,
        workspace,
        binding,
        decision="rejected",
    )
    conflict_candidate = create_group_memory_candidate(
        uow,
        conflicting_projection,
        source=conflicting_source,
        actor=owner,
        now=NOW + timedelta(seconds=2),
    )
    conflict = resolve_group_candidate(
        uow,
        conflict_candidate.id,
        actor=owner,
        now=NOW + timedelta(seconds=2),
    )
    assert conflict is not None and conflict.status == "conflicted"
    assert active.status == "active"
    assert active.payload == {"decision": "approved"}


def test_binding_revocation_ttl_or_corrupt_source_makes_group_memory_unreadable() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None

    binding.status = "revoked"
    assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
    assert item.status == "revoked"

    binding.status = "active"
    expiring_projection, expiring_source = _group_projection(
        uow,
        workspace,
        binding,
        message_id=uuid4(),
        valid_until=NOW + timedelta(seconds=1),
    )
    expiring_candidate = create_group_memory_candidate(
        uow,
        expiring_projection,
        source=expiring_source,
        actor=owner,
        now=NOW,
    )
    expiring = resolve_group_candidate(uow, expiring_candidate.id, actor=owner, now=NOW)
    assert expiring is not None
    assert read_memory_projection(
        uow, expiring.id, actor=owner, now=NOW + timedelta(seconds=2)
    ) is None
    assert expiring.status == "expired"

    corrupt_projection, corrupt_source = _group_projection(
        uow, workspace, binding, message_id=uuid4(), decision="pending"
    )
    corrupt_candidate = create_group_memory_candidate(
        uow,
        corrupt_projection,
        source=corrupt_source,
        actor=owner,
        now=NOW,
    )
    corrupt = resolve_group_candidate(uow, corrupt_candidate.id, actor=owner, now=NOW)
    assert corrupt is not None
    corrupt.source_refs = []
    assert read_memory_projection(uow, corrupt.id, actor=owner, now=NOW) is None
    assert corrupt.status == "deleted"


def test_accepted_candidate_revoke_revokes_only_exact_fingerprint_memory() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None
    unrelated = Stage08MemoryItem(
        id=uuid4(),
        workspace_id=workspace.id,
        memory_type="decision",
        status="active",
        scope=item.scope,
        payload={"decision": "unrelated"},
        source_refs=item.source_refs,
        source_fingerprint=uuid4().hex,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    uow.add_memory_item(unrelated)

    result = revoke_memory_candidate(
        uow,
        candidate.id,
        actor=owner,
        expected_version=2,
        now=NOW + timedelta(seconds=1),
    )
    assert result == CandidateRevocationResult("accepted", 2, "revoked")
    assert item.status == "revoked"
    assert unrelated.status == "active"
    assert candidate.status == "accepted"


def test_list_group_memory_returns_only_safe_active_projection() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None

    assert list_memory_projections(uow, workspace.id, actor=owner, now=NOW) == [
        {
            "memory_type": "decision",
            "status": "active",
            "version": 1,
            "payload": {"decision": "approved"},
            "valid_until": None,
        }
    ]


def test_generic_group_materialization_rejects_raw_carrier_without_persistence() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, _source = _group_projection(uow, workspace, binding)
    bypass = MemoryMaterializationProjection(
        memory_type=projection.candidate_type,
        scope=projection.scope,
        payload={"raw_caption": "GROUP_GENERIC_BYPASS_SENTINEL"},
        source_refs=projection.source_refs,
    )

    with pytest.raises(
        PlatformValidationError,
        match="memory_group_source_not_supported",
    ):
        materialize_memory_from_projection(uow, bypass, actor=owner, now=NOW)

    assert uow.memory_items == []
    assert list_memory_projections(uow, workspace.id, actor=owner, now=NOW) == []


def test_group_memory_read_deletes_stored_payload_with_source_identity_carrier() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None
    item.payload = {"binding_id": "GROUP_SOURCE_IDENTITY_SENTINEL"}

    assert list_memory_projections(uow, workspace.id, actor=owner, now=NOW) == []
    assert item.status == "deleted"
    assert "GROUP_SOURCE_IDENTITY_SENTINEL" not in str(uow.audit_events)


def test_accepted_candidate_revoke_recomputes_fingerprint_before_correlation() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    original = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert original is not None
    unrelated = Stage08MemoryItem(
        id=uuid4(),
        workspace_id=workspace.id,
        memory_type="decision",
        status="active",
        scope=original.scope,
        payload={"decision": "unrelated"},
        source_refs=original.source_refs,
        source_fingerprint=uuid4().hex,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    uow.add_memory_item(unrelated)
    candidate.source_fingerprint = unrelated.source_fingerprint

    with pytest.raises(
        PlatformValidationError,
        match="memory_candidate_source_invalid",
    ):
        revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=2,
            now=NOW + timedelta(seconds=1),
        )

    assert original.status == "active"
    assert unrelated.status == "active"


def test_expired_group_candidate_revoke_expires_instead_of_rejecting() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(
        uow,
        workspace,
        binding,
        valid_until=NOW + timedelta(seconds=1),
    )
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )

    with pytest.raises(PlatformValidationError, match="memory_candidate_expired"):
        revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=1,
            now=NOW + timedelta(seconds=2),
        )

    assert candidate.status == "expired"
    assert candidate.version == 2
    assert uow.memory_items == []
    assert "approved" not in str(uow.audit_events)
    assert uow.audit_events[-1].event_type == "stage08.memory_candidate_expired"
    assert uow.audit_events[-1].permission_snapshot == {
        "action": "memory_candidate_ttl_expired"
    }


def test_stale_version_precedes_candidate_ttl_expiry_without_mutation() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(
        uow,
        workspace,
        binding,
        valid_until=NOW + timedelta(seconds=1),
    )
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    audit_count = len(uow.audit_events)

    with pytest.raises(
        PlatformValidationError,
        match="memory_candidate_version_conflict",
    ):
        revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=99,
            now=NOW + timedelta(seconds=2),
        )

    assert candidate.status == "candidate"
    assert candidate.version == 1
    assert candidate.reviewed_at is None
    assert uow.memory_items == []
    assert len(uow.audit_events) == audit_count

    with pytest.raises(PlatformValidationError, match="memory_candidate_expired"):
        revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=1,
            now=NOW + timedelta(seconds=2),
        )

    assert candidate.status == "expired"
    assert candidate.version == 2


def test_expired_accepted_candidate_revoke_does_not_revoke_memory() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(
        uow,
        workspace,
        binding,
        valid_until=NOW + timedelta(seconds=1),
    )
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None

    with pytest.raises(PlatformValidationError, match="memory_candidate_expired"):
        revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=2,
            now=NOW + timedelta(seconds=2),
        )

    assert candidate.status == "expired"
    assert candidate.version == 3
    assert item.status == "active"


def test_stale_version_precedes_accepted_candidate_ttl_expiry_without_mutation() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(
        uow,
        workspace,
        binding,
        valid_until=NOW + timedelta(seconds=1),
    )
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None
    audit_count = len(uow.audit_events)
    reviewed_at = candidate.reviewed_at
    reviewed_by_user_id = candidate.reviewed_by_user_id
    item_version = item.version

    with pytest.raises(
        PlatformValidationError,
        match="memory_candidate_version_conflict",
    ):
        revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=99,
            now=NOW + timedelta(seconds=2),
        )

    assert candidate.status == "accepted"
    assert candidate.version == 2
    assert candidate.reviewed_at == reviewed_at
    assert candidate.reviewed_by_user_id == reviewed_by_user_id
    assert item.status == "active"
    assert item.version == item_version
    assert item.revoked_at is None
    assert len(uow.audit_events) == audit_count

    with pytest.raises(PlatformValidationError, match="memory_candidate_expired"):
        revoke_memory_candidate(
            uow,
            candidate.id,
            actor=owner,
            expected_version=2,
            now=NOW + timedelta(seconds=2),
        )

    assert candidate.status == "expired"
    assert candidate.version == 3
    assert item.status == "active"


def test_inactive_workspace_revokes_group_memory_instead_of_deleting_source() -> None:
    uow, owner, workspace, _member, binding = _group_fixture()
    projection, source = _group_projection(uow, workspace, binding)
    candidate = create_group_memory_candidate(
        uow, projection, source=source, actor=owner, now=NOW
    )
    item = resolve_group_candidate(uow, candidate.id, actor=owner, now=NOW)
    assert item is not None
    workspace.status = "archived"

    assert read_memory_projection(uow, item.id, actor=owner, now=NOW) is None
    assert item.status == "revoked"
    assert item.revoked_at == NOW
    assert item.deleted_at is None
