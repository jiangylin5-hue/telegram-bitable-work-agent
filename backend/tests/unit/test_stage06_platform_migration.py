from pathlib import Path
import re


STAGE06_CORE_TABLES = {
    "workspaces",
    "workspace_members",
    "stage06_telegram_bindings",
    "bases",
    "tables",
    "fields",
    "records",
    "record_links",
    "views",
    "forms",
}


def test_stage06_platform_core_migration_creates_generic_tables() -> None:
    migration = Path("alembic/versions/20260709_0017_stage06_platform_core.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    assert 'revision = "20260709_0017"' in source
    assert 'down_revision = "20260707_0016"' in source
    for table_name in STAGE06_CORE_TABLES:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_stage06_platform_core_migration_uses_jsonb_for_records_and_metadata() -> None:
    migration = Path("alembic/versions/20260709_0017_stage06_platform_core.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for column_name in {
        "settings",
        "scope_policy",
        "options",
        "permission_policy",
        "values",
        "config",
        "form_config",
    }:
        assert re.search(rf'sa\.Column\("{column_name}", postgresql\.JSONB\(', source)
