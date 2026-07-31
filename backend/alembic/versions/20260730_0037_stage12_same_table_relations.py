"""Allow distinct Stage12 relation records in the same table.

Revision ID: 20260730_0037
Revises: 20260730_0036
Create Date: 2026-07-30
"""

from __future__ import annotations

from alembic import op
from sqlalchemy.sql.naming import conv


revision = "20260730_0037"
down_revision = "20260730_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        conv("ck_s12_relation_endpoints"),
        "stage12_relation_edges",
        type_="check",
    )
    op.create_check_constraint(
        conv("ck_s12_relation_endpoints"),
        "stage12_relation_edges",
        "source_record_id <> target_record_id",
    )


def downgrade() -> None:
    op.drop_constraint(
        conv("ck_s12_relation_endpoints"),
        "stage12_relation_edges",
        type_="check",
    )
    op.create_check_constraint(
        conv("ck_s12_relation_endpoints"),
        "stage12_relation_edges",
        "source_table_id <> target_table_id "
        "AND source_record_id <> target_record_id",
    )
