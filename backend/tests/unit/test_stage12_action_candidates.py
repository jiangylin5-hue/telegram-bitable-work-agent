from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import TypeAdapter

from app.schemas.agent_task_spec_v2 import (
    ActionSlotV1,
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    authorized_schema_sha256,
)
from app.schemas.authorized_query_plan import (
    StructuredQueryResultV1,
    structured_query_result_sha256,
)
from app.services.agent_action_candidates import resolve_action_candidates


WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("00000000-0000-4000-8000-000000000002")
TABLE_ID = UUID("00000000-0000-4000-8000-000000000003")
RECORD_ID = UUID("00000000-0000-4000-8000-000000000004")
FIELD_ID = UUID("00000000-0000-4000-8000-000000000005")
SCOPE_HASH = "a" * 64
SCHEMA_HASH = "b" * 64


def _snapshot(*, writable: bool = True) -> AuthorizedSchemaSnapshot:
    field = AuthorizedFieldSpec(
        field_id=FIELD_ID,
        table_id=TABLE_ID,
        key="status",
        name="状态",
        field_type="status",
        aliases=(),
        choices=("待处理", "完成"),
        writable=writable,
        default_value=None,
    )
    table = AuthorizedTableSpec(
        table_id=TABLE_ID,
        base_id=UUID("00000000-0000-4000-8000-000000000006"),
        key="tasks",
        name="任务",
        aliases=(),
        fields=(field,),
        identity_field_id=None,
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": SCOPE_HASH,
        "tables": (table,),
    }
    values["schema_hash"] = authorized_schema_sha256(**values)
    return AuthorizedSchemaSnapshot.model_validate(values)


def _result(*, records: bool = True, version: int = 3) -> StructuredQueryResultV1:
    values = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": "c" * 64,
        "records": (
            (
                {
                    "record_id": RECORD_ID,
                    "table_id": TABLE_ID,
                    "values": (),
                },
            )
            if records
            else ()
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (
            ({"table_id": TABLE_ID, "record_id": RECORD_ID, "record_version": version},)
            if records
            else ()
        ),
        "scope_hash": SCOPE_HASH,
        "schema_hash": _snapshot().schema_hash,
        "scanned_record_count": 1 if records else 0,
        "traversed_edge_count": 0,
        "truncated": False,
    }
    values["result_hash"] = structured_query_result_sha256(
        TypeAdapter(dict[str, object]).dump_python(values, mode="json")
    )
    return StructuredQueryResultV1.model_validate(values)


def _slot(action_kind: str = "record.update") -> ActionSlotV1:
    return ActionSlotV1.model_validate(
        {
            "slot_id": "act-01",
            "objective_id": "obj-01",
            "action_kind": action_kind,
            "target": {
                "table_id": TABLE_ID,
                "record_codes": (),
                "source_entity_codes": (),
                "resolution_status": (
                    "deferred_query_result"
                    if action_kind == "record.update"
                    else "resolved"
                ),
                "query_spec_ref": (
                    "query:obj-00" if action_kind == "record.update" else None
                ),
                "expansion_policy": (
                    "each_result" if action_kind == "record.update" else "none"
                ),
            },
            "assignments": (
                {
                    "field_id": FIELD_ID,
                    "field_key": "status",
                    "value": "完成",
                    "source_span": {"start": 0, "end": 2, "text": "完成"},
                },
            ),
            "required_field_keys": ("status",),
            "confirmation_policy": "required",
            "deadline_start_utc": None,
            "deadline_end_utc": None,
            "conflict_group_id": None,
            "planning_outcome": "planned",
            "denial_reason": None,
        }
    )


def test_deferred_update_expands_from_structured_result_with_versions() -> None:
    resolution = resolve_action_candidates(
        _slot(),
        snapshot=_snapshot(),
        query_result=_result(),
    )

    assert resolution.status == "resolved"
    assert resolution.target_table_ids == (TABLE_ID,)
    assert resolution.candidates[0].record_id == RECORD_ID
    assert resolution.candidates[0].record_version == 3
    assert resolution.candidates[0].writable_field_ids == (FIELD_ID,)


def test_empty_candidate_is_a_local_denial() -> None:
    resolution = resolve_action_candidates(
        _slot(),
        snapshot=_snapshot(),
        query_result=_result(records=False),
    )

    assert resolution.status == "denied"
    assert resolution.denial_reason == "action_candidate_empty"


def test_unwritable_assignment_is_denied_before_provider() -> None:
    resolution = resolve_action_candidates(
        _slot(),
        snapshot=_snapshot(writable=False),
        query_result=_result(),
    )

    assert resolution.status == "denied"
    assert resolution.denial_reason == "action_field_not_writable"


@pytest.mark.parametrize("kind", ["record.create", "task.create"])
def test_create_actions_resolve_authorized_table_without_fake_record(kind: str) -> None:
    resolution = resolve_action_candidates(
        _slot(kind),
        snapshot=_snapshot(),
        query_result=None,
    )

    assert resolution.status == "resolved"
    assert resolution.target_table_ids == (TABLE_ID,)
    assert resolution.candidates == ()


def test_scope_or_schema_drift_is_fail_closed() -> None:
    result = _result()
    object.__setattr__(result, "scope_hash", "d" * 64)

    with pytest.raises(ValueError, match="action_candidate_scope_mismatch"):
        resolve_action_candidates(_slot(), snapshot=_snapshot(), query_result=result)
