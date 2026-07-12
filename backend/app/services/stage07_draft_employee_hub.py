from uuid import UUID, uuid4

from app.models.audit import OpsAuditEvent
from app.models.stage06_runtime import RecordChangeDraft
from app.services.permissions import Actor
from app.services.stage06_platform import PlatformValidationError, Stage06PlatformUnitOfWork


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
