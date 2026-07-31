"""Executable isolated fixture for Stage12 Evaluation V2.

The same service-layer materializer works with the in-memory and PostgreSQL UOWs.
It performs no external sends and creates only fictional evaluation data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.services.permissions import Actor
from app.services.stage06_platform import (
    Stage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    can_actor_write_record_fields,
    get_table_schema,
)
from scripts.stage09_multitable_chinese_eval import (
    MultiTableFixture,
    _PROJECT_ROWS,
    _RISK_ROWS,
    _WORK_ITEM_ROWS,
)
from scripts.stage12_quality_evaluation import _fixture_snapshot


@dataclass(frozen=True)
class Stage12EvaluationFixture:
    uow: Stage06PlatformUnitOfWork
    actor: Actor
    core: MultiTableFixture
    base_id: UUID
    table_ids: dict[str, UUID]
    owner_record_ids: dict[str, UUID]


def _add_field(
    uow: Stage06PlatformUnitOfWork,
    table_id: UUID,
    *,
    key: str,
    field_type: str,
    actor: Actor,
    target_table_id: UUID | None = None,
    default: object | None = None,
    choices: tuple[str, ...] = (),
    permission_policy: dict[str, object] | None = None,
) -> None:
    options: dict[str, Any] = {}
    if target_table_id is not None:
        options["target_table_id"] = str(target_table_id)
    if default is not None:
        options["default"] = default
    if choices:
        options["choices"] = list(choices)
    create_field(
        uow,
        table_id,
        name=key.replace("_", " ").title(),
        key=key,
        field_type=field_type,
        options=options,
        permission_policy=permission_policy,
        actor=actor,
    )


def materialize_stage12_evaluation_fixture(
    uow: Stage06PlatformUnitOfWork,
    actor: Actor,
    *,
    workspace_name: str = "Stage12 Quality Architecture V2 Evaluation",
) -> Stage12EvaluationFixture:
    workspace = create_workspace(
        uow,
        name=workspace_name,
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(
        uow,
        workspace.id,
        name="Stage12 Evaluation Fixture",
        actor=actor,
    )
    tables = {
        key: create_table(uow, base.id, name=name, key=key, actor=actor)
        for key, name in (
            ("projects", "Projects"),
            ("work_items", "Work Items"),
            ("risks", "Risks"),
            ("tasks", "Tasks"),
            ("owners", "Owners"),
            ("daily_metrics", "Daily Metrics"),
            ("interactions", "Interactions"),
        )
    }
    projects = tables["projects"]
    work_items = tables["work_items"]
    risks = tables["risks"]
    tasks = tables["tasks"]
    owners = tables["owners"]
    daily = tables["daily_metrics"]
    interactions = tables["interactions"]

    for key, field_type in (
        ("owner_code", "text"),
        ("name", "text"),
    ):
        _add_field(uow, owners.id, key=key, field_type=field_type, actor=actor)

    for key, field_type in (
        ("project_code", "text"),
        ("project_name", "text"),
        ("phase", "text"),
        ("delivery_state", "text"),
    ):
        _add_field(uow, projects.id, key=key, field_type=field_type, actor=actor)
    _add_field(
        uow,
        projects.id,
        key="owner_link",
        field_type="linked_record",
        target_table_id=owners.id,
        actor=actor,
    )
    _add_field(
        uow,
        projects.id,
        key="customer_secret",
        field_type="text",
        permission_policy={"default": "hidden", "owner": "hidden"},
        actor=actor,
    )

    for key, field_type, choices in (
        ("ticket_code", "text", ()),
        ("title", "text", ()),
        ("project_code", "text", ()),
        ("status", "status", ("planned", "in_progress", "done", "blocked")),
        ("priority", "single_select", ("high", "medium", "low")),
        ("risk_level", "single_select", ("high", "medium", "low")),
        ("summary", "text", ()),
    ):
        _add_field(
            uow,
            work_items.id,
            key=key,
            field_type=field_type,
            choices=choices,
            actor=actor,
        )
    for key, target_table_id in (
        ("project_link", projects.id),
        ("owner_link", owners.id),
    ):
        _add_field(
            uow,
            work_items.id,
            key=key,
            field_type="linked_record",
            target_table_id=target_table_id,
            actor=actor,
        )
    _add_field(
        uow,
        work_items.id,
        key="blocked_reason",
        field_type="text",
        permission_policy={"default": "read", "owner": "read"},
        actor=actor,
    )
    _add_field(
        uow,
        work_items.id,
        key="internal_note",
        field_type="text",
        permission_policy={"default": "hidden", "owner": "hidden"},
        actor=actor,
    )

    for key, field_type, choices in (
        ("risk_code", "text", ()),
        ("title", "text", ()),
        ("level", "single_select", ("high", "medium", "low")),
        ("status", "status", ("open", "monitoring")),
        ("ticket_code", "text", ()),
    ):
        _add_field(
            uow,
            risks.id,
            key=key,
            field_type=field_type,
            choices=choices,
            actor=actor,
        )
    _add_field(
        uow,
        risks.id,
        key="affected_work_items",
        field_type="linked_record",
        target_table_id=work_items.id,
        actor=actor,
    )

    entity_fields = {
        "projects": ("project_code", "project_name"),
        "work_items": ("ticket_code", "title"),
        "risks": ("risk_code", "title"),
        "owners": ("owner_code", "name"),
        "daily_metrics": ("date", "date"),
        "interactions": ("interaction_code", "interaction_code"),
    }
    for table_key, (identity_key, label_key) in entity_fields.items():
        table = tables[table_key]
        table.settings = {
            **(table.settings or {}),
            "identity_field_key": identity_key,
            "entity_label_field_key": label_key,
            "entity_alias_field_keys": [],
        }

    owner_record_ids = {
        code: create_record(
            uow,
            owners.id,
            values={"owner_code": code, "name": f"{project.title()} owner"},
            actor=actor,
        ).id
        for project, code in (
            ("atlas", "OWNER-ATLAS"),
            ("beacon", "OWNER-BEACON"),
            ("cedar", "OWNER-CEDAR"),
            ("delta", "OWNER-DELTA"),
            ("ember", "OWNER-EMBER"),
            ("fjord", "OWNER-FJORD"),
        )
    }
    owner_by_project = {
        row["project_code"]: owner_record_ids[f"OWNER-{row['project_name'].upper()}"]
        for row in _PROJECT_ROWS
    }
    project_record_ids = {
        row["project_code"]: create_record(
            uow,
            projects.id,
            values={
                **row,
                "owner_link": [str(owner_by_project[row["project_code"]])],
            },
            actor=actor,
        ).id
        for row in _PROJECT_ROWS
    }
    work_item_project_record_ids = {
        row["ticket_code"]: project_record_ids[row["project_code"]]
        for row in _WORK_ITEM_ROWS
    }
    work_item_record_ids = {
        row["ticket_code"]: create_record(
            uow,
            work_items.id,
            values={
                **row,
                "project_link": [str(project_record_ids[row["project_code"]])],
                "owner_link": [str(owner_by_project[row["project_code"]])],
            },
            actor=actor,
        ).id
        for row in _WORK_ITEM_ROWS
    }
    risk_work_item_record_ids = {
        row["risk_code"]: work_item_record_ids[row["ticket_code"]] for row in _RISK_ROWS
    }
    risk_record_ids = {
        row["risk_code"]: create_record(
            uow,
            risks.id,
            values={
                **row,
                "affected_work_items": [str(work_item_record_ids[row["ticket_code"]])],
            },
            actor=actor,
        ).id
        for row in _RISK_ROWS
    }

    for key, field_type, target, default, choices in (
        ("title", "text", None, None, ()),
        ("priority", "single_select", None, "medium", ("high", "medium", "low")),
        ("status", "status", None, "planned", ("planned", "done")),
        ("project_link", "linked_record", projects.id, None, ()),
        ("source_work_item", "linked_record", work_items.id, None, ()),
        ("assignee", "linked_record", owners.id, None, ()),
        ("due_date", "date", None, None, ()),
    ):
        _add_field(
            uow,
            tasks.id,
            key=key,
            field_type=field_type,
            target_table_id=target,
            default=default,
            choices=choices,
            actor=actor,
        )

    for key, field_type in (
        ("date", "date"),
        ("completed", "number"),
        ("blocked", "number"),
        ("overdue", "number"),
    ):
        _add_field(uow, daily.id, key=key, field_type=field_type, actor=actor)
    create_record(
        uow,
        daily.id,
        values={"date": "2026-07-28", "completed": 5, "blocked": 4, "overdue": 3},
        actor=actor,
    )

    _add_field(
        uow, interactions.id, key="interaction_code", field_type="text", actor=actor
    )
    _add_field(
        uow,
        interactions.id,
        key="sentiment",
        field_type="single_select",
        choices=("positive", "neutral", "negative"),
        actor=actor,
    )
    create_record(
        uow,
        interactions.id,
        values={"interaction_code": "INT-001", "sentiment": "negative"},
        actor=actor,
    )

    core = MultiTableFixture(
        uow=uow,
        workspace_id=workspace.id,
        base_id=base.id,
        project_table_id=projects.id,
        work_item_table_id=work_items.id,
        risk_table_id=risks.id,
        project_record_ids=project_record_ids,
        work_item_record_ids=work_item_record_ids,
        risk_record_ids=risk_record_ids,
        work_item_project_record_ids=work_item_project_record_ids,
        risk_work_item_record_ids=risk_work_item_record_ids,
    )
    table_ids = {table.key: table.id for table in uow.list_tables(base.id)}
    return Stage12EvaluationFixture(
        uow=uow,
        actor=actor,
        core=core,
        base_id=base.id,
        table_ids=table_ids,
        owner_record_ids=owner_record_ids,
    )


def snapshot_materialized_fixture(
    fixture: Stage12EvaluationFixture,
) -> dict[str, object]:
    expected = _fixture_snapshot()
    uow = fixture.uow
    tables = {table.key: table for table in uow.list_tables(fixture.base_id)}
    if set(tables) != set(expected["tables"]):
        raise ValueError("evaluation_materialized_tables_mismatch")
    for table_key, expected_table in expected["tables"].items():
        actual_fields = {
            field.key: field for field in uow.list_fields(tables[table_key].id)
        }
        expected_fields = {field["key"]: field for field in expected_table["fields"]}
        if set(actual_fields) != set(expected_fields):
            raise ValueError("evaluation_materialized_fields_mismatch")
        for field_key, field_spec in expected_fields.items():
            actual = actual_fields[field_key]
            if actual.field_type != field_spec["type"]:
                raise ValueError("evaluation_materialized_field_type_mismatch")
            target_key = field_spec.get("target")
            if target_key is not None and actual.options.get("target_table_id") != str(
                tables[target_key].id
            ):
                raise ValueError("evaluation_materialized_field_target_mismatch")
            if (
                "default" in field_spec
                and actual.options.get("default") != field_spec["default"]
            ):
                raise ValueError("evaluation_materialized_field_default_mismatch")
            visibility = field_spec.get("visibility")
            if visibility == "hidden":
                visible_keys = {
                    item["key"]
                    for item in get_table_schema(
                        uow,
                        tables[table_key].id,
                        actor=fixture.actor,
                    )["fields"]
                }
                if field_key in visible_keys:
                    raise ValueError(
                        "evaluation_materialized_field_permission_mismatch"
                    )

    identity_fields = {
        "projects": "project_code",
        "work_items": "ticket_code",
        "risks": "risk_code",
        "owners": "owner_code",
        "daily_metrics": "date",
        "interactions": "interaction_code",
    }
    code_by_record_id: dict[UUID, str] = {}
    actual_versions: dict[str, int] = {}
    for table_key, expected_table in expected["tables"].items():
        actual_records = uow.list_records(tables[table_key].id)
        expected_records = tuple(expected_table["records"])
        if len(actual_records) != len(expected_records):
            raise ValueError("evaluation_materialized_record_count_mismatch")
        if not expected_records:
            continue
        identity_field = identity_fields[table_key]
        expected_by_identity = {
            str(row[identity_field]): row for row in expected_records
        }
        actual_by_identity = {
            str(record.values.get(identity_field)): record for record in actual_records
        }
        if set(actual_by_identity) != set(expected_by_identity):
            raise ValueError("evaluation_materialized_record_identity_mismatch")
        for identity, expected_row in expected_by_identity.items():
            record = actual_by_identity[identity]
            if any(
                record.values.get(key) != value for key, value in expected_row.items()
            ):
                raise ValueError("evaluation_materialized_record_mismatch")
            code = f"DAILY-{identity}" if table_key == "daily_metrics" else identity
            code_by_record_id[record.id] = code
            actual_versions[code] = record.version

    expected_relations = {
        (item["source"], item["field"], item["target"])
        for item in expected["relations"]
    }
    fields_by_id = {
        field.id: f"{table_key}.{field.key}"
        for table_key, table in tables.items()
        for field in uow.list_fields(table.id)
    }
    actual_relations: set[tuple[str, str, str]] = set()
    for target_record_id, target_code in code_by_record_id.items():
        for link in uow.list_record_links_to(target_record_id):
            source_code = code_by_record_id.get(link.source_record_id)
            field_code = fields_by_id.get(link.source_field_id)
            if source_code is None or field_code is None:
                raise ValueError("evaluation_materialized_relation_unknown")
            actual_relations.add((source_code, field_code, target_code))
    if actual_relations != expected_relations:
        raise ValueError("evaluation_materialized_relation_mismatch")

    if actual_versions != expected["record_versions"]:
        raise ValueError("evaluation_materialized_record_version_mismatch")

    permission_profile = expected["permission_profile"]
    for qualified_key in permission_profile["hidden_fields"]:
        table_key, field_key = qualified_key.split(".", 1)
        visible_keys = {
            item["key"]
            for item in get_table_schema(
                uow,
                tables[table_key].id,
                actor=fixture.actor,
            )["fields"]
        }
        if field_key in visible_keys:
            raise ValueError("evaluation_materialized_field_permission_mismatch")
    for qualified_key in permission_profile["denied_write_fields"]:
        table_key, field_key = qualified_key.split(".", 1)
        if can_actor_write_record_fields(
            uow,
            tables[table_key].id,
            (field_key,),
            actor=fixture.actor,
        ):
            raise ValueError("evaluation_materialized_field_permission_mismatch")
    return expected


__all__ = [
    "Stage12EvaluationFixture",
    "materialize_stage12_evaluation_fixture",
    "snapshot_materialized_fixture",
]
