from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import UUID, uuid4

import pytest

from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    StructuredAggregate,
    StructuredFieldValue,
    StructuredQueryArtifactV1,
    StructuredQueryResultV1,
    StructuredRecord,
    authorized_query_plan_sha256,
    structured_query_result_sha256,
)
from app.services.agent_specialists_v2.base import SpecialistExecutionContextV2
from app.services.agent_specialists_v2.tabular import TabularSpecialistV2


TABLE_ID = UUID("32000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("32000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("32000000-0000-4000-8000-000000000003")
HASH = "a" * 64


def _query_artifact(*, scope_hash: str = HASH, truncated: bool = False):
    plan = AuthorizedQueryPlanV1(
        version="authorized-query-plan.v1",
        query_intent_id="query-01",
        root_table_id=TABLE_ID,
        authorized_view_ids=(),
        entity_codes=(),
        predicate=None,
        traversals=(),
        projection_field_ids=(FIELD_ID,),
        group_by_field_ids=(),
        aggregates=(),
        sort_rules=(),
        limit=None,
        max_scan_rows=5000,
        max_relation_expansions=1000,
        scope_hash=scope_hash,
        schema_hash=HASH,
        traversal_paths=(),
    )
    plan_hash = authorized_query_plan_sha256(plan)
    values = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": plan_hash,
        "records": [
            StructuredRecord(
                record_id=RECORD_ID,
                table_id=TABLE_ID,
                values=(StructuredFieldValue(field_id=FIELD_ID, value="阻塞"),),
            ).model_dump(mode="json"),
        ],
        "groups": [],
        "aggregates": [
            StructuredAggregate(
                aggregate_id="agg-count", group_key=None, value=1
            ).model_dump(mode="json"),
        ],
        "relation_paths": [],
        "source_versions": [
            {
                "table_id": str(TABLE_ID),
                "record_id": str(RECORD_ID),
                "record_version": 3,
            },
        ],
        "scope_hash": scope_hash,
        "schema_hash": HASH,
        "scanned_record_count": 1,
        "traversed_edge_count": 0,
        "truncated": truncated,
    }
    values["result_hash"] = structured_query_result_sha256(values)
    result = StructuredQueryResultV1.model_validate_json(json.dumps(values))
    return StructuredQueryArtifactV1(
        version="structured-query-artifact.v1",
        plan=plan,
        plan_hash=plan_hash,
        result=result,
    )


def _command(ref):
    payload = {
        "version": "objective-specialist-input.v1",
        "objective_id": "obj-01",
        "capability_id": "platform.tabular.analyse",
        "task_spec_ref": "task-spec:sha256:" + "b" * 64,
        "input_artifact_refs": (ref,),
        "scope_hash": HASH,
        "schema_hash": HASH,
        "data_version_hash": None,
    }
    payload["content_hash"] = specialist_payload_sha256(payload)
    return ObjectiveSpecialistInputV1.model_validate(payload)


def _context(ref, artifact):
    calls = []

    def read(value):
        calls.append(value)
        assert value == ref
        return artifact

    class Bomb:
        def __getattr__(self, name):
            raise AssertionError(f"tabular_must_not_call_{name}")

    return (
        SpecialistExecutionContextV2(
            artifact_reader=read,
            authorized_query_gateway=Bomb(),
            model_gateway=Bomb(),
            clock=lambda: datetime(2026, 7, 30, tzinfo=UTC),
            metrics=lambda _name, _value: None,
        ),
        calls,
    )


def test_tabular_handler_copies_deterministic_query_facts_without_provider() -> None:
    ref = uuid4()
    context, calls = _context(ref, _query_artifact())

    result = TabularSpecialistV2().execute(_command(ref), context)

    assert isinstance(result.payload, StructuredFactSetV1)
    assert result.payload.records[0].record_id == RECORD_ID
    assert result.payload.aggregates[0].value == 1
    assert result.payload.complete is True
    assert result.payload.truncated is False
    assert result.metrics == {"records": 1, "aggregates": 1, "provider_calls": 0}
    assert calls == [ref]


def test_tabular_handler_preserves_query_truncation_and_exact_aggregate() -> None:
    ref = uuid4()
    context, _calls = _context(ref, _query_artifact(truncated=True))

    result = TabularSpecialistV2().execute(_command(ref), context)

    assert result.payload.complete is False
    assert result.payload.truncated is True
    assert result.payload.aggregates[0].value == 1


def test_tabular_handler_rejects_scope_drift_before_fact_release() -> None:
    ref = uuid4()
    context, _calls = _context(ref, _query_artifact(scope_hash="c" * 64))

    with pytest.raises(ValueError, match="tabular_specialist_scope_mismatch"):
        TabularSpecialistV2().execute(_command(ref), context)
