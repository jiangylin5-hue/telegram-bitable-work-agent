from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import inf, nan
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint

from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage08_memory import (
    Stage08MemoryExtractionCandidate,
    Stage08MemoryItem,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_workspace,
)
from app.runtime.stage08_memory_contracts import (
    GroupMemoryCandidateProjection,
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.stage08_group_memory_source import (
    TrustedGroupMessageInput,
    resolve_authorized_group_message_source,
)
from app.services.stage08_memory import GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def _memory_item(
    *,
    workspace_id,
    created_at=NOW,
    item_id: UUID | None = None,
) -> Stage08MemoryItem:
    return Stage08MemoryItem(
        id=uuid4() if item_id is None else item_id,
        workspace_id=workspace_id,
        memory_type="customer_fact",
        status="active",
        scope={"workspace_id": str(workspace_id)},
        payload={"customer_key": "acme"},
        source_refs=[{"source_kind": "platform_record", "source_id": str(uuid4())}],
        source_fingerprint=uuid4().hex,
        version=1,
        created_at=created_at,
        updated_at=created_at,
    )


def _candidate(
    *,
    workspace_id,
    created_at=NOW,
    candidate_id: UUID | None = None,
) -> Stage08MemoryExtractionCandidate:
    return Stage08MemoryExtractionCandidate(
        id=uuid4() if candidate_id is None else candidate_id,
        workspace_id=workspace_id,
        candidate_type="customer_fact",
        status="candidate",
        confidence=0.9,
        scope={"workspace_id": str(workspace_id)},
        normalized_payload={"customer_key": "acme"},
        source_refs=[{"source_kind": "telegram_message", "source_id": str(uuid4())}],
        source_fingerprint=uuid4().hex,
        version=1,
        created_at=created_at,
        updated_at=created_at,
    )


def test_memory_model_contract_exposes_canonical_lifecycle_checks() -> None:
    item_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in Stage08MemoryItem.__table__.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }
    candidate_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in Stage08MemoryExtractionCandidate.__table__.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }

    assert "active" in item_constraints["ck_stage08_memory_item_status"]
    assert "deleted" in item_constraints["ck_stage08_memory_item_status"]
    assert "jsonb_typeof(scope) = 'object'" in item_constraints[
        "ck_stage08_memory_item_scope_object"
    ]
    assert "jsonb_typeof(payload) = 'object'" in item_constraints[
        "ck_stage08_memory_item_payload_object"
    ]
    assert "jsonb_typeof(source_refs) = 'array'" in item_constraints[
        "ck_stage08_memory_item_source_refs_array"
    ]
    assert "version > 0" in item_constraints["ck_stage08_memory_item_version_positive"]
    assert "candidate" in candidate_constraints[
        "ck_stage08_memory_candidate_status"
    ]
    assert "expired" in candidate_constraints["ck_stage08_memory_candidate_status"]
    assert "confidence >= 0 AND confidence <= 1" in candidate_constraints[
        "ck_stage08_memory_candidate_confidence_range"
    ]


def test_in_memory_memory_uow_returns_newest_items_and_candidates_first() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace_id = uuid4()
    older_item = _memory_item(workspace_id=workspace_id, created_at=NOW)
    newer_item = _memory_item(
        workspace_id=workspace_id,
        created_at=NOW + timedelta(seconds=1),
    )
    older_candidate = _candidate(workspace_id=workspace_id, created_at=NOW)
    newer_candidate = _candidate(
        workspace_id=workspace_id,
        created_at=NOW + timedelta(seconds=1),
    )

    uow.add_memory_item(older_item)
    uow.add_memory_item(newer_item)
    uow.add_memory_extraction_candidate(older_candidate)
    uow.add_memory_extraction_candidate(newer_candidate)

    assert uow.get_memory_item(newer_item.id) is newer_item
    assert uow.lock_memory_item_for_lifecycle(newer_item.id) is newer_item
    assert uow.list_memory_items(workspace_id) == [newer_item, older_item]
    assert uow.get_memory_extraction_candidate(newer_candidate.id) is newer_candidate
    assert (
        uow.lock_memory_extraction_candidate_for_lifecycle(newer_candidate.id)
        is newer_candidate
    )
    assert uow.list_memory_extraction_candidates(workspace_id) == [
        newer_candidate,
        older_candidate,
    ]


