"""Add revisions for Stage07 governance-write commands."""

import sqlalchemy as sa
from alembic import op


revision = "20260712_0023"
down_revision = "20260711_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_members",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "fields",
        sa.Column(
            "permission_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("fields", "permission_version")
    op.drop_column("workspace_members", "version")
