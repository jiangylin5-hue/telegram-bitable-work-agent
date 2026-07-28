from app.models import metadata
from app.models.agent_event_runtime import (
    AgentCommand,
    AgentEvent,
    AgentOutboxEvent,
    AgentPrivateInput,
    AgentRunCheckpoint,
    AgentWorkflowRun,
)


def test_runtime_control_plane_tables_have_no_private_content_columns() -> None:
    expected = {
        "agent_workflow_runs",
        "agent_run_checkpoints",
        "agent_commands",
        "agent_events",
        "agent_artifacts",
        "agent_outbox_events",
        "agent_private_inputs",
    }
    assert expected.issubset(metadata.tables)

    forbidden = {
        "query",
        "prompt",
        "raw_result",
        "provider_response",
        "record_values",
        "group_text",
    }
    for table_name in expected:
        assert forbidden.isdisjoint(metadata.tables[table_name].columns.keys())


def test_runtime_control_plane_declares_identity_and_ordering_constraints() -> None:
    assert AgentWorkflowRun.__table__.c.idempotency_key_hash.unique is True
    assert AgentRunCheckpoint.__table__.c.checkpoint_no.nullable is False
    assert AgentCommand.__table__.c.idempotency_key_hash.unique is True
    assert AgentEvent.__table__.c.sequence.nullable is False
    assert AgentOutboxEvent.__table__.c.event_id.unique is True
    assert AgentPrivateInput.__table__.c.ciphertext.nullable is False
    assert "query" not in AgentPrivateInput.__table__.columns

    constraint_names = {
        constraint.name
        for table in (
            AgentRunCheckpoint.__table__,
            AgentEvent.__table__,
        )
        for constraint in table.constraints
    }
    assert "uq_agent_run_checkpoint_run_no" in constraint_names
    assert "uq_agent_event_run_sequence" in constraint_names