def test_in_memory_memory_uow_breaks_equal_created_at_ties_by_id_descending() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace_id = uuid4()
    lower_id = UUID(int=1)
    higher_id = UUID(int=2)
    lower_item = _memory_item(
        workspace_id=workspace_id,
        item_id=lower_id,
    )
    higher_item = _memory_item(
        workspace_id=workspace_id,
        item_id=higher_id,
    )
    lower_candidate = _candidate(
        workspace_id=workspace_id,
        candidate_id=lower_id,
    )
    higher_candidate = _candidate(
        workspace_id=workspace_id,
        candidate_id=higher_id,
    )

    uow.add_memory_item(lower_item)
    uow.add_memory_item(higher_item)
    uow.add_memory_extraction_candidate(lower_candidate)
    uow.add_memory_extraction_candidate(higher_candidate)

    assert uow.list_memory_items(workspace_id) == [higher_item, lower_item]
    assert uow.list_memory_extraction_candidates(workspace_id) == [
        higher_candidate,
        lower_candidate,
    ]


def test_memory_projection_contract_rejects_recursive_raw_content_keys() -> None:
    workspace_id = uuid4()

    import pytest

    with pytest.raises(ValueError):
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(workspace_id=workspace_id),
            payload={"safe": {"RAW_TEXT": "never persist"}},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=uuid4(),
                    source_version=1,
                    field_keys=("safe",),
                ),
            ),
        )


def test_memory_projection_contract_rejects_malformed_sources_and_non_json_values() -> None:
    workspace_id = uuid4()

    import pytest

    with pytest.raises(ValueError):
        MemorySourceRef(
            source_kind="platform_record",
            source_id=uuid4(),
            source_version=1,
            field_keys=("Bad-Key", ""),
        )


@pytest.mark.parametrize(
    "field_key",
    ("prompt", "Response", "RAW_TEXT", "normalized_text", "api_key", "TOKEN", "telegram_user_id"),
)
def test_memory_source_ref_rejects_forbidden_field_key_names(field_key: str) -> None:
    with pytest.raises(ValueError, match="memory_forbidden_content_key"):
        MemorySourceRef(
            source_kind="platform_record",
            source_id=uuid4(),
            source_version=1,
            field_keys=(field_key,),
        )


@pytest.mark.parametrize("invalid_number", (nan, inf, -inf))
def test_memory_projection_contract_rejects_non_finite_json_numbers(invalid_number: float) -> None:
    with pytest.raises(ValueError, match="memory_non_finite_json_value"):
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(workspace_id=uuid4()),
            payload={"safe": {"nested": invalid_number}},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=uuid4(),
                    source_version=1,
                    field_keys=("safe",),
                ),
            ),
        )


def test_memory_projection_contract_requires_timezone_aware_valid_until() -> None:
    workspace_id = uuid4()
    with pytest.raises(ValueError, match="memory_valid_until_timezone_required"):
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(workspace_id=uuid4()),
            payload={"safe": "value"},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=uuid4(),
                    source_version=1,
                    field_keys=("safe",),
                ),
            ),
            valid_until=datetime(2026, 7, 18, 12, 0),
        )
    with pytest.raises(ValueError):
        MemoryMaterializationProjection(
            memory_type="unknown",
            scope=MemoryScopeProjection(workspace_id=workspace_id),
            payload={"safe": "value"},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=uuid4(),
                    source_version=1,
                    field_keys=("safe",),
                ),
            ),
        )
    with pytest.raises(ValueError):
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(workspace_id=workspace_id),
            payload={"safe": object()},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=uuid4(),
                    source_version=1,
                    field_keys=("safe",),
                ),
            ),
        )
    with pytest.raises(ValueError):
        MemoryMaterializationProjection(
            memory_type="decision",
            scope=MemoryScopeProjection(workspace_id=workspace_id),
            payload={"safe": "value"},
            source_refs=(),
        )


def _group_candidate_projection(
    workspace_id: UUID,
    binding_id: UUID,
    *,
    confidence: Decimal = Decimal("0.85"),
    payload: dict[str, object] | None = None,
) -> GroupMemoryCandidateProjection:
    return GroupMemoryCandidateProjection(
        candidate_type="decision",
        confidence=confidence,
        scope=MemoryScopeProjection(
            workspace_id=workspace_id,
            group_chat_ref=f"stage06-binding:{binding_id}",
        ),
        normalized_payload={"decision": "approved"} if payload is None else payload,
        source_refs=(
            MemorySourceRef(
                source_kind="telegram_message",
                source_id=uuid4(),
                source_version=None,
                field_keys=("group_candidate_projection",),
            ),
        ),
    )


