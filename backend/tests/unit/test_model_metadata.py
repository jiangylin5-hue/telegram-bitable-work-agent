from app.models import metadata


CORE_TABLES = {
    "users",
    "telegram_identities",
    "customers",
    "customer_groups",
    "messages",
    "service_drafts",
    "service_records",
    "execution_tickets",
    "execution_logs",
    "collection_records",
    "recharge_records",
    "account_assets",
    "account_inventory",
    "account_assignments",
    "account_status_events",
    "account_daily_metrics",
    "risk_events",
    "customer_daily_reports",
    "company_daily_reports",
    "agent_runs",
    "table_views",
    "view_columns",
    "view_filters",
    "field_permissions",
    "automation_rules",
    "ops_audit_events",
    "outbox_events",
    "payment_profiles",
    "account_card_bindings",
}

FORBIDDEN_COLUMNS = {
    "tenant_id",
    "raw_card_number",
    "card_number",
    "cvv",
}


def test_core_tables_are_registered_in_metadata() -> None:
    assert CORE_TABLES.issubset(set(metadata.tables))


def test_stage_02_does_not_introduce_tenant_or_raw_payment_columns() -> None:
    for table in metadata.tables.values():
        column_names = {column.name for column in table.columns}

        assert column_names.isdisjoint(FORBIDDEN_COLUMNS), table.name
