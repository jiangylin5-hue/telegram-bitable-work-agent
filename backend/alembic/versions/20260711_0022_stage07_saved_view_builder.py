"""Add V1 saved-view ownership and member-grant persistence."""

import sqlalchemy as sa
from alembic import op


revision = "20260711_0022"
down_revision = "20260710_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "views",
        sa.Column("owner_user_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "views",
        sa.Column(
            "scope",
            sa.String(length=40),
            nullable=False,
            server_default="system_default",
        ),
    )
    op.add_column(
        "views",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_table(
        "view_member_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("view_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("access_level", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["view_id"],
            ["views.id"],
            name=op.f("fk_view_member_grants_view_id_views"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_view_member_grants")),
        sa.UniqueConstraint(
            "view_id",
            "user_id",
            name="uq_view_member_grants_view_user",
        ),
    )


def downgrade() -> None:
    op.drop_table("view_member_grants")
    op.drop_column("views", "version")
    op.drop_column("views", "scope")
    op.drop_column("views", "owner_user_id")