def test_group_candidate_requires_exact_deployed_confidence_floor() -> None:
    workspace_id = uuid4()
    binding_id = uuid4()

    assert GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE == Decimal("0.85")
    assert _group_candidate_projection(
        workspace_id,
        binding_id,
        confidence=Decimal("0.85"),
    ).confidence == Decimal("0.85")
    with pytest.raises(ValueError, match="memory_candidate_confidence_below_threshold"):
        _group_candidate_projection(
            workspace_id,
            binding_id,
            confidence=Decimal("0.8499"),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"decision": {"raw_text": "GROUP_MEMORY_RAW_SENTINEL"}},
        {"message_text": "GROUP_MEMORY_RAW_SENTINEL"},
        {"decision": "x" * 501},
        {"decision": [str(index) for index in range(21)]},
        {"decision": {"a": {"b": {"c": {"d": "too-deep"}}}}},
        {f"key_{index}": index for index in range(17)},
    ],
)
def test_group_candidate_rejects_raw_message_carriers_and_limits_recursively(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="memory_(forbidden_content_key|payload_invalid)"):
        _group_candidate_projection(uuid4(), uuid4(), payload=payload)

    with pytest.raises(ValidationError):
        TrustedGroupMessageInput(
            message_id=uuid4(),
            chat_id="-100123",
            chat_type="group",
            binding_id=uuid4(),
            raw_text="GROUP_MEMORY_RAW_SENTINEL",
        )


@pytest.mark.parametrize(
    "carrier_key",
    ["chat_id", "binding_id", "group_chat_ref", "source_refs", "field_keys"],
)
def test_group_candidate_rejects_transport_and_source_identity_carriers_recursively(
    carrier_key: str,
) -> None:
    with pytest.raises(ValueError, match="memory_forbidden_content_key"):
        _group_candidate_projection(
            uuid4(),
            uuid4(),
            payload={"decision": {carrier_key: "GROUP_SOURCE_IDENTITY_SENTINEL"}},
        )


@pytest.mark.parametrize(
    "carrier_key",
    [
        "telegram_chat_id",
        "telegram_message_id",
        "telegram_update_id",
        "message_id",
        "update_id",
        "source_id",
        "source_ref",
    ],
)
def test_group_candidate_rejects_telegram_transport_identity_carriers_recursively(
    carrier_key: str,
) -> None:
    with pytest.raises(ValueError, match="memory_forbidden_content_key"):
        _group_candidate_projection(
            uuid4(),
            uuid4(),
            payload={"decision": {carrier_key: "GROUP_TELEGRAM_IDENTITY_SENTINEL"}},
        )


def test_group_candidate_requires_exact_telegram_source_and_opaque_binding_ref() -> None:
    workspace_id = uuid4()
    binding_id = uuid4()
    projection = _group_candidate_projection(workspace_id, binding_id)
    assert projection.source_refs[0].field_keys == ("group_candidate_projection",)

    with pytest.raises(ValueError, match="memory_group_source_invalid"):
        GroupMemoryCandidateProjection(
            candidate_type="decision",
            confidence=Decimal("0.85"),
            scope=MemoryScopeProjection(
                workspace_id=workspace_id,
                group_chat_ref="stage06-binding:not-a-uuid",
            ),
            normalized_payload={"decision": "approved"},
            source_refs=projection.source_refs,
        )


def test_adapter_requires_active_chat_user_binding_member_and_real_group_type() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Group memory", owner_user_id="owner-1")
    member = uow.workspace_members[0]
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="-100123",
        telegram_user_id="987654",
        binding_type="chat_user",
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(binding)
    trusted = TrustedGroupMessageInput(
        message_id=uuid4(),
        chat_id="-100123",
        chat_type="supergroup",
        binding_id=binding.id,
    )

    source = resolve_authorized_group_message_source(uow, trusted)
    assert source is not None
    assert source.binding_id == binding.id
    assert source.scope == MemoryScopeProjection(
        workspace_id=workspace.id,
        group_chat_ref=f"stage06-binding:{binding.id}",
    )
    assert source.source_ref.source_id == trusted.message_id
    assert source.source_ref.source_version is None
    assert "-100123" not in source.model_dump_json()
    assert "987654" not in source.model_dump_json()

    binding.status = "revoked"
    assert resolve_authorized_group_message_source(uow, trusted) is None
    binding.status = "active"
    member.status = "disabled"
    assert resolve_authorized_group_message_source(uow, trusted) is None
    member.status = "active"
    binding.binding_type = "user"
    assert resolve_authorized_group_message_source(uow, trusted) is None
    binding.binding_type = "chat_user"
    wrong_chat = trusted.model_copy(update={"chat_id": "-100999"})
    assert resolve_authorized_group_message_source(uow, wrong_chat) is None

    with pytest.raises(ValidationError):
        TrustedGroupMessageInput(
            message_id=uuid4(),
            chat_id="-100123",
            chat_type="private",
            binding_id=binding.id,
        )
