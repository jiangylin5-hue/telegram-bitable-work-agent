from uuid import UUID, uuid4

from app.models.audit import OpsAuditEvent
from app.models.stage06_runtime import RecordChangeDraft
from app.services.permissions import Actor
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    update_record,
)


def reject_s5_draft(
    uow: Stage06PlatformUnitOfWork,
    draft_id: UUID,
    *,
    expected_version: int,
    actor: Actor,
) -> RecordChangeDraft:
    draft = uow.lock_record_change_draft_for_transition(draft_id)
    if draft is None:
        raise PlatformValidationError("record_change_draft_not_found", str(draft_id))
    if draft.status != "pending_confirmation":
        raise PlatformValidationError("record_change_draft_invalid_state", str(draft_id))
    if draft.version != expected_version:
        raise PlatformValidationError("record_change_draft_revision_conflict", str(draft_id))
    audit = OpsAuditEvent(
        id=uuid4(),
        trace_id=f"stage07:draft-reject:{draft.id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="stage07.record_change_draft_rejected",
        entity_type="record_change_draft",
        entity_id=draft.id,
        after_state={"status": "rejected"},
        permission_snapshot={"role": actor.role, "action": "record_change_draft.reject"},
    )
    getattr(uow, "session", uow).add(audit)
    draft.status = "rejected"
    draft.version += 1
    draft.terminal_audit_event_id = audit.id
    return draft


def confirm_s5_draft(
    uow: Stage06PlatformUnitOfWork,
    draft_id: UUID,
    *,
    expected_version: int,
    actor: Actor,
) -> RecordChangeDraft:
    draft = _lock_pending_s5_draft(uow, draft_id, expected_version)
    if draft.record_id is None:
        raise PlatformValidationError("record_change_draft_missing_record", str(draft_id))
    record = uow.get_record(draft.record_id)
    if record is None:
        raise PlatformValidationError("record_not_found", str(draft.record_id))
    if record.table_id != draft.table_id:
        raise PlatformValidationError("resource_scope_mismatch", "draft_record_table")
    update_record(
        uow,
        record.id,
        values=draft.proposed_values,
        expected_version=draft.expected_version,
        actor=actor,
    )
    _mark_terminal(
        uow,
        draft,
        actor=actor,
        status="confirmed",
        event_type="stage07.record_change_draft_confirmed",
        action="record_change_draft.confirm",
    )
    return draft


def _lock_pending_s5_draft(
    uow: Stage06PlatformUnitOfWork,
    draft_id: UUID,
    expected_version: int,
) -> RecordChangeDraft:
    draft = uow.lock_record_change_draft_for_transition(draft_id)
    if draft is None:
        raise PlatformValidationError("record_change_draft_not_found", str(draft_id))
    if draft.status != "pending_confirmation":
        raise PlatformValidationError("record_change_draft_invalid_state", str(draft_id))
    if draft.version != expected_version:
        raise PlatformValidationError("record_change_draft_revision_conflict", str(draft_id))
    return draft


def _mark_terminal(
    uow: Stage06PlatformUnitOfWork,
    draft: RecordChangeDraft,
    *,
    actor: Actor,
    status: str,
    event_type: str,
    action: str,
) -> None:
    audit = OpsAuditEvent(
        id=uuid4(),
        trace_id=f"stage07:draft-{status}:{draft.id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=event_type,
        entity_type="record_change_draft",
        entity_id=draft.id,
        after_state={"status": status},
        permission_snapshot={"role": actor.role, "action": action},
    )
    getattr(uow, "session", uow).add(audit)
    draft.status = status
    draft.version += 1
    draft.terminal_audit_event_id = audit.id
