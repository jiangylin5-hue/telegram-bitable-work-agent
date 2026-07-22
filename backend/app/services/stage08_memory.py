from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from typing import Any, Literal, NamedTuple
from uuid import UUID, uuid4

from app.models.stage08_memory import (
    Stage08MemoryExtractionCandidate,
    Stage08MemoryItem,
)
from app.models.outbox import OutboxEvent
from app.models.stage06_platform import PlatformRecord
from app.models.stage06_runtime import RecordChangeDraft
from app.runtime.stage08_memory_contracts import (
    GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE,
    GroupMemoryCandidateProjection,
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.stage08_group_memory_source import (
    GroupMemorySourceProjection,
    validate_group_memory_source_projection,
)
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    read_record_for_actor,
)


class CandidateRevocationResult(NamedTuple):
    candidate_status: Literal["rejected", "accepted", "expired"]
    candidate_version: int
    memory_status: Literal["revoked"] | None


def materialize_memory_from_projection(
    uow: Stage06PlatformUnitOfWork,
    projection: MemoryMaterializationProjection,
    *,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryItem:
    if _is_group_memory_projection(projection):
        raise PlatformValidationError(
            "memory_group_source_not_supported",
            "memory_group_source_not_supported",
        )
    return _materialize_memory_from_validated_projection(
        uow,
        projection,
        actor=actor,
        now=now,
    )


def _materialize_memory_from_validated_projection(
    uow: Stage06PlatformUnitOfWork,
    projection: MemoryMaterializationProjection,
    *,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryItem:
    locked_workspace = uow.lock_workspace_for_stage08_execution(
        projection.scope.workspace_id
    )
    if locked_workspace is None or locked_workspace.status != "active":
        raise PlatformValidationError("memory_scope_invalid", "memory_scope_invalid")
    _require_active_user_membership(uow, projection.scope.workspace_id, actor)
    _validate_scope(uow, projection.scope)
    _validate_current_platform_sources(uow, projection, actor)

    source_fingerprint = _source_fingerprint_for_projection(projection)
    identity_fingerprint = _fingerprint(
        {
            "memory_type": projection.memory_type,
            "scope": projection.scope.model_dump(mode="json", exclude_none=True),
        }
    )
    items = uow.list_memory_items(projection.scope.workspace_id)
    existing = next(
        (
            item
            for item in items
            if item.memory_type == projection.memory_type
            and item.source_fingerprint == source_fingerprint
        ),
        None,
    )
    if existing is not None:
        _record_memory_audit(uow, actor, "reused", existing, "memory_reused")
        return existing

    active = next(
        (
            item
            for item in items
            if item.status == "active"
            and _stored_identity_fingerprint(item) == identity_fingerprint
        ),
        None,
    )
    if active is None:
        item = _new_memory_item(
            projection,
            source_fingerprint=source_fingerprint,
            status="active",
            version=1,
            supersedes_id=None,
            now=now,
        )
        _add_memory_item_and_flush(uow, item)
        _record_memory_audit(uow, actor, "created", item, "memory_created")
        return item

    if _canonical_json(active.payload) == _canonical_json(projection.payload):
        active.status = "superseded"
        _record_memory_audit(uow, actor, "superseded", active, "memory_superseded")
        item = _new_memory_item(
            projection,
            source_fingerprint=source_fingerprint,
            status="active",
            version=active.version + 1,
            supersedes_id=active.id,
            now=now,
        )
        _add_memory_item_and_flush(uow, item)
        _record_memory_audit(uow, actor, "created", item, "memory_supersede_created")
        return item

    item = _new_memory_item(
        projection,
        source_fingerprint=source_fingerprint,
        status="conflicted",
        version=active.version + 1,
        supersedes_id=None,
        now=now,
    )
    _add_memory_item_and_flush(uow, item)
    _record_memory_audit(uow, actor, "conflicted", item, "memory_conflicted")
    return item


def create_group_memory_candidate(
    uow: Stage06PlatformUnitOfWork,
    projection: GroupMemoryCandidateProjection,
    *,
    source: GroupMemorySourceProjection,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryExtractionCandidate:
    projection = _revalidate_group_candidate_projection(projection)
    locked_workspace = uow.lock_workspace_for_stage08_execution(
        projection.scope.workspace_id
    )
    if locked_workspace is None or locked_workspace.status != "active":
        raise PlatformValidationError("memory_scope_invalid", "memory_scope_invalid")
    _require_active_user_membership(uow, projection.scope.workspace_id, actor)
    _validate_scope(uow, projection.scope)
    if (
        projection.scope != source.scope
        or projection.source_refs != (source.source_ref,)
        or projection.scope.group_chat_ref != f"stage06-binding:{source.binding_id}"
    ):
        raise PlatformValidationError(
            "memory_group_source_mismatch",
            "memory_group_source_mismatch",
        )
    source_state = validate_group_memory_source_projection(
        uow,
        scope=source.scope,
        source_ref=source.source_ref,
    )
    if source_state != "active":
        raise PlatformValidationError(
            "memory_group_source_invalid",
            "memory_group_source_invalid",
        )
    if projection.confidence < GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE:
        raise PlatformValidationError(
            "memory_candidate_confidence_below_threshold",
            "memory_candidate_confidence_below_threshold",
        )
    materialization = _materialization_from_group_candidate(projection)
    source_fingerprint = _source_fingerprint_for_projection(materialization)
    existing = next(
        (
            candidate
            for candidate in uow.list_memory_extraction_candidates(
                projection.scope.workspace_id
            )
            if candidate.candidate_type == projection.candidate_type
            and candidate.source_fingerprint == source_fingerprint
        ),
        None,
    )
    if existing is not None:
        return existing
    candidate = Stage08MemoryExtractionCandidate(
        id=uuid4(),
        workspace_id=projection.scope.workspace_id,
        candidate_type=projection.candidate_type,
        status="candidate",
        confidence=projection.confidence,
        scope=projection.scope.model_dump(mode="json", exclude_none=True),
        normalized_payload=projection.normalized_payload,
        source_refs=[
            source_ref.model_dump(mode="json") for source_ref in projection.source_refs
        ],
        source_fingerprint=source_fingerprint,
        version=1,
        valid_until=projection.valid_until,
        created_at=now,
        updated_at=now,
    )
    uow.add_memory_extraction_candidate(candidate)
    _flush_if_sqlalchemy(uow)
    _record_candidate_transition_audit(
        uow,
        actor,
        candidate,
        transition="created",
        reason_code="memory_candidate_created",
    )
    return candidate


def resolve_group_candidate(
    uow: Stage06PlatformUnitOfWork,
    candidate_id: UUID,
    *,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryItem | None:
    candidate_snapshot = uow.get_memory_extraction_candidate(candidate_id)
    if candidate_snapshot is None:
        return None
    locked_workspace = uow.lock_workspace_for_stage08_execution(
        candidate_snapshot.workspace_id
    )
    if locked_workspace is None or locked_workspace.status != "active":
        return None
    candidate = uow.lock_memory_extraction_candidate_for_lifecycle(candidate_id)
    if candidate is None or candidate.workspace_id != candidate_snapshot.workspace_id:
        return None
    _require_active_user_membership(uow, candidate.workspace_id, actor)
    if candidate.status != "candidate":
        return None
    if candidate.valid_until is not None and candidate.valid_until <= now:
        _expire_group_candidate(
            uow,
            candidate,
            actor=actor,
            now=now,
            reason_code="memory_candidate_ttl_expired",
        )
        return None
    projection = _group_projection_from_candidate(candidate)
    if projection is None:
        raise PlatformValidationError(
            "memory_group_source_invalid",
            "memory_group_source_invalid",
        )
    materialization = _materialization_from_group_candidate(projection)
    if candidate.source_fingerprint != _source_fingerprint_for_projection(materialization):
        raise PlatformValidationError(
            "memory_group_source_invalid",
            "memory_group_source_invalid",
        )
    source_state = validate_group_memory_source_projection(
        uow,
        scope=projection.scope,
        source_ref=projection.source_refs[0],
    )
    if source_state != "active":
        _expire_group_candidate(
            uow,
            candidate,
            actor=actor,
            now=now,
            reason_code="memory_candidate_source_invalid",
        )
        return None
    item = _materialize_memory_from_validated_projection(
        uow,
        materialization,
        actor=actor,
        now=now,
    )
    candidate.status = "accepted"
    candidate.version += 1
    candidate.reviewed_at = now
    candidate.reviewed_by_user_id = _actor_uuid_or_none(actor)
    _record_candidate_transition_audit(
        uow,
        actor,
        candidate,
        transition="accepted",
        reason_code="memory_candidate_accepted",
    )
    return item


CONFIRMED_RECORD_MEMORY_EVENT = "stage08.memory.confirmed_record.v1"
_CONFIRMED_RECORD_EVENT_KEYS = frozenset(
    {
        "workspace_id",
        "table_id",
        "record_id",
        "record_version",
        "policy_version",
        "rule_index",
    }
)
_SCOPE_FIELD_NAMES = frozenset({"customer_record_id", "project_record_id"})


def enqueue_confirmed_record_memory_event(
    uow: Stage06PlatformUnitOfWork,
    draft: RecordChangeDraft,
    record: PlatformRecord,
    *,
    confirmation_actor: Actor,
    now: datetime,
) -> OutboxEvent | None:
    """Create the post-confirmation event for an exactly-one-rule policy."""
    # The confirmation flow already holds this lock, but this service is also
    # invoked directly by recovery/replay paths.  Reacquiring the same row lock
    # serializes those callers before the idempotency-key lookup, so a second
    # SQLAlchemy session observes the committed reference-only event instead of
    # racing into the unique outbox constraint at commit time.
    locked_draft = uow.lock_record_change_draft_for_transition(draft.id)
    if locked_draft is not None:
        draft = locked_draft
    current_record = (
        uow.get_record(draft.record_id) if draft.record_id is not None else None
    )
    if current_record is None:
        return None
    record = current_record
    if getattr(draft, "status", None) != "confirmed":
        return None
    if (
        getattr(draft, "record_id", None) != getattr(record, "id", None)
        or getattr(draft, "table_id", None) != getattr(record, "table_id", None)
    ):
        return None
    table = uow.get_table(record.table_id)
    if table is None or table.status != "active":
        return None
    base = uow.get_base(table.base_id)
    if base is None or base.status != "active" or base.id != getattr(draft, "base_id", None):
        return None
    if base.workspace_id != getattr(draft, "workspace_id", None):
        return None
    policy = _memory_policy(table.settings)
    if policy is None:
        return None
    rule = policy["rules"][0]
    if not _policy_rule_is_currently_readable(
        uow, record, rule, confirmation_actor, base.workspace_id
    ):
        return None
    payload = {
        "workspace_id": str(base.workspace_id),
        "table_id": str(table.id),
        "record_id": str(record.id),
        "record_version": record.version,
        "policy_version": policy["version"],
        "rule_index": 0,
    }
    idempotency_key = "stage08:memory:confirmed_record:" + _fingerprint(payload)
    existing = uow.get_outbox_event_by_idempotency_key(idempotency_key)
    if existing is not None:
        return existing
    event = OutboxEvent(
        id=uuid4(),
        event_type=CONFIRMED_RECORD_MEMORY_EVENT,
        aggregate_type="platform_record",
        aggregate_id=str(record.id),
        payload=payload,
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        trace_id=f"stage08:memory:confirmed_record:{draft.id}",
        created_at=now,
    )
    uow.add_outbox_event(event)
    return event


def materialize_stage08_memory_outbox_event(
    uow: Stage06PlatformUnitOfWork,
    event_id: UUID,
    *,
    actor: Actor,
    now: datetime,
) -> Stage08MemoryItem | None:
    event = uow.get_outbox_event(event_id)
    if event is None or event.event_type != CONFIRMED_RECORD_MEMORY_EVENT:
        return None
    # A processed event is not a read capability.  Returning an ORM item here
    # would bypass B2's current membership, field, source, TTL, and scope
    # checks, so replays fail closed.
    if event.status == "processed":
        return None
    event_payload = event.payload
    if not isinstance(event_payload, dict) or set(event_payload) != _CONFIRMED_RECORD_EVENT_KEYS:
        return None
    try:
        workspace_id = UUID(str(event_payload["workspace_id"]))
        table_id = UUID(str(event_payload["table_id"]))
        record_id = UUID(str(event_payload["record_id"]))
        record_version = _positive_int(event_payload["record_version"])
        policy_version = _positive_int(event_payload["policy_version"])
        rule_index = _nonnegative_int(event_payload["rule_index"])
    except (KeyError, TypeError, ValueError):
        return None
    record = uow.get_record(record_id)
    table = uow.get_table(table_id)
    if (
        record is None
        or table is None
        or record.table_id != table_id
        or record.version != record_version
        or record.record_status != "active"
    ):
        return None
    base = uow.get_base(table.base_id)
    if base is None or base.workspace_id != workspace_id:
        return None
    policy = _memory_policy(table.settings)
    if policy is None or policy["version"] != policy_version:
        return None
    if rule_index >= len(policy["rules"]):
        return None
    projection = _projection_from_confirmed_record(
        uow,
        record=record,
        table=table,
        base_id=base.id,
        workspace_id=workspace_id,
        policy_version=policy_version,
        rule=policy["rules"][rule_index],
        actor=actor,
        now=now,
    )
    if projection is None:
        return None
    try:
        item = materialize_memory_from_projection(uow, projection, actor=actor, now=now)
    except PlatformValidationError:
        # Authorization, source, scope, and lifecycle checks can change after
        # enqueue.  These expected operational denials are fail-closed; leave
        # the event pending and do not conceal programmer errors.
        return None
    event.status = "processed"
    event.processed_at = now
    return item


def read_memory_projection(
    uow: Stage06PlatformUnitOfWork,
    item_id: UUID,
    *,
    actor: Actor,
    now: datetime,
    lifecycle_mode: Literal["lifecycle_aware", "read_only"] = "lifecycle_aware",
) -> dict[str, object] | None:
    if lifecycle_mode not in {"lifecycle_aware", "read_only"}:
        raise PlatformValidationError(
            "memory_lifecycle_mode_invalid", "memory_lifecycle_mode_invalid"
        )
    item = uow.get_memory_item(item_id)
    if item is None:
        return None
    if not _has_active_user_membership(uow, item.workspace_id, actor):
        return None
    if item.status != "active":
        return None
    if item.valid_until is not None and item.valid_until <= now:
        if lifecycle_mode == "read_only":
            return None
        locked = uow.lock_memory_item_for_lifecycle(item.id)
        if locked is not None and locked.status == "active":
            locked.status = "expired"
            _record_memory_audit(uow, actor, "expired", locked, "memory_ttl_expired")
        return None

    is_group_item = _stored_item_uses_group_source(item)
    projection: MemoryMaterializationProjection | None = None
    try:
        projection = MemoryMaterializationProjection.model_validate(
            {
                "memory_type": item.memory_type,
                "scope": item.scope,
                "payload": item.payload,
                "source_refs": item.source_refs,
                "valid_until": item.valid_until,
            }
        )
        if projection.scope.workspace_id != item.workspace_id:
            raise PlatformValidationError("memory_scope_invalid", "memory_scope_invalid")
        if is_group_item:
            _validate_group_materialization_contract(projection)
            _validate_current_platform_sources(uow, projection, actor)
            _validate_scope(uow, projection.scope)
        else:
            _validate_scope(uow, projection.scope)
            _validate_current_platform_sources(uow, projection, actor)
    except (PlatformValidationError, ValueError) as exc:
        if lifecycle_mode == "read_only":
            return None
        locked = uow.lock_memory_item_for_lifecycle(item.id)
        if locked is not None and locked.status == "active":
            if (
                is_group_item
                and isinstance(exc, PlatformValidationError)
                and exc.code == "memory_group_binding_revoked"
            ):
                locked.status = "revoked"
                locked.revoked_at = now
                _record_memory_audit(
                    uow, actor, "revoked", locked, "memory_group_binding_revoked"
                )
            else:
                locked.status = "deleted"
                locked.deleted_at = now
                _record_memory_audit(
                    uow, actor, "deleted", locked, "memory_source_invalid"
                )
        return None

    return {
        "id": item.id,
        "memory_type": item.memory_type,
        "version": item.version,
        "scope": projection.scope.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"identity_token"},
        ),
        "payload": projection.payload,
        "valid_until": item.valid_until,
    }


def revoke_memory_candidate(
    uow: Stage06PlatformUnitOfWork,
    candidate_id: UUID,
    *,
    actor: Actor,
    expected_version: int,
    now: datetime,
) -> CandidateRevocationResult:
    if (
        not isinstance(expected_version, int)
        or isinstance(expected_version, bool)
        or expected_version < 1
    ):
        raise PlatformValidationError(
            "memory_candidate_expected_version_invalid",
            "memory_candidate_expected_version_invalid",
        )
    candidate = uow.lock_memory_extraction_candidate_for_lifecycle(candidate_id)
    if candidate is None:
        raise PlatformValidationError(
            "memory_candidate_not_found",
            "memory_candidate_not_found",
        )
    _require_active_manager_membership(uow, candidate.workspace_id, actor)
    if candidate.version != expected_version:
        raise PlatformValidationError(
            "memory_candidate_version_conflict",
            "memory_candidate_version_conflict",
        )
    if (
        candidate.status in {"candidate", "accepted"}
        and candidate.valid_until is not None
        and candidate.valid_until <= now
    ):
        _expire_group_candidate(
            uow,
            candidate,
            actor=actor,
            now=now,
            reason_code="memory_candidate_ttl_expired",
        )
        raise PlatformValidationError(
            "memory_candidate_expired",
            "memory_candidate_expired",
        )
    group_projection = _group_projection_from_candidate(candidate)
    correlation_fingerprint = candidate.source_fingerprint
    if candidate.scope.get("group_chat_ref") is not None:
        if group_projection is None or validate_group_memory_source_projection(
            uow,
            scope=group_projection.scope,
            source_ref=group_projection.source_refs[0],
        ) != "active":
            _expire_group_candidate(
                uow,
                candidate,
                actor=actor,
                now=now,
                reason_code="memory_candidate_source_invalid",
            )
            raise PlatformValidationError(
                "memory_candidate_source_invalid",
                "memory_candidate_source_invalid",
            )
        canonical_fingerprint = _source_fingerprint_for_projection(
            _materialization_from_group_candidate(group_projection)
        )
        if candidate.source_fingerprint != canonical_fingerprint:
            _expire_group_candidate(
                uow,
                candidate,
                actor=actor,
                now=now,
                reason_code="memory_candidate_source_invalid",
            )
            raise PlatformValidationError(
                "memory_candidate_source_invalid",
                "memory_candidate_source_invalid",
            )
        correlation_fingerprint = canonical_fingerprint
    if candidate.status == "candidate":
        candidate.status = "rejected"
        candidate.reviewed_at = now
        candidate.reviewed_by_user_id = _actor_uuid_or_none(actor)
        candidate.version += 1
        _record_candidate_transition_audit(
            uow,
            actor,
            candidate,
            transition="rejected",
            reason_code="memory_candidate_revoked",
        )
        return CandidateRevocationResult("rejected", candidate.version, None)
    if candidate.status == "accepted":
        related = next(
            (
                item
                for item in uow.list_memory_items(candidate.workspace_id)
                if item.memory_type == candidate.candidate_type
                and item.source_fingerprint == correlation_fingerprint
            ),
            None,
        )
        if related is None:
            raise PlatformValidationError(
                "memory_candidate_related_item_missing",
                "memory_candidate_related_item_missing",
            )
        locked_item = uow.lock_memory_item_for_lifecycle(related.id)
        if locked_item is None or locked_item.status not in {"active", "conflicted"}:
            raise PlatformValidationError(
                "memory_candidate_related_item_not_revocable",
                "memory_candidate_related_item_not_revocable",
            )
        if group_projection is not None and not _memory_item_matches_group_candidate(
            locked_item,
            group_projection,
            correlation_fingerprint,
        ):
            _expire_group_candidate(
                uow,
                candidate,
                actor=actor,
                now=now,
                reason_code="memory_candidate_source_invalid",
            )
            raise PlatformValidationError(
                "memory_candidate_source_invalid",
                "memory_candidate_source_invalid",
            )
        locked_item.status = "revoked"
        locked_item.revoked_at = now
        _record_memory_audit(
            uow,
            actor,
            "revoked",
            locked_item,
            "memory_candidate_accepted_revoked",
        )
        return CandidateRevocationResult("accepted", candidate.version, "revoked")
    raise PlatformValidationError(
        "memory_candidate_invalid_state",
        "memory_candidate_invalid_state",
    )


def list_memory_projections(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    *,
    actor: Actor,
    now: datetime,
) -> list[dict[str, object]]:
    _require_active_user_membership(uow, workspace_id, actor)
    projections: list[dict[str, object]] = []
    for item in uow.list_memory_items(workspace_id):
        if item.status != "active":
            continue
        projection = read_memory_projection(uow, item.id, actor=actor, now=now)
        if projection is None:
            continue
        projections.append(
            {
                "memory_type": projection["memory_type"],
                "status": "active",
                "version": projection["version"],
                "payload": projection["payload"],
                "valid_until": projection["valid_until"],
            }
        )
    return projections


def _validate_scope(
    uow: Stage06PlatformUnitOfWork,
    scope: MemoryScopeProjection,
) -> None:
    workspace = uow.get_workspace(scope.workspace_id)
    if workspace is None or workspace.status != "active":
        raise PlatformValidationError("memory_scope_invalid", "memory_scope_invalid")
    base = None
    if scope.base_id is not None:
        base = uow.get_base(scope.base_id)
        if (
            base is None
            or base.status != "active"
            or base.workspace_id != scope.workspace_id
        ):
            raise PlatformValidationError("memory_scope_invalid", "memory_scope_invalid")
    if scope.table_id is not None:
        table = uow.get_table(scope.table_id)
        table_base = None if table is None else uow.get_base(table.base_id)
        if (
            table is None
            or table.status != "active"
            or table_base is None
            or table_base.status != "active"
            or table_base.workspace_id != scope.workspace_id
            or (base is not None and table.base_id != base.id)
        ):
            raise PlatformValidationError("memory_scope_invalid", "memory_scope_invalid")
    for record_id in (scope.customer_record_id, scope.project_record_id):
        if record_id is None:
            continue
        record = uow.get_record(record_id)
        table = None if record is None else uow.get_table(record.table_id)
        record_base = None if table is None else uow.get_base(table.base_id)
        if (
            record is None
            or record.record_status != "active"
            or table is None
            or table.status != "active"
            or record_base is None
            or record_base.status != "active"
            or record_base.workspace_id != scope.workspace_id
        ):
            raise PlatformValidationError("memory_scope_invalid", "memory_scope_invalid")


def _validate_current_platform_sources(
    uow: Stage06PlatformUnitOfWork,
    projection: MemoryMaterializationProjection,
    actor: Actor,
) -> None:
    if projection.scope.group_chat_ref is not None:
        if (
            not projection.scope.group_chat_ref.startswith("stage06-binding:")
            or len(projection.source_refs) != 1
            or projection.source_refs[0].source_kind != "telegram_message"
            or projection.source_refs[0].field_keys
            != ("group_candidate_projection",)
        ):
            raise PlatformValidationError(
                "memory_group_source_not_supported",
                "memory_group_source_not_supported",
            )
        source_state = validate_group_memory_source_projection(
            uow,
            scope=projection.scope,
            source_ref=projection.source_refs[0],
        )
        if source_state == "revoked":
            raise PlatformValidationError(
                "memory_group_binding_revoked",
                "memory_group_binding_revoked",
            )
        if source_state != "active":
            raise PlatformValidationError(
                "memory_source_invalid", "memory_source_invalid"
            )
        return
    readable_by_key: dict[str, object] = {}
    field_keys: set[str] = set()
    for source in projection.source_refs:
        if source.source_kind != "platform_record":
            raise PlatformValidationError(
                "memory_source_not_supported",
                "memory_source_not_supported",
            )
        if source.source_version is None:
            raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
        record = uow.get_record(source.source_id)
        if (
            record is None
            or record.record_status != "active"
            or record.version != source.source_version
        ):
            raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
        _validate_source_record_scope(uow, record.table_id, projection.scope)
        try:
            record_projection = read_record_for_actor(uow, record.id, actor=actor)
        except PlatformValidationError as exc:
            raise PlatformValidationError("memory_source_invalid", "memory_source_invalid") from exc
        readable = record_projection.get("values")
        if not isinstance(readable, dict):
            raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
        for key in source.field_keys:
            field = next(
                (item for item in uow.list_fields(record.table_id) if item.key == key),
                None,
            )
            if field is None or field.status != "active":
                raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
            if key not in readable:
                raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
            if key in readable_by_key and _canonical_json(readable_by_key[key]) != _canonical_json(readable[key]):
                raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
            readable_by_key[key] = readable[key]
            field_keys.add(key)
    for key, value in projection.payload.items():
        if key not in field_keys or key not in readable_by_key:
            raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
        if _canonical_json(value) != _canonical_json(readable_by_key[key]):
            raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")


def _validate_source_record_scope(
    uow: Stage06PlatformUnitOfWork,
    table_id: UUID,
    scope: MemoryScopeProjection,
) -> None:
    table = uow.get_table(table_id)
    base = None if table is None else uow.get_base(table.base_id)
    if (
        table is None
        or table.status != "active"
        or base is None
        or base.status != "active"
        or base.workspace_id != scope.workspace_id
    ):
        raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
    if scope.base_id is not None and table.base_id != scope.base_id:
        raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")
    if scope.table_id is not None and table_id != scope.table_id:
        raise PlatformValidationError("memory_source_invalid", "memory_source_invalid")


def _require_active_user_membership(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    actor: Actor,
) -> None:
    if not _has_active_user_membership(uow, workspace_id, actor):
        raise PlatformValidationError("actor_not_workspace_member", "actor_not_workspace_member")


def _has_active_user_membership(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    actor: Actor,
) -> bool:
    return actor.actor_type == "user" and any(
        member.user_id == actor.actor_id and member.status == "active"
        for member in uow.list_workspace_members(workspace_id)
    )


def _require_active_manager_membership(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    actor: Actor,
) -> None:
    if actor.actor_type != "user" or actor.role not in {"owner", "admin"}:
        raise PlatformValidationError(
            "memory_candidate_revoke_forbidden",
            "memory_candidate_revoke_forbidden",
        )
    workspace = uow.get_workspace(workspace_id)
    if workspace is None or workspace.status != "active":
        raise PlatformValidationError(
            "memory_candidate_workspace_inactive",
            "memory_candidate_workspace_inactive",
        )
    member = next(
        (
            item
            for item in uow.list_workspace_members(workspace_id)
            if item.user_id == actor.actor_id and item.status == "active"
        ),
        None,
    )
    if member is None:
        raise PlatformValidationError(
            "memory_candidate_workspace_denied",
            "memory_candidate_workspace_denied",
        )
    if member.role not in {"owner", "admin"}:
        raise PlatformValidationError(
            "memory_candidate_revoke_forbidden",
            "memory_candidate_revoke_forbidden",
        )


def _new_memory_item(
    projection: MemoryMaterializationProjection,
    *,
    source_fingerprint: str,
    status: str,
    version: int,
    supersedes_id: UUID | None,
    now: datetime,
) -> Stage08MemoryItem:
    return Stage08MemoryItem(
        id=uuid4(),
        workspace_id=projection.scope.workspace_id,
        memory_type=projection.memory_type,
        status=status,
        scope=projection.scope.model_dump(mode="json", exclude_none=True),
        payload=projection.payload,
        source_refs=[source.model_dump(mode="json") for source in projection.source_refs],
        source_fingerprint=source_fingerprint,
        version=version,
        supersedes_id=supersedes_id,
        valid_until=projection.valid_until,
        created_at=now,
        updated_at=now,
    )


def _stored_identity_fingerprint(item: Stage08MemoryItem) -> str | None:
    try:
        scope = MemoryScopeProjection.model_validate(item.scope)
        return _fingerprint(
            {
                "memory_type": item.memory_type,
                "scope": scope.model_dump(mode="json", exclude_none=True),
            }
        )
    except ValueError:
        return None


def _memory_policy(settings: object) -> dict[str, Any] | None:
    if not isinstance(settings, dict):
        return None
    policy = settings.get("memory_policy")
    if not isinstance(policy, dict) or set(policy) != {"version", "rules"}:
        return None
    if policy.get("version") != 1 or not isinstance(policy.get("rules"), list):
        return None
    rules: list[dict[str, Any]] = []
    for rule in policy["rules"]:
        if not _valid_memory_policy_rule(rule):
            return None
        rules.append(rule)
    if len(rules) != 1:
        return None
    return {"version": 1, "rules": rules}


def _valid_memory_policy_rule(rule: object) -> bool:
    if not isinstance(rule, dict) or set(rule) != {
        "memory_type",
        "identity_field_keys",
        "payload_field_keys",
        "scope_field_keys",
        "valid_for_days",
    }:
        return False
    if rule["memory_type"] not in {
        "decision", "preference", "risk", "customer_fact", "project_fact"
    }:
        return False
    for key_name in ("identity_field_keys", "payload_field_keys"):
        keys = rule[key_name]
        if (
            not isinstance(keys, list)
            or not keys
            or len(keys) != len(set(keys))
            or any(not _is_safe_policy_field_key(key) for key in keys)
        ):
            return False
    scope_fields = rule["scope_field_keys"]
    if (
        not isinstance(scope_fields, dict)
        or not scope_fields
        or not set(scope_fields).issubset(_SCOPE_FIELD_NAMES)
        or any(not _is_safe_policy_field_key(key) for key in scope_fields.values())
    ):
        return False
    valid_for_days = rule["valid_for_days"]
    return (
        isinstance(valid_for_days, int)
        and not isinstance(valid_for_days, bool)
        and 1 <= valid_for_days <= 3650
    )


def _is_safe_policy_field_key(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value not in {
        "prompt", "response", "raw_text", "normalized_text", "api_key", "token",
        "telegram_user_id",
    } and value.replace("_", "").isalnum() and value == value.lower()


def _policy_rule_is_currently_readable(
    uow: Stage06PlatformUnitOfWork,
    record: Any,
    rule: dict[str, Any],
    actor: Actor,
    workspace_id: UUID,
) -> bool:
    table = uow.get_table(record.table_id)
    if table is None:
        return False
    required_keys = set(rule["identity_field_keys"]) | set(rule["payload_field_keys"]) | set(rule["scope_field_keys"].values())
    active_keys = {field.key for field in uow.list_fields(table.id) if field.status == "active"}
    if not required_keys.issubset(active_keys):
        return False
    try:
        projection = read_record_for_actor(uow, record.id, actor=actor)
        values = projection.get("values")
        if not isinstance(values, dict) or not required_keys.issubset(values):
            return False
        scope = _scope_from_values(
            workspace_id=workspace_id,
            base_id=uow.get_base(table.base_id).id if uow.get_base(table.base_id) else None,
            table_id=table.id,
            values=values,
            scope_field_keys=rule["scope_field_keys"],
        )
        _validate_scope(uow, scope)
    except (PlatformValidationError, TypeError, ValueError):
        return False
    return True


def _projection_from_confirmed_record(
    uow: Stage06PlatformUnitOfWork,
    *,
    record: Any,
    table: Any,
    base_id: UUID,
    workspace_id: UUID,
    policy_version: int,
    rule: dict[str, Any],
    actor: Actor,
    now: datetime,
) -> MemoryMaterializationProjection | None:
    if not _policy_rule_is_currently_readable(uow, record, rule, actor, workspace_id):
        return None
    try:
        readable = read_record_for_actor(uow, record.id, actor=actor)["values"]
        if not isinstance(readable, dict):
            return None
        scope = _scope_from_values(
            workspace_id=workspace_id,
            base_id=base_id,
            table_id=table.id,
            values=readable,
            scope_field_keys=rule["scope_field_keys"],
        )
        identity_values = [readable[key] for key in rule["identity_field_keys"]]
        scope.identity_token = _identity_token(
            policy_version=policy_version,
            table_id=table.id,
            memory_type=rule["memory_type"],
            identity_field_values=identity_values,
        )
        source_keys = tuple(
            sorted(
                set(rule["identity_field_keys"])
                | set(rule["payload_field_keys"])
                | set(rule["scope_field_keys"].values())
            )
        )
        return MemoryMaterializationProjection(
            memory_type=rule["memory_type"],
            scope=scope,
            payload={key: readable[key] for key in rule["payload_field_keys"]},
            source_refs=(
                MemorySourceRef(
                    source_kind="platform_record",
                    source_id=record.id,
                    source_version=record.version,
                    field_keys=source_keys,
                ),
            ),
            valid_until=now + timedelta(days=rule["valid_for_days"]),
        )
    except (KeyError, PlatformValidationError, TypeError, ValueError):
        return None


def _scope_from_values(
    *,
    workspace_id: UUID,
    base_id: UUID | None,
    table_id: UUID,
    values: dict[str, Any],
    scope_field_keys: dict[str, str],
) -> MemoryScopeProjection:
    if base_id is None:
        raise ValueError("memory_scope_invalid")
    scope_values: dict[str, Any] = {
        "workspace_id": workspace_id,
        "base_id": base_id,
        "table_id": table_id,
    }
    for scope_name, field_key in scope_field_keys.items():
        scope_values[scope_name] = values[field_key]
    return MemoryScopeProjection.model_validate(scope_values)


def _identity_token(
    *,
    policy_version: int,
    table_id: UUID,
    memory_type: str,
    identity_field_values: list[Any],
) -> str:
    key = os.getenv("STAGE08_MEMORY_IDENTITY_HMAC_KEY")
    if not key:
        raise ValueError("memory_identity_hmac_key_missing")
    canonical_input = _canonical_json(
        {
            "policy_version": policy_version,
            "table_id": str(table_id),
            "memory_type": memory_type,
            "identity_field_values": identity_field_values,
        }
    )
    return hmac.new(key.encode("utf-8"), canonical_input.encode("utf-8"), hashlib.sha256).hexdigest()


def _positive_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("memory_outbox_reference_invalid")
    return value


def _nonnegative_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("memory_outbox_reference_invalid")
    return value


def _materialization_from_group_candidate(
    projection: GroupMemoryCandidateProjection,
) -> MemoryMaterializationProjection:
    return MemoryMaterializationProjection(
        memory_type=projection.candidate_type,
        scope=projection.scope,
        payload=projection.normalized_payload,
        source_refs=projection.source_refs,
        valid_until=projection.valid_until,
    )


def _revalidate_group_candidate_projection(
    projection: GroupMemoryCandidateProjection,
) -> GroupMemoryCandidateProjection:
    if projection.confidence < GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE:
        raise PlatformValidationError(
            "memory_candidate_confidence_below_threshold",
            "memory_candidate_confidence_below_threshold",
        )
    try:
        return GroupMemoryCandidateProjection(
            candidate_type=projection.candidate_type,
            confidence=projection.confidence,
            scope=projection.scope,
            normalized_payload=projection.normalized_payload,
            source_refs=projection.source_refs,
            valid_until=projection.valid_until,
        )
    except ValueError as exc:
        raise PlatformValidationError(
            "memory_group_source_invalid",
            "memory_group_source_invalid",
        ) from exc


def _is_group_memory_projection(
    projection: MemoryMaterializationProjection,
) -> bool:
    return projection.scope.group_chat_ref is not None or any(
        source.source_kind == "telegram_message" for source in projection.source_refs
    )


def _validate_group_materialization_contract(
    projection: MemoryMaterializationProjection,
) -> GroupMemoryCandidateProjection:
    try:
        return GroupMemoryCandidateProjection(
            candidate_type=projection.memory_type,
            confidence=GROUP_MEMORY_CANDIDATE_MIN_CONFIDENCE,
            scope=projection.scope,
            normalized_payload=projection.payload,
            source_refs=projection.source_refs,
            valid_until=projection.valid_until,
        )
    except ValueError as exc:
        raise PlatformValidationError(
            "memory_source_invalid",
            "memory_source_invalid",
        ) from exc


def _stored_item_uses_group_source(item: Stage08MemoryItem) -> bool:
    if isinstance(item.scope, dict) and item.scope.get("group_chat_ref") is not None:
        return True
    return isinstance(item.source_refs, list) and any(
        isinstance(source, dict) and source.get("source_kind") == "telegram_message"
        for source in item.source_refs
    )


def _memory_item_matches_group_candidate(
    item: Stage08MemoryItem,
    candidate: GroupMemoryCandidateProjection,
    expected_fingerprint: str,
) -> bool:
    try:
        projection = MemoryMaterializationProjection.model_validate(
            {
                "memory_type": item.memory_type,
                "scope": item.scope,
                "payload": item.payload,
                "source_refs": item.source_refs,
                "valid_until": item.valid_until,
            }
        )
        _validate_group_materialization_contract(projection)
    except (PlatformValidationError, ValueError):
        return False
    expected_projection = _materialization_from_group_candidate(candidate)
    return (
        item.workspace_id == candidate.scope.workspace_id
        and item.source_fingerprint == expected_fingerprint
        and _source_fingerprint_for_projection(projection) == expected_fingerprint
        and _canonical_json(projection.model_dump(mode="json"))
        == _canonical_json(expected_projection.model_dump(mode="json"))
    )


def _group_projection_from_candidate(
    candidate: Stage08MemoryExtractionCandidate,
) -> GroupMemoryCandidateProjection | None:
    try:
        projection = GroupMemoryCandidateProjection.model_validate(
            {
                "candidate_type": candidate.candidate_type,
                "confidence": candidate.confidence,
                "scope": candidate.scope,
                "normalized_payload": candidate.normalized_payload,
                "source_refs": candidate.source_refs,
                "valid_until": candidate.valid_until,
            },
            strict=False,
        )
    except (TypeError, ValueError):
        return None
    if projection.scope.workspace_id != candidate.workspace_id:
        return None
    return projection


def _source_fingerprint_for_projection(
    projection: MemoryMaterializationProjection,
) -> str:
    return _fingerprint(
        {
            "memory_type": projection.memory_type,
            "scope": projection.scope.model_dump(mode="json", exclude_none=True),
            "payload": projection.payload,
            "source_refs": [
                source.model_dump(mode="json") for source in projection.source_refs
            ],
        }
    )


def _expire_group_candidate(
    uow: Stage06PlatformUnitOfWork,
    candidate: Stage08MemoryExtractionCandidate,
    *,
    actor: Actor,
    now: datetime,
    reason_code: str,
) -> None:
    if candidate.status in {"candidate", "accepted"}:
        candidate.status = "expired"
        candidate.version += 1
        candidate.reviewed_at = now
        candidate.reviewed_by_user_id = _actor_uuid_or_none(actor)
        _record_candidate_transition_audit(
            uow,
            actor,
            candidate,
            transition="expired",
            reason_code=reason_code,
        )




def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _actor_uuid_or_none(actor: Actor) -> UUID | None:
    try:
        return UUID(actor.actor_id)
    except (TypeError, ValueError):
        return None


def _record_memory_audit(
    uow: Stage06PlatformUnitOfWork,
    actor: Actor,
    transition: str,
    item: Stage08MemoryItem,
    reason_code: str,
) -> None:
    record_audit_event(
        _audit_target(uow),
        trace_id=f"stage08:memory:{item.id}:{transition}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=f"stage08.memory_{transition}",
        entity_type="stage08_memory_item",
        entity_id=item.id,
        after_state={"status": item.status, "version": item.version},
        permission_snapshot={"action": reason_code},
    )


def _record_candidate_transition_audit(
    uow: Stage06PlatformUnitOfWork,
    actor: Actor,
    candidate: Stage08MemoryExtractionCandidate,
    *,
    transition: str,
    reason_code: str,
) -> None:
    record_audit_event(
        _audit_target(uow),
        trace_id=f"stage08:memory_candidate:{candidate.id}:{reason_code}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=f"stage08.memory_candidate_{transition}",
        entity_type="stage08_memory_extraction_candidate",
        entity_id=candidate.id,
        after_state={"status": candidate.status, "version": candidate.version},
        permission_snapshot={"action": reason_code},
    )


def _audit_target(uow: Stage06PlatformUnitOfWork) -> Any:
    return getattr(uow, "session", uow)


def _flush_if_sqlalchemy(uow: Stage06PlatformUnitOfWork) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.flush()


def _add_memory_item_and_flush(
    uow: Stage06PlatformUnitOfWork,
    item: Stage08MemoryItem,
) -> None:
    uow.add_memory_item(item)
    _flush_if_sqlalchemy(uow)
