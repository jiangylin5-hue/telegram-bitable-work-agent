from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    specialist_payload_sha256,
)
from app.schemas.agent_stage12_runtime import (
    Stage12ObjectiveDispatchV1,
    Stage12RuntimeAdmissionRequest,
    Stage12RuntimeAdmissionResult,
)
from app.services.agent_typed_artifacts import stage12_command_input_artifact_ids


RUN_ID = UUID("32000000-0000-4000-8000-000000000001")
WORKSPACE_ID = UUID("32000000-0000-4000-8000-000000000002")
EMPLOYEE_ID = UUID("32000000-0000-4000-8000-000000000003")
HASH = "a" * 64


def _objective(*, dependencies: tuple[UUID, ...]) -> ObjectiveSpecialistInputV1:
    values = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-facts",
        "capability_id": "platform.tabular.analyse",
        "task_spec_ref": f"stage08-idempotency:{uuid4()}",
        "input_artifact_refs": dependencies,
        "scope_hash": HASH,
        "schema_hash": "b" * 64,
        "data_version_hash": "c" * 64,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ObjectiveSpecialistInputV1.model_validate(values)


def test_admission_request_requires_utc_deadline_and_never_serializes_raw_query_elsewhere() -> (
    None
):
    request = Stage12RuntimeAdmissionRequest(
        run_id=RUN_ID,
        actor_user_id="owner-1",
        workspace_id=WORKSPACE_ID,
        digital_employee_id=EMPLOYEE_ID,
        intent="business_fact",
        query="列出阻塞事项",
        target_record_id=None,
        idempotency_key="stage12-contract-1",
        skill_id="platform-tabular-analysis",
        authorization_hash=HASH,
        deadline_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )

    assert request.query == "列出阻塞事项"
    with pytest.raises(ValidationError, match="stage12_admission_utc_required"):
        Stage12RuntimeAdmissionRequest(
            **{
                **request.model_dump(),
                "deadline_at": datetime(2026, 8, 1, 12),
            }
        )


def test_dispatch_binds_one_objective_owner_to_the_exact_declared_dependencies() -> (
    None
):
    dependency_ids = (uuid4(), uuid4())
    objective_artifact_id = uuid4()
    dispatch = Stage12ObjectiveDispatchV1(
        objective=_objective(dependencies=dependency_ids),
        objective_artifact_id=objective_artifact_id,
        dependency_artifact_ids=dependency_ids,
        private_input_ref=f"agent-private-input:{uuid4()}",
    )

    assert stage12_command_input_artifact_ids(dispatch) == (
        objective_artifact_id,
        *dependency_ids,
    )
    assert "query" not in dispatch.model_dump(mode="json")


@pytest.mark.parametrize(
    ("dependency_ids", "owner_in_dependencies", "private_input_ref", "error"),
    [
        ((uuid4(),), False, f"agent-private-input:{uuid4()}", "dependency_mismatch"),
        (
            (),
            True,
            f"agent-private-input:{uuid4()}",
            "objective_owner_dependency_conflict",
        ),
        ((), False, f"stage08-idempotency:{uuid4()}", "string_pattern_mismatch"),
    ],
)
def test_dispatch_rejects_dependency_owner_or_private_ref_drift(
    dependency_ids: tuple[UUID, ...],
    owner_in_dependencies: bool,
    private_input_ref: str,
    error: str,
) -> None:
    declared = (uuid4(),)
    owner_id = declared[0] if owner_in_dependencies else uuid4()
    supplied = declared if owner_in_dependencies else dependency_ids

    with pytest.raises(ValidationError, match=error):
        Stage12ObjectiveDispatchV1(
            objective=_objective(dependencies=declared),
            objective_artifact_id=owner_id,
            dependency_artifact_ids=supplied,
            private_input_ref=private_input_ref,
        )


def test_dispatch_contract_forbids_plaintext_query_field() -> None:
    dependency_id = uuid4()

    with pytest.raises(ValidationError, match="extra_forbidden"):
        Stage12ObjectiveDispatchV1.model_validate(
            {
                "objective": _objective(dependencies=(dependency_id,)),
                "objective_artifact_id": uuid4(),
                "dependency_artifact_ids": (dependency_id,),
                "private_input_ref": f"agent-private-input:{uuid4()}",
                "query": "不得进入 typed artifact",
            }
        )


def test_admission_result_rejects_duplicate_objectives_and_non_hash_data_version() -> (
    None
):
    dependency_id = uuid4()
    dispatch = Stage12ObjectiveDispatchV1(
        objective=_objective(dependencies=(dependency_id,)),
        objective_artifact_id=uuid4(),
        dependency_artifact_ids=(dependency_id,),
        private_input_ref=f"agent-private-input:{uuid4()}",
    )

    with pytest.raises(ValidationError, match="stage12_dispatch_objective_duplicate"):
        Stage12RuntimeAdmissionResult(
            task_spec_ref=f"stage08-idempotency:{uuid4()}",
            schema_ref=f"stage08-idempotency:{uuid4()}",
            objective_dispatches=(dispatch, dispatch),
            data_version_hash=HASH,
        )
    with pytest.raises(ValidationError):
        Stage12RuntimeAdmissionResult(
            task_spec_ref=f"stage08-idempotency:{uuid4()}",
            schema_ref=f"stage08-idempotency:{uuid4()}",
            objective_dispatches=(dispatch,),
            data_version_hash="not-a-hash",
        )
