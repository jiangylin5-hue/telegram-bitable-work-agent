from pathlib import Path
import re
from uuid import uuid4

from app.adapters.llm_fake import FakeStructuredLLMClient
from app.agents.interfaces import LLMMessage, StructuredLLMRequest
from app.models import metadata
from app.services.agent_runs import create_agent_run_record


def _router_request() -> StructuredLLMRequest:
    return StructuredLLMRequest(
        messages=[
            LLMMessage(role="system", content="Return Stage05 JSON."),
            LLMMessage(role="user", content="帮 act_123 充值 100 USD"),
        ],
        response_schema={"type": "object"},
        prompt_version="stage05-router-v1",
    )


def test_stage05_agent_run_metadata_shape() -> None:
    table = metadata.tables["agent_runs"]
    column_names = {column.name for column in table.columns}

    assert {
        "message_id",
        "usage_summary",
        "cost_summary",
        "latency_ms",
        "error_code",
        "error_message_redacted",
        "created_entity_refs",
        "redaction_policy",
    }.issubset(column_names)
    assert "full_prompt" not in column_names
    assert "raw_response" not in column_names
    assert "openrouter_api_key" not in column_names


def test_success_agent_run_records_stage05_evidence_without_raw_prompt() -> None:
    message_id = uuid4()
    request = _router_request()
    result = FakeStructuredLLMClient(
        response={
            "intents": ["recharge", "customer_reply"],
            "overall_confidence": "0.9100",
        },
        model_name="fake-stage05-router",
    ).generate_json(request)

    run = create_agent_run_record(
        agent_name="message_intake_router",
        graph_name="stage05_supervisor",
        trace_id="tg:stage05:1",
        request=request,
        result=result,
        message_id=message_id,
        latency_ms=1234,
        cost_summary={"currency": "USD", "estimated_cost": "0.0000"},
        created_entity_refs=[
            {"entity_type": "service_draft", "entity_id": str(uuid4())}
        ],
    )

    assert run.message_id == message_id
    assert run.usage_summary == {"prompt_tokens": 0, "completion_tokens": 0}
    assert run.cost_summary == {"currency": "USD", "estimated_cost": "0.0000"}
    assert run.latency_ms == 1234
    assert run.error_code is None
    assert run.error_message_redacted is None
    assert run.created_entity_refs[0]["entity_type"] == "service_draft"
    assert run.redaction_policy == "summary_only"
    assert run.input_summary["redaction_policy"] == "summary_only"
    assert "帮 act_123" not in str(run.input_summary)
    assert "帮 act_123" not in str(run.output_summary)


def test_failed_agent_run_records_safe_error_without_raw_response() -> None:
    from app.services.agent_runs import create_failed_agent_run_record

    run = create_failed_agent_run_record(
        agent_name="message_intake_router",
        graph_name="stage05_supervisor",
        trace_id="tg:stage05:invalid-json",
        request=_router_request(),
        model_provider="openrouter",
        model_name="openrouter/stage05-model",
        error_code="openrouter_invalid_json",
        error_message_redacted="Model response was not a JSON object.",
        latency_ms=987,
    )

    assert run.status == "failed"
    assert run.output_summary == {}
    assert run.usage_summary == {}
    assert run.error_code == "openrouter_invalid_json"
    assert run.error_message_redacted == "Model response was not a JSON object."
    assert run.latency_ms == 987
    assert "raw" not in str(run.output_summary).lower()


def test_agent_run_record_schema_exposes_operational_evidence_only() -> None:
    from app.schemas.agent_runs import AgentRunRecord

    record = AgentRunRecord(
        id=str(uuid4()),
        agent_name="message_intake_router",
        graph_name="stage05_supervisor",
        model_provider="openrouter",
        model_name="openrouter/stage05-model",
        prompt_version="stage05-router-v1",
        status="succeeded",
        trace_id="tg:stage05:1",
        input_summary={"message_count": 2, "redacted": True},
        output_summary={"intents": ["recharge"]},
        usage_summary={"prompt_tokens": 100, "completion_tokens": 20},
        cost_summary={"currency": "USD", "estimated_cost": "0.0000"},
        latency_ms=1200,
        error_code=None,
        created_entity_refs=[],
    )

    payload = record.model_dump()

    assert "raw_response" not in payload
    assert "full_prompt" not in payload
    assert "openrouter_api_key" not in payload
    assert payload["usage_summary"]["prompt_tokens"] == 100


def test_stage05_agent_run_migration_adds_evidence_columns_and_indexes() -> None:
    migration = Path(
        "alembic/versions/20260707_0012_stage05_agent_run_evidence.py"
    )

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")

    for column_name in {
        "message_id",
        "usage_summary",
        "cost_summary",
        "latency_ms",
        "error_code",
        "error_message_redacted",
        "created_entity_refs",
        "redaction_policy",
    }:
        assert re.search(
            rf'op\.add_column\(\s*"agent_runs",\s*sa\.Column\(\s*"{column_name}"',
            source,
        )
    assert "ix_agent_runs_message_id_started_at" in source
    assert "ix_agent_runs_status_started_at" in source
    assert "raw_response" not in source
    assert "full_prompt" not in source
