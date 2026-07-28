"""Add the Stage10 durable agent event control plane.

Revision ID: 20260728_0034
Revises: 20260723_0033
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260728_0034"
down_revision = "20260723_0033"
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


def _replace_stage06_idempotency_status_constraint(*, allowed_statuses: str) -> None:
    """Replace the historical constraint when its table exists.

    Some recovery and focused migration paths legitimately stamp the database at
    the Stage09 revision after creating only the platform tables required by the
    Stage10 runtime.  The Stage06 idempotency table is therefore optional here.
    Two names are removed because older databases may contain the explicit name,
    while databases created with the current SQLAlchemy naming convention contain
    the table-prefixed physical name.
    """

    op.execute(
        sa.text(
            f"""
            DO $stage10$
            BEGIN
                IF to_regclass('stage06_idempotency_records') IS NOT NULL THEN
                    ALTER TABLE stage06_idempotency_records
                        DROP CONSTRAINT IF EXISTS
                        ck_stage06_idempotency_records_ck_stage06_idempotency_status;
                    ALTER TABLE stage06_idempotency_records
                        DROP CONSTRAINT IF EXISTS ck_stage06_idempotency_status;
                    ALTER TABLE stage06_idempotency_records
                        ADD CONSTRAINT
                        ck_stage06_idempotency_records_ck_stage06_idempotency_status
                        CHECK (status IN ({allowed_statuses}));
                END IF;
            END
            $stage10$;
            """
        )
    )


def upgrade() -> None:
    _replace_stage06_idempotency_status_constraint(
        allowed_statuses="'in_progress', 'completed', 'failed'",
    )
    op.create_table(
        "agent_workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("root_employee_id", sa.Uuid(), nullable=False),
        sa.Column("target_record_id", sa.Uuid(), nullable=True),
        sa.Column("parent_run_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("data_version_hash", sa.String(length=64), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("safe_result_ref", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('accepted','queued','running','waiting_approval',"
            "'completed','degraded','failed','cancelled','timed_out')",
            name="ck_agent_workflow_runs_agent_workflow_run_status",
        ),
        sa.CheckConstraint(
            "scope_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_workflow_runs_agent_workflow_run_scope_hash",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["root_employee_id"], ["digital_employees.id"]),
        sa.ForeignKeyConstraint(["target_record_id"], ["records.id"]),
        sa.ForeignKeyConstraint(["parent_run_id"], ["agent_workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name="uq_agent_workflow_runs_idempotency_key_hash",
        ),
    )
    op.create_index(
        "ix_agent_workflow_run_workspace_status",
        "agent_workflow_runs",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_agent_workflow_run_lease",
        "agent_workflow_runs",
        ["lease_expires_at", "status"],
    )

    op.create_table(
        "agent_run_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_no", sa.Integer(), nullable=False),
        sa.Column("node_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "control_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("authorization_hash", sa.String(length=64), nullable=False),
        sa.Column("data_version_hash", sa.String(length=64), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "checkpoint_no > 0",
            name="ck_agent_run_checkpoints_agent_run_checkpoint_no_positive",
        ),
        sa.CheckConstraint(
            "authorization_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_run_checkpoints_agent_run_checkpoint_authorization_hash",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "checkpoint_no", name="uq_agent_run_checkpoint_run_no"
        ),
    )
    op.create_index(
        "ix_agent_run_checkpoint_run_created",
        "agent_run_checkpoints",
        ["run_id", "created_at"],
    )

    op.create_table(
        "agent_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("parent_command_id", sa.Uuid(), nullable=True),
        sa.Column("target_capability", sa.String(length=120), nullable=False),
        sa.Column("command_type", sa.String(length=80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload_ref", sa.String(length=160), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["agent_workflow_runs.id"]),
        sa.ForeignKeyConstraint(["parent_command_id"], ["agent_commands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "sequence", name="uq_agent_command_run_sequence"
        ),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name="uq_agent_commands_idempotency_key_hash",
        ),
    )
    op.create_index(
        "ix_agent_command_run_status",
        "agent_commands",
        ["run_id", "status"],
    )

    op.create_table(
        "agent_private_inputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.String(length=80), nullable=False),
        sa.Column("aad_hash", sa.String(length=64), nullable=False),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "aad_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_private_inputs_agent_private_input_aad_hash",
        ),
        sa.CheckConstraint(
            "scope_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_private_inputs_agent_private_input_scope_hash",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_workflow_runs.id"]),
        sa.ForeignKeyConstraint(["command_id"], ["agent_commands.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("command_id", name="uq_agent_private_input_command"),
    )
    op.create_index(
        "ix_agent_private_input_expiry",
        "agent_private_inputs",
        ["expires_at", "consumed_at"],
    )

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("storage_ref", sa.String(length=200), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("visibility_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_artifacts_agent_artifact_content_hash",
        ),
        sa.CheckConstraint(
            "visibility_scope_hash ~ '^[0-9a-f]{64}$'",
            name="ck_agent_artifacts_agent_artifact_visibility_hash",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_artifact_run_kind", "agent_artifacts", ["run_id", "kind"]
    )

    op.create_table(
        "agent_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("causation_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("source_role", sa.String(length=24), nullable=False),
        sa.Column("source_capability", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("safe_summary", sa.String(length=240), nullable=True),
        sa.Column("artifact_ref", sa.Uuid(), nullable=True),
        sa.Column(
            "metrics_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["agent_workflow_runs.id"]),
        sa.ForeignKeyConstraint(["command_id"], ["agent_commands.id"]),
        sa.ForeignKeyConstraint(["artifact_ref"], ["agent_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_event_run_sequence"),
    )
    op.create_index(
        "ix_agent_event_run_created", "agent_events", ["run_id", "created_at"]
    )

    op.create_table(
        "agent_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=60), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publish_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_agent_outbox_events_event_id"),
    )
    op.create_index(
        "ix_agent_outbox_unpublished",
        "agent_outbox_events",
        ["published_at", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_outbox_unpublished", table_name="agent_outbox_events")
    op.drop_table("agent_outbox_events")
    op.drop_index("ix_agent_event_run_created", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_agent_artifact_run_kind", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
    op.drop_index("ix_agent_private_input_expiry", table_name="agent_private_inputs")
    op.drop_table("agent_private_inputs")
    op.drop_index("ix_agent_command_run_status", table_name="agent_commands")
    op.drop_table("agent_commands")
    op.drop_index(
        "ix_agent_run_checkpoint_run_created", table_name="agent_run_checkpoints"
    )
    op.drop_table("agent_run_checkpoints")
    op.drop_index("ix_agent_workflow_run_lease", table_name="agent_workflow_runs")
    op.drop_index(
        "ix_agent_workflow_run_workspace_status", table_name="agent_workflow_runs"
    )
    op.drop_table("agent_workflow_runs")
    _replace_stage06_idempotency_status_constraint(
        allowed_statuses="'in_progress', 'completed'",
    )
