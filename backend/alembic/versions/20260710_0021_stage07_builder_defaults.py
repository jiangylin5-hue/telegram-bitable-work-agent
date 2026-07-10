"""Add the Stage07 Builder default-view invariant."""

import sqlalchemy as sa
from alembic import op


revision = "20260710_0021"
down_revision = "20260710_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_views_one_default_per_table",
        "views",
        ["table_id"],
        unique=True,
        postgresql_where=sa.text("is_default IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_views_one_default_per_table", table_name="views")
