from pathlib import Path
import re


STAGE06_RUNTIME_TABLES = {
    "digital_employees",
    "record_change_drafts",
    "notification_requests",
}


def test_stage06_digital_employee_migration_creates_runtime_tables() -> None:
    migration = Path("alembic/versions/20260709_0019_stage06_digital_employee_runtime.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    assert 'revision = "20260709_0019"' in source
    assert 'down_revision = "20260709_0018"' in source
    for table_name in STAGE06_RUNTIME_TABLES:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_stage06_digital_employee_migration_uses_jsonb_for_scope_and_drafts() -> None:
    migration = Path("alembic/versions/20260709_0019_stage06_digital_employee_runtime.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for column_name in {
        "accessible_tables",
        "accessible_views",
        "field_policy",
        "allowed_actions",
        "confirmation_policy",
        "response_style",
        "proposed_values",
        "before_values",
        "target",
        "message_payload",
        "send_policy",
    }:
        assert re.search(rf'sa\.Column\("{column_name}", postgresql\.JSONB\(', source)
