from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.agent_event_runtime import AgentActionSlot, AgentObjectiveRun


def test_stage12_action_models_expose_required_constraints_and_indexes() -> None:
    objective_constraints = AgentObjectiveRun.__table__.constraints
    action_constraints = AgentActionSlot.__table__.constraints

    assert any(
        isinstance(item, UniqueConstraint)
        and tuple(column.name for column in item.columns) == ("run_id", "objective_key")
        for item in objective_constraints
    )
    assert any(
        isinstance(item, UniqueConstraint)
        and tuple(column.name for column in item.columns) == ("idempotency_key_hash",)
        for item in action_constraints
    )
    assert sum(isinstance(item, CheckConstraint) for item in action_constraints) >= 5
    assert {index.name for index in AgentActionSlot.__table__.indexes} >= {
        "ix_agent_action_slot_run_status",
        "ix_agent_action_slot_objective_status",
        "ix_agent_action_slot_recovery",
    }


def test_stage12_action_migration_is_single_head() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))

    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260730_0039"]
    revision = script.get_revision("20260730_0036")
    assert revision is not None
    assert revision.down_revision == "20260729_0035"
