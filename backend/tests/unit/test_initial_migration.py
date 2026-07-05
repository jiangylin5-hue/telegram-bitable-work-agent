from pathlib import Path
import re


CORE_TABLES = {
    "users",
    "customers",
    "customer_groups",
    "telegram_identities",
    "messages",
    "ops_audit_events",
    "outbox_events",
}


def test_initial_migration_creates_stage_02_core_tables() -> None:
    migration = Path("alembic/versions/20260704_0001_stage_02_core_tables.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for table_name in CORE_TABLES:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_service_draft_migration_creates_service_drafts_table() -> None:
    migration = Path("alembic/versions/20260704_0002_service_drafts.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    assert re.search(r'op\.create_table\(\s*"service_drafts"', source)


def test_recharge_flow_migration_creates_phase_4_tables() -> None:
    migration = Path("alembic/versions/20260704_0003_recharge_flow.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for table_name in {
        "service_records",
        "execution_tickets",
        "execution_logs",
        "collection_records",
        "recharge_records",
    }:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_account_inventory_migration_creates_phase_5_tables() -> None:
    migration = Path("alembic/versions/20260704_0004_account_inventory.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for table_name in {
        "account_assets",
        "account_inventory",
        "account_assignments",
        "account_status_events",
    }:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_reporting_migration_creates_phase_6_tables() -> None:
    migration = Path("alembic/versions/20260704_0005_reporting.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for table_name in {
        "account_daily_metrics",
        "risk_events",
        "customer_daily_reports",
        "company_daily_reports",
    }:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_llm_agent_run_migration_creates_phase_8_table() -> None:
    migration = Path("alembic/versions/20260704_0006_agent_runs.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    assert re.search(r'op\.create_table\(\s*"agent_runs"', source)
    for column_name in {
        "agent_name",
        "graph_name",
        "model_provider",
        "model_name",
        "prompt_version",
        "input_summary",
        "output_summary",
        "tool_calls",
        "status",
        "trace_id",
    }:
        assert re.search(rf'sa\.Column\("{column_name}"', source)


def test_bitable_config_migration_creates_view_tables() -> None:
    migration = Path("alembic/versions/20260704_0007_bitable_config.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for table_name in {
        "table_views",
        "view_columns",
        "view_filters",
        "field_permissions",
        "automation_rules",
    }:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)


def test_outbox_schema_alignment_migration_adds_plan_fields() -> None:
    migration = Path("alembic/versions/20260704_0008_outbox_schema_alignment.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for column_name in {
        "aggregate_type",
        "aggregate_id",
        "attempt_count",
        "available_at",
        "processed_at",
        "last_error",
    }:
        assert re.search(
            rf'op\.add_column\(\s*"outbox_events",\s*sa\.Column\(\s*"{column_name}"',
            source,
        )


def test_card_binding_migration_creates_tokenized_card_tables() -> None:
    migration = Path("alembic/versions/20260705_0009_card_binding_facts.py")

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for table_name in {
        "payment_profiles",
        "account_card_bindings",
    }:
        assert re.search(rf'op\.create_table\(\s*"{table_name}"', source)

    forbidden_terms = {"raw_card_number", "card_number", "cvv"}
    for forbidden in forbidden_terms:
        assert forbidden not in source
