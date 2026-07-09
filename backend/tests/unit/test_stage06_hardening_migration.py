from pathlib import Path
import re


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260710_0020_stage06_security_hardening.py"
)


def test_stage06_security_hardening_migration_has_expected_revision_chain() -> None:
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260710_0020"' in content
    assert 'down_revision = "20260709_0019"' in content


def test_stage06_security_hardening_migration_adds_required_guards() -> None:
    content = MIGRATION.read_text(encoding="utf-8")

    assert '"stage06_idempotency_records"' in content
    assert '"workspace_member_id"' in content
    assert "fk_stage06_binding_member" in content
    assert "fk_stage06_binding_employee" in content
    assert "uq_stage06_digital_employee_alias" in content
    assert "uq_stage06_active_telegram_binding" in content
    assert "ck_stage06_records_positive_version" in content
    assert "ck_stage06_drafts_positive_expected_version" in content
    assert "create_index" in content


def test_stage06_security_hardening_migration_is_additive() -> None:
    upgrade = MIGRATION.read_text(encoding="utf-8").split("def downgrade", 1)[0]

    assert "drop_table" not in upgrade
    assert "drop_column" not in upgrade


def test_stage06_security_hardening_identifiers_fit_postgres_limit() -> None:
    content = MIGRATION.read_text(encoding="utf-8")
    identifiers = re.findall(r'"((?:fk|uq|ix|ck|pk)_[a-z0-9_]+)"', content)

    assert identifiers
    assert {identifier for identifier in identifiers if len(identifier) > 63} == set()
