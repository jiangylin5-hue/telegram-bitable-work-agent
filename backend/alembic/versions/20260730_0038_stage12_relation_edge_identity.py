"""Bind Stage12 relation identity to endpoints and authority scope.

Revision ID: 20260730_0038
Revises: 20260730_0037
Create Date: 2026-07-30
"""

from __future__ import annotations

from alembic import op


revision = "20260730_0038"
down_revision = "20260730_0037"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "uq_s12_relation_version_visibility"


def upgrade() -> None:
    op.drop_constraint(
        CONSTRAINT_NAME,
        "stage12_relation_edges",
        type_="unique",
    )
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "stage12_relation_edges",
        [
            "workspace_id",
            "relation_id",
            "source_record_id",
            "target_record_id",
            "direction",
            "source_version",
            "target_version",
            "visibility_profile_hash",
            "scope_hash",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        CONSTRAINT_NAME,
        "stage12_relation_edges",
        type_="unique",
    )
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "stage12_relation_edges",
        [
            "workspace_id",
            "relation_id",
            "direction",
            "source_version",
            "target_version",
            "visibility_profile_hash",
        ],
    )
