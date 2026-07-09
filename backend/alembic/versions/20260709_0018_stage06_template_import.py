"""Add Stage 06 template and import tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260709_0018"
down_revision = "20260709_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_templates")),
    )
    op.create_table(
        "template_installations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("template_version", sa.String(length=40), nullable=False),
        sa.Column("resource_map", postgresql.JSONB(), nullable=False),
        sa.Column("installed_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"], name=op.f("fk_template_installations_base_id_bases")),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], name=op.f("fk_template_installations_template_id_templates")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_template_installations_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_template_installations")),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("file_ref", postgresql.JSONB(), nullable=False),
        sa.Column("detected_schema", postgresql.JSONB(), nullable=False),
        sa.Column("preview_rows", postgresql.JSONB(), nullable=False),
        sa.Column("mapping", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"], name=op.f("fk_import_jobs_base_id_bases")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_import_jobs_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
    )


def downgrade() -> None:
    op.drop_table("import_jobs")
    op.drop_table("template_installations")
    op.drop_table("templates")
