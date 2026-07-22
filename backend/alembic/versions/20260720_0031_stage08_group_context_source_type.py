"""Add immutable source chat type to Stage08 group-context projections."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.naming import conv


revision = "20260720_0031"
down_revision = "20260719_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stage08_group_message_projections",
        sa.Column(
            "source_chat_type",
            sa.String(length=20),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        conv("ck_stage08_group_projection_source_chat_type"),
        "stage08_group_message_projections",
        "source_chat_type IN ('group', 'supergroup', 'unknown')",
    )
    op.drop_index(
        "ix_stage08_group_projection_mapping_lifecycle_event",
        table_name="stage08_group_message_projections",
    )
    op.create_index(
        "ix_stage08_group_projection_mapping_lifecycle_event",
        "stage08_group_message_projections",
        [
            "business_context_binding_id",
            "source_chat_type",
            "lifecycle_status",
            "event_at",
            "id",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage08_group_projection_mapping_lifecycle_event",
        table_name="stage08_group_message_projections",
    )
    op.create_index(
        "ix_stage08_group_projection_mapping_lifecycle_event",
        "stage08_group_message_projections",
        ["business_context_binding_id", "lifecycle_status", "event_at", "id"],
    )
    op.drop_constraint(
        conv("ck_stage08_group_projection_source_chat_type"),
        "stage08_group_message_projections",
        type_="check",
    )
    op.drop_column(
        "stage08_group_message_projections",
        "source_chat_type",
    )
