from __future__ import annotations

import pytest

from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    can_actor_write_record_fields,
    get_table_schema,
    update_record,
)
from scripts.stage12_evaluation_fixture import (
    materialize_stage12_evaluation_fixture,
    snapshot_materialized_fixture,
)
from scripts.stage12_quality_evaluation import _fixture_snapshot, canonical_sha256


def test_materializer_builds_the_schema_relations_acl_profile_and_versions_it_hashes() -> (
    None
):
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage12-eval-owner", role="owner")
    fixture = materialize_stage12_evaluation_fixture(
        uow,
        actor,
    )

    tables = {table.key: table for table in uow.list_tables(fixture.base_id)}
    assert set(tables) == {
        "projects",
        "work_items",
        "risks",
        "tasks",
        "owners",
        "daily_metrics",
        "interactions",
    }
    task_fields = {field.key: field for field in uow.list_fields(tables["tasks"].id)}
    assert task_fields["due_date"].field_type == "date"
    assert task_fields["assignee"].field_type == "linked_record"
    work_fields = {
        field.key: field for field in uow.list_fields(tables["work_items"].id)
    }
    assert work_fields["owner_link"].field_type == "linked_record"
    assert work_fields["internal_note"].field_type == "text"
    assert work_fields["status"].options["choices"] == [
        "planned",
        "in_progress",
        "done",
        "blocked",
    ]
    assert work_fields["priority"].options["choices"] == [
        "high",
        "medium",
        "low",
    ]
    project_schema = get_table_schema(uow, tables["projects"].id, actor=actor)
    assert "customer_secret" not in {item["key"] for item in project_schema["fields"]}
    assert not can_actor_write_record_fields(
        uow,
        tables["work_items"].id,
        ("blocked_reason",),
        actor=actor,
    )
    assert not can_actor_write_record_fields(
        uow,
        tables["work_items"].id,
        ("internal_note",),
        actor=actor,
    )

    materialized = snapshot_materialized_fixture(fixture)

    assert materialized == _fixture_snapshot()
    assert canonical_sha256(materialized) == canonical_sha256(_fixture_snapshot())
    assert materialized["permission_profile"]["outside_workspace"] == "denied"


def test_materialized_snapshot_rejects_record_or_version_drift() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage12-eval-owner", role="owner")
    fixture = materialize_stage12_evaluation_fixture(uow, actor)
    project_id = fixture.core.project_record_ids["PRJ-ATLAS"]
    project = uow.get_record(project_id)
    assert project is not None
    update_record(
        uow,
        project_id,
        values={"project_name": "Tampered"},
        expected_version=project.version,
        actor=actor,
    )

    with pytest.raises(ValueError, match="evaluation_materialized_record_mismatch"):
        snapshot_materialized_fixture(fixture)
