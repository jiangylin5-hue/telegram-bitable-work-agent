from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.schemas.agent_specialist_results import (
    DailyBriefV1,
    ObjectiveSpecialistInputV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2
from app.services.agent_specialists_v2.daily import DailySpecialistV2


TABLE_ID = UUID("34000000-0000-4000-8000-000000000001")
FIELD_ID = UUID("34000000-0000-4000-8000-000000000002")
HASH = "a" * 64


def _facts() -> StructuredFactSetV1:
    payload = {
        "version": "structured-fact-set.v1",
        "objective_id": "obj-tabular",
        "records": tuple(
            {
                "record_id": UUID(f"34000000-0000-4000-8000-{index:012d}"),
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "记录"},),
            }
            for index in (3, 4)
        ),
        "groups": (),
        "aggregates": (
            {"aggregate_id": "agg-authoritative", "group_key": None, "value": 1},
        ),
        "relation_paths": (),
        "source_versions": (),
        "evidence_refs": ("query-result:sha256:" + "b" * 64,),
        "scope_hash": HASH,
        "schema_hash": HASH,
        "complete": True,
        "truncated": False,
    }
    payload["content_hash"] = specialist_payload_sha256(payload)
    return StructuredFactSetV1.model_validate(payload)


def _command(ref) -> ObjectiveSpecialistInputV1:
    values = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-daily",
        "capability_id": "platform.daily.summarise",
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
        raise AssertionError(f"daily_must_not_call_{name}")


def test_daily_handler_uses_authoritative_aggregate_and_does_not_recount() -> None:
    ref = uuid4()
    context = SpecialistExecutionContextV2(
        artifact_reader=lambda value: _facts() if value == ref else None,
        authorized_query_gateway=_Bomb(),
        model_gateway=_Bomb(),
        clock=lambda: datetime(2026, 7, 30, 8, 0, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )

    result = DailySpecialistV2().execute(_command(ref), context)

    assert isinstance(result.payload, DailyBriefV1)
    fact = result.payload.statements[0]
    assert fact.aggregate_id == "agg-authoritative"
    assert "1" in fact.text
    assert "2" not in fact.text
    assert result.metrics["provider_calls"] == 0


def test_daily_handler_preserves_grouped_aggregate_identity_without_collision() -> None:
    facts = _facts()
    values = facts.model_dump(mode="python", exclude={"content_hash"})
    values["aggregates"] = (
        {"aggregate_id": "agg-status", "group_key": "blocked", "value": 2},
        {"aggregate_id": "agg-status", "group_key": "planned", "value": 3},
    )
    values["content_hash"] = specialist_payload_sha256(values)
    facts = StructuredFactSetV1.model_validate(values)
    ref = uuid4()
    context = SpecialistExecutionContextV2(
        artifact_reader=lambda value: facts if value == ref else None,
        clock=lambda: datetime(2026, 7, 30, 8, 0, tzinfo=UTC),
        metrics=lambda _name, _value: None,
    )

    result = DailySpecialistV2().execute(_command(ref), context)

    assert len(result.payload.statements) == 2
    assert len({item.statement_id for item in result.payload.statements}) == 2
    assert {item.aggregate_id for item in result.payload.statements} == {"agg-status"}
    assert any("blocked" in item.text for item in result.payload.statements)
    assert any("planned" in item.text for item in result.payload.statements)
