"""Add Stage12-F durable objective and action state.

Revision ID: 20260730_0036
Revises: 20260729_0035
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260730_0036"
down_revision = "20260729_0035"
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
        "agent_objective_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("objective_key", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dependency_keys", postgresql.JSONB(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=True),
        sa.Column("result_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','proposed','denied',"
            "'degraded','failed','cancelled')",
            name="ck_agent_objective_runs_agent_objective_run_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(dependency_keys) = 'array'",
            name="ck_agent_objective_runs_agent_objective_dependency_array",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_workflow_runs.id"]),
        sa.ForeignKeyConstraint(["command_id"], ["agent_commands.id"]),
        sa.ForeignKeyConstraint(["result_artifact_id"], ["agent_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "objective_key", name="uq_agent_objective_run_key"
        ),
    )
    op.create_index(
        "ix_agent_objective_run_status",
        "agent_objective_runs",
        ["run_id", "status"],
    )

    op.create_table(
        "agent_action_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("objective_run_id", sa.Uuid(), nullable=False),
        sa.Column("slot_key", sa.String(length=80), nullable=False),
        sa.Column("action_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("control_json", postgresql.JSONB(), nullable=False),
        sa.Column("private_payload_ref", sa.String(length=200), nullable=False),
        sa.Column("target_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("data_version_hash", sa.String(length=64), nullable=True),
        sa.Column("materialized_resource_id", sa.Uuid(), nullable=True),
        sa.Column("execution_ticket_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "action_kind IN ('record.create','record.update','task.create',"
            "'reminder.request')",
            name="ck_agent_action_slots_agent_action_slot_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','proposed','pending_confirmation',"
            "'confirmed','executed','denied','degraded','failed','rejected',"
            "'conflicted','cancelled','expired')",
            name="ck_agent_action_slots_agent_action_slot_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(control_json) = 'object'",
            name="ck_agent_action_slots_agent_action_slot_control_object",
        ),
        sa.CheckConstraint(
            "proposal_version > 0",
            name="ck_agent_action_slots_agent_action_slot_version_positive",
        ),
        sa.CheckConstraint(
            "target_scope_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_action_slots_agent_action_slot_scope_hash",
        ),
        sa.CheckConstraint(
            "data_version_hash IS NULL OR data_version_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_action_slots_agent_action_slot_data_hash",
        ),
        sa.CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_action_slots_agent_action_slot_idempotency_hash",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_workflow_runs.id"]),
        sa.ForeignKeyConstraint(["objective_run_id"], ["agent_objective_runs.id"]),
        sa.ForeignKeyConstraint(
            ["execution_ticket_id"], ["stage08_execution_tickets.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key_hash", name="uq_agent_action_slot_key"),
        sa.UniqueConstraint("run_id", "slot_key", name="uq_agent_action_slot_run_key"),
    )
    op.create_index(
        "ix_agent_action_slot_run_status",
        "agent_action_slots",
        ["run_id", "status"],
    )
    op.create_index(
        "ix_agent_action_slot_objective_status",
        "agent_action_slots",
        ["objective_run_id", "status"],
    )
    op.create_index(
        "ix_agent_action_slot_recovery",
        "agent_action_slots",
        ["updated_at", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_action_slot_recovery", table_name="agent_action_slots")
    op.drop_index(
        "ix_agent_action_slot_objective_status", table_name="agent_action_slots"
    )
    op.drop_index("ix_agent_action_slot_run_status", table_name="agent_action_slots")
    op.drop_table("agent_action_slots")
    op.drop_index("ix_agent_objective_run_status", table_name="agent_objective_runs")
    op.drop_table("agent_objective_runs")
