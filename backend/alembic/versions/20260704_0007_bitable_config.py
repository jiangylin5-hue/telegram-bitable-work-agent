"""Create Bitable view configuration tables.

Revision ID: 20260704_0007
Revises: 20260704_0006
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0007"
down_revision: str | None = "20260704_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "table_views",
        sa.Column("view_key", sa.String(length=120), nullable=False),
        sa.Column("table_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_table_views"),
        sa.UniqueConstraint("view_key", name="uq_table_views_view_key"),
    )

    op.create_table(
        "view_columns",
        sa.Column("table_view_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("field_type", sa.String(length=60), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["table_view_id"],
            ["table_views.id"],
            name="fk_view_columns_table_view_id_table_views",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_view_columns"),
        sa.UniqueConstraint(
            "table_view_id",
            "field_name",
            name="uq_view_columns_view_field",
        ),
    )

    op.create_table(
        "view_filters",
        sa.Column("table_view_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("operator", sa.String(length=40), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["table_view_id"],
            ["table_views.id"],
            name="fk_view_filters_table_view_id_table_views",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_view_filters"),
    )

    op.create_table(
        "field_permissions",
        sa.Column("table_name", sa.String(length=120), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_field_permissions"),
        sa.UniqueConstraint(
            "table_name",
            "field_name",
            "role",
            name="uq_field_permissions_table_field_role",
        ),
    )

    op.create_table(
        "automation_rules",
        sa.Column("view_key", sa.String(length=120), nullable=False),
        sa.Column("trigger_event", sa.String(length=120), nullable=False),
        sa.Column("target_event_type", sa.String(length=120), nullable=False),
        sa.Column("rule_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_automation_rules"),
    )


def downgrade() -> None:
    op.drop_table("automation_rules")
    op.drop_table("field_permissions")
    op.drop_table("view_filters")
    op.drop_table("view_columns")
    op.drop_table("table_views")
