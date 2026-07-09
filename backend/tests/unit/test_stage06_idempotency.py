from uuid import uuid4

import pytest

from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_workspace,
)


def test_stage06_request_fingerprint_is_canonical() -> None:
    assert fingerprint_request({"b": 2, "a": 1}) == fingerprint_request(
        {"a": 1, "b": 2}
    )


def test_stage06_same_key_and_fingerprint_replays_completed_result() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    fingerprint = fingerprint_request({"import_job_id": "job-1"})

    first = begin_idempotent_operation(
        uow,
        workspace_id=workspace.id,
        operation="import.commit",
        idempotency_key="key-1",
        request_fingerprint=fingerprint,
        trace_id="trace-1",
    )
    complete_idempotent_operation(
        first.record,
        response_ref={"import_job_id": "job-1", "status": "committed"},
    )
    replay = begin_idempotent_operation(
        uow,
        workspace_id=workspace.id,
        operation="import.commit",
        idempotency_key="key-1",
        request_fingerprint=fingerprint,
        trace_id="trace-2",
    )

    assert first.status == "started"
    assert replay.status == "replay"
    assert replay.response_ref == {
        "import_job_id": "job-1",
        "status": "committed",
    }
    assert len(uow.idempotency_records) == 1


def test_stage06_same_key_with_different_fingerprint_conflicts() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    begin_idempotent_operation(
        uow,
        workspace_id=workspace.id,
        operation="import.commit",
        idempotency_key="key-1",
        request_fingerprint="sha-a",
        trace_id="trace-1",
    )

    with pytest.raises(PlatformValidationError) as denied:
        begin_idempotent_operation(
            uow,
            workspace_id=workspace.id,
            operation="import.commit",
            idempotency_key="key-1",
            request_fingerprint="sha-b",
            trace_id="trace-2",
        )

    assert denied.value.code == "idempotency_conflict"


def test_stage06_in_progress_duplicate_conflicts() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    fingerprint = fingerprint_request({"draft_id": str(uuid4())})
    begin_idempotent_operation(
        uow,
        workspace_id=workspace.id,
        operation="draft.confirm",
        idempotency_key="key-1",
        request_fingerprint=fingerprint,
        trace_id="trace-1",
    )

    with pytest.raises(PlatformValidationError) as denied:
        begin_idempotent_operation(
            uow,
            workspace_id=workspace.id,
            operation="draft.confirm",
            idempotency_key="key-1",
            request_fingerprint=fingerprint,
            trace_id="trace-2",
        )

    assert denied.value.code == "idempotency_in_progress"
