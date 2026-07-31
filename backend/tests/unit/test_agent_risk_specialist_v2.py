from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.services.agent_risk_policy import (
    AuthorizedRiskPolicyV1,
    risk_policy_sha256,
)
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2
from app.services.agent_specialists_v2.risk import RiskSpecialistV2


TABLE_ID = UUID("33000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("33000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("33000000-0000-4000-8000-000000000003")
HASH = "a" * 64


def _facts(scope_hash: str = HASH) -> StructuredFactSetV1:
    payload = {
        "version": "structured-fact-set.v1",
        "objective_id": "obj-tabular",
        "records": (
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "阻塞"},),
            },
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (
            {"table_id": TABLE_ID, "record_id": RECORD_ID, "record_version": 3},
        ),
        "evidence_refs": ("query-result:sha256:" + "b" * 64,),
        "scope_hash": scope_hash,
        "schema_hash": HASH,
        "complete": True,
        "truncated": False,
    }
    payload["content_hash"] = specialist_payload_sha256(payload)
    return StructuredFactSetV1.model_validate(payload)


def _policy(scope_hash: str = HASH) -> AuthorizedRiskPolicyV1:
    values = {
        "version": "authorized-risk-policy.v1",
        "policy_version": "workspace-risk.v1",
        "rules": (
            {
                "rule_id": "blocked-high",
                "field_id": FIELD_ID,
                "operator": "eq",
                "expected_value": "阻塞",
                "severity": "high",
                "reason_code": "blocked",
            },
        ),
        "scope_hash": scope_hash,
    }
    values["content_hash"] = risk_policy_sha256(values)
    return AuthorizedRiskPolicyV1.model_validate(values)


def _command(ref) -> ObjectiveSpecialistInputV1:
    values = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-risk",
        "capability_id": "platform.risk.analyse",
        "task_spec_ref": "task-spec:sha256:" + "c" * 64,
        "input_artifact_refs": (ref,),
        "scope_hash": HASH,
        "schema_hash": HASH,
        "data_version_hash": None,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return ObjectiveSpecialistInputV1.model_validate(values)


class _Bomb:
    def __getattr__(self, name):
        raise AssertionError(f"risk_must_not_call_{name}")


def test_risk_handler_consumes_fact_and_policy_without_rescan() -> None:
    ref = uuid4()
    context = SpecialistExecutionContextV2(
        artifact_reader=lambda value: _facts() if value == ref else None,
        risk_policy_reader=lambda _objective_id: _policy(),
        authorized_query_gateway=_Bomb(),
        model_gateway=_Bomb(),
        clock=lambda: datetime(2026, 7, 30, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )

    result = RiskSpecialistV2().execute(_command(ref), context)

    assert isinstance(result.payload, RiskAssessmentSetV1)
    assert result.payload.assessments[0].subject_ref == str(RECORD_ID)
    assert result.payload.assessments[0].severity == "high"
    assert result.payload.assessments[0].reason_codes == ("blocked",)
    assert result.metrics["provider_calls"] == 0


def test_risk_handler_rejects_policy_scope_drift() -> None:
    ref = uuid4()
    context = SpecialistExecutionContextV2(
        artifact_reader=lambda _value: _facts(),
        risk_policy_reader=lambda _objective_id: _policy("d" * 64),
        clock=lambda: datetime(2026, 7, 30, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )
    with pytest.raises(ValueError, match="risk_specialist_scope_mismatch"):
        RiskSpecialistV2().execute(_command(ref), context)
