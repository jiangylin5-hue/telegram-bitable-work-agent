from pathlib import Path
import re


STAGE06_TEMPLATE_IMPORT_TABLES = {
    "templates",
    "template_installations",
    "import_jobs",
}


def test_stage06_template_import_migration_creates_package3_tables() -> None:
    migration = Path("alembic/versions/20260709_0018_stage06_template_import.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    assert 'revision = "20260709_0018"' in source
    assert 'down_revision = "20260709_0017"' in source
    for table_name in STAGE06_TEMPLATE_IMPORT_TABLES:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_stage06_template_import_migration_uses_jsonb_for_manifests_and_preview() -> None:
    migration = Path("alembic/versions/20260709_0018_stage06_template_import.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for column_name in {
        "manifest",
        "resource_map",
        "file_ref",
        "detected_schema",
        "preview_rows",
        "mapping",
    }:
        assert re.search(rf'sa\.Column\("{column_name}", postgresql\.JSONB\(', source)
