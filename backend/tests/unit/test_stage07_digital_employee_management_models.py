from pathlib import Path
from uuid import uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models import metadata
from app.models.stage06_runtime import (
    DigitalEmployee,
    DigitalEmployeeMemberGrant,
)
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260713_0027_stage07_digital_employee_management.py"
)


def test_managed_employee_metadata_has_closed_revision_and_access_mode() -> None:
    table = DigitalEmployee.__table__

    assert table.c.version.default is not None
    assert table.c.version.default.arg == 1
    assert table.c.access_mode.default is not None
    assert table.c.access_mode.default.arg == "workspace"
    assert table.c.access_mode.type.length == 20
    assert any(
        isinstance(constraint, CheckConstraint)
        and "version > 0" in str(constraint.sqltext)
        for constraint in table.constraints
    )
    assert any(
        isinstance(constraint, CheckConstraint)
        and "access_mode IN ('workspace', 'assigned')" in str(constraint.sqltext)
        for constraint in table.constraints
    )


def test_member_grant_metadata_prevents_duplicate_employee_member_pairs() -> None:
    table = DigitalEmployeeMemberGrant.__table__

    assert table.name in metadata.tables
    assert {"employee_id", "workspace_member_id", "created_at", "updated_at"}.issubset(
        table.c.keys()
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns)
        == ("employee_id", "workspace_member_id")
        for constraint in table.constraints
    )


def test_in_memory_uow_replaces_grants_as_one_employee_owned_set() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    first = DigitalEmployeeMemberGrant()
    second = DigitalEmployeeMemberGrant()
    employee_id = uuid4()
    first.employee_id = second.employee_id = employee_id

    uow.add_digital_employee_member_grant(first)
    uow.replace_digital_employee_member_grants(employee_id, [second])

    assert uow.list_digital_employee_member_grants(employee_id) == [second]


def test_management_migration_is_additive_and_has_directory_index() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260713_0027"' in source
    assert 'down_revision = "20260713_0026"' in source
    assert '"digital_employee_member_grants"' in source
    assert '"version"' in source
    assert '"access_mode"' in source
    assert "ck_stage07_digital_employee_positive_version" in source
    assert "ck_stage07_digital_employee_access_mode" in source
    assert "uq_stage07_digital_employee_member_grant" in source
    assert "ix_stage07_digital_employee_management_base_updated" in source
    assert "drop_table(\"digital_employee_member_grants\")" in source
