"""Add Stage 06 generic platform core tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260709_0017"
down_revision = "20260707_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("owner_user_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_workspace_members_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_members")),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )
    op.create_table(
        "bases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_bases_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bases")),
    )
    op.create_table(
        "stage06_telegram_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=120), nullable=True),
        sa.Column("telegram_user_id", sa.String(length=120), nullable=True),
        sa.Column("binding_type", sa.String(length=40), nullable=False),
        sa.Column("default_base_id", sa.Uuid(), nullable=True),
        sa.Column("default_digital_employee_id", sa.Uuid(), nullable=True),
        sa.Column("scope_policy", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["default_base_id"], ["bases.id"], name=op.f("fk_stage06_telegram_bindings_default_base_id_bases")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_stage06_telegram_bindings_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage06_telegram_bindings")),
    )
    op.create_table(
        "tables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("primary_field_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"], name=op.f("fk_tables_base_id_bases")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tables")),
        sa.UniqueConstraint("base_id", "key", name="uq_tables_base_key"),
    )
    op.create_table(
        "fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=40), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("unique", sa.Boolean(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("default_value", postgresql.JSONB(), nullable=True),
        sa.Column("permission_policy", postgresql.JSONB(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"], name=op.f("fk_fields_table_id_tables")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fields")),
        sa.UniqueConstraint("table_id", "key", name="uq_fields_table_key"),
    )
    op.create_table(
        "records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("values", postgresql.JSONB(), nullable=False),
        sa.Column("record_status", sa.String(length=40), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=120), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=120), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"], name=op.f("fk_records_table_id_tables")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_records")),
    )
    op.create_table(
        "record_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_table_id", sa.Uuid(), nullable=False),
        sa.Column("source_record_id", sa.Uuid(), nullable=False),
        sa.Column("source_field_id", sa.Uuid(), nullable=False),
        sa.Column("target_table_id", sa.Uuid(), nullable=False),
        sa.Column("target_record_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_field_id"], ["fields.id"], name=op.f("fk_record_links_source_field_id_fields")),
        sa.ForeignKeyConstraint(["source_record_id"], ["records.id"], name=op.f("fk_record_links_source_record_id_records")),
        sa.ForeignKeyConstraint(["source_table_id"], ["tables.id"], name=op.f("fk_record_links_source_table_id_tables")),
        sa.ForeignKeyConstraint(["target_record_id"], ["records.id"], name=op.f("fk_record_links_target_record_id_records")),
        sa.ForeignKeyConstraint(["target_table_id"], ["tables.id"], name=op.f("fk_record_links_target_table_id_tables")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_links")),
    )
    op.create_table(
        "views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("view_type", sa.String(length=40), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("permission_policy", postgresql.JSONB(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"], name=op.f("fk_views_base_id_bases")),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"], name=op.f("fk_views_table_id_tables")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_views")),
    )
    op.create_table(
        "forms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("view_id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("form_config", postgresql.JSONB(), nullable=False),
        sa.Column("submit_policy", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"], name=op.f("fk_forms_table_id_tables")),
        sa.ForeignKeyConstraint(["view_id"], ["views.id"], name=op.f("fk_forms_view_id_views")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forms")),
    )


def downgrade() -> None:
    op.drop_table("forms")
    op.drop_table("views")
    op.drop_table("record_links")
    op.drop_table("records")
    op.drop_table("fields")
    op.drop_table("tables")
    op.drop_table("stage06_telegram_bindings")
    op.drop_table("bases")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
