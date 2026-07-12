"""Add bounded digital employee management persistence for Stage07 TD010."""

import sqlalchemy as sa
from alembic import op


revision = "20260713_0027"
down_revision = "20260713_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "digital_employees",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "digital_employees",
        sa.Column(
            "access_mode",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'workspace'"),
        ),
    )
    op.create_check_constraint(
        "ck_stage07_digital_employee_positive_version",
        "digital_employees",
        "version > 0",
    )
    op.create_check_constraint(
        "ck_stage07_digital_employee_access_mode",
        "digital_employees",
        "access_mode IN ('workspace', 'assigned')",
    )
    op.create_table(
        "digital_employee_member_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_member_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["employee_id"], ["digital_employees.id"]),
        sa.ForeignKeyConstraint(["workspace_member_id"], ["workspace_members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "workspace_member_id",
            name="uq_stage07_digital_employee_member_grant",
        ),
    )
    op.create_index(
        "ix_stage07_digital_employee_management_base_updated",
        "digital_employees",
        ["base_id", sa.text("updated_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage07_digital_employee_management_base_updated",
        table_name="digital_employees",
    )
    op.drop_table("digital_employee_member_grants")
    op.drop_constraint(
        "ck_stage07_digital_employee_access_mode",
        "digital_employees",
        type_="check",
    )
    op.drop_constraint(
        "ck_stage07_digital_employee_positive_version",
        "digital_employees",
        type_="check",
    )
    op.drop_column("digital_employees", "access_mode")
    op.drop_column("digital_employees", "version")
