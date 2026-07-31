"""Add durable authorized Retrieval V2 scope registrations.

Revision ID: 20260730_0039
Revises: 20260730_0038
Create Date: 2026-07-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv


revision = "20260730_0039"
down_revision = "20260730_0038"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "stage12_retrieval_scope_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("base_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("actor_role_hash", sa.String(length=64), nullable=False),
        sa.Column("member_version", sa.Integer(), nullable=False),
        sa.Column("employee_version", sa.Integer(), nullable=False),
        sa.Column(
            "scope_view_ids",
            postgresql.ARRAY(sa.Uuid()),
            nullable=False,
        ),
        sa.Column("allow_whole_table", sa.Boolean(), nullable=False),
        sa.Column("schema_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieval_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_hash", sa.String(length=64), nullable=False),
        sa.Column("field_policy_version", sa.String(length=64), nullable=False),
        sa.Column("field_policy_hash", sa.String(length=64), nullable=False),
        sa.Column("registration_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "actor_type = 'user' AND char_length(btrim(actor_id)) > 0",
            name=conv("ck_s12_registration_actor"),
        ),
        sa.CheckConstraint(
            "employee_version > 0 AND member_version > 0",
            name=conv("ck_s12_registration_versions"),
        ),
        sa.CheckConstraint(
            "field_policy_version = 'stage12-field-policy.v2'",
            name=conv("ck_s12_registration_policy_version"),
        ),
        sa.CheckConstraint(
            "(allow_whole_table AND cardinality(scope_view_ids) = 0) OR "
            "(NOT allow_whole_table AND cardinality(scope_view_ids) > 0)",
            name=conv("ck_s12_registration_scope_boundary"),
        ),
        sa.CheckConstraint(
            "cardinality(scope_view_ids) <= 128",
            name=conv("ck_s12_registration_view_budget"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name=conv("ck_s12_registration_status"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND revoked_at IS NULL) OR "
            "(status = 'revoked' AND revoked_at IS NOT NULL)",
            name=conv("ck_s12_registration_lifecycle"),
        ),
        sa.CheckConstraint(
            "expires_at > last_seen_at",
            name=conv("ck_s12_registration_expiry"),
        ),
        sa.CheckConstraint(
            "schema_scope_hash ~ '^[0-9a-f]{64}$' AND "
            "retrieval_scope_hash ~ '^[0-9a-f]{64}$' AND "
            "schema_hash ~ '^[0-9a-f]{64}$' AND "
            "field_policy_hash ~ '^[0-9a-f]{64}$' AND "
            "actor_role_hash ~ '^[0-9a-f]{64}$' AND "
            "registration_hash ~ '^[0-9a-f]{64}$'",
            name=conv("ck_s12_registration_hashes"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["base_id"], ["bases.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["digital_employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_s12_registration_active_identity",
        "stage12_retrieval_scope_registrations",
        [
            "workspace_id",
            "employee_id",
            "actor_type",
            "actor_id",
            "retrieval_scope_hash",
        ],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND revoked_at IS NULL"),
    )
    op.create_index(
        "ix_s12_registration_workspace_lifecycle",
        "stage12_retrieval_scope_registrations",
        ["workspace_id", "status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_s12_registration_workspace_lifecycle",
        table_name="stage12_retrieval_scope_registrations",
    )
    op.drop_index(
        "uq_s12_registration_active_identity",
        table_name="stage12_retrieval_scope_registrations",
    )
    op.drop_table("stage12_retrieval_scope_registrations")
