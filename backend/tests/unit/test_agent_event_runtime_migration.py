from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_agent_event_runtime_is_the_single_alembic_head() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))

    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260730_0039"]
    revision = script.get_revision("20260728_0034")
    assert revision is not None
    assert revision.down_revision == "20260723_0033"


def test_agent_event_runtime_migration_tolerates_optional_stage06_table() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    migration = (
        backend_root / "alembic" / "versions" / "20260728_0034_agent_event_runtime.py"
    ).read_text(encoding="utf-8")

    assert "to_regclass('stage06_idempotency_records') IS NOT NULL" in migration
    assert "ck_stage06_idempotency_records_ck_stage06_idempotency_status" in migration
    assert "DROP CONSTRAINT IF EXISTS ck_stage06_idempotency_status" in migration


def test_postgres_runtime_evidence_never_resets_the_shared_public_schema() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    integration_test = (
        backend_root / "tests" / "integration" / "test_agent_event_runtime_postgres.py"
    ).read_text(encoding="utf-8")

    assert "DROP SCHEMA public" not in integration_test
    assert "CREATE SCHEMA public" not in integration_test
