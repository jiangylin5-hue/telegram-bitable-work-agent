from decimal import Decimal
import json
import re

import pytest
from pydantic import ValidationError


def test_router_result_validates_multi_intent_output() -> None:
    from app.agents.schemas import RouterResult

    result = RouterResult.model_validate(
        {
            "intents": [
                {
                    "intent_type": "recharge",
                    "confidence": "0.9100",
                    "entities": {
                        "account_hint": "act_1001",
                        "amount": "100",
                        "currency": "USD",
                    },
                    "risk_flags": [],
                    "missing_context": [],
                },
                {
                    "intent_type": "bm_invite",
                    "confidence": "0.8400",
                    "entities": {"bm_hint": "BM-APAC-01"},
                    "risk_flags": [],
                    "missing_context": ["email"],
                },
                {
                    "intent_type": "customer_reply",
                    "confidence": "0.7900",
                    "entities": {"reply_topic": "acknowledgement"},
                    "risk_flags": [],
                    "missing_context": [],
                },
            ],
            "overall_confidence": "0.8800",
            "requires_manual_review": False,
            "manual_review_reasons": [],
            "redacted_summary": "Customer asks for recharge, BM invite and a reply draft.",
        }
    )

    assert [intent.intent_type for intent in result.intents] == [
        "recharge",
        "bm_invite",
        "customer_reply",
    ]
    assert result.intents[0].confidence == Decimal("0.9100")
    assert result.intents[1].missing_context == ["email"]
    assert result.requires_manual_review is False


def test_router_result_rejects_unsupported_intent_type() -> None:
    from app.agents.schemas import RouterResult

    with pytest.raises(ValidationError):
        RouterResult.model_validate(
            {
                "intents": [
                    {
                        "intent_type": "produce_account",
                        "confidence": "0.9900",
                        "entities": {},
                        "risk_flags": [],
                        "missing_context": [],
                    }
                ],
                "overall_confidence": "0.9900",
                "requires_manual_review": False,
                "manual_review_reasons": [],
                "redacted_summary": "Unsupported account production request.",
            }
        )


def test_stage05_workflow_state_initializer_sets_required_keys() -> None:
    from app.agents.stage05_state import new_stage05_workflow_state

    state = new_stage05_workflow_state(
        trace_id="trace-router-1",
        message_id="message-1",
        customer_id="customer-1",
        source_text_summary="Customer asks to recharge act_1001 100 USD.",
    )
    second_state = new_stage05_workflow_state(
        trace_id="trace-router-2",
        message_id="message-2",
        customer_id="customer-2",
        source_text_summary="Customer says thanks.",
    )

    assert state["trace_id"] == "trace-router-1"
    assert state["message_id"] == "message-1"
    assert state["customer_id"] == "customer-1"
    assert state["source_text_summary"] == "Customer asks to recharge act_1001 100 USD."
    assert state["router_result"] is None
    assert state["selected_agents"] == []
    assert state["draft_candidates"] == []
    assert state["account_status_actions"] == []
    assert state["manual_review_reasons"] == []
    assert state["agent_run_ids"] == []
    assert state["created_entity_refs"] == []
    assert state["status"] == "initialized"
    assert state["errors"] == []

    state["errors"].append({"error_code": "agent_output_invalid"})
    assert second_state["errors"] == []


def test_select_child_agents_deduplicates_supported_intents() -> None:
    from app.agents.message_intake_router import select_child_agents
    from app.agents.schemas import RouterResult

    result = RouterResult.model_validate(
        {
            "intents": [
                _intent("recharge"),
                _intent("card_binding"),
                _intent("bm_invite"),
                _intent("customer_reply"),
                _intent("account_assignment"),
                _intent("account_status_exception"),
                _intent("irrelevant"),
                _intent("unknown"),
            ],
            "overall_confidence": "0.7500",
            "requires_manual_review": True,
            "manual_review_reasons": ["unknown intent needs review"],
            "redacted_summary": "Mixed request with one unknown branch.",
        }
    )

    assert select_child_agents(result) == [
        "recharge_draft_agent",
        "card_binding_draft_agent",
        "bm_invite_draft_agent",
        "customer_reply_draft_agent",
        "account_inventory_agent",
    ]


def test_build_router_request_uses_structured_llm_contract_without_secrets() -> None:
    from app.agents.interfaces import StructuredLLMRequest
    from app.agents.message_intake_router import build_router_request

    request = build_router_request(
        trace_id="trace-router-3",
        message_id="message-3",
        customer_id="customer-3",
        source_text_summary="客户要求 recharge act_1001 100 USD and invite BM.",
        context_summary="Customer is bound and has one open draft.",
    )

    assert isinstance(request, StructuredLLMRequest)
    assert request.prompt_version == "stage05-router-v1"
    assert [message.role for message in request.messages] == ["system", "user"]
    assert request.response_schema["type"] == "object"
    assert "intents" in request.response_schema["properties"]

    combined_prompt = "\n".join(message.content for message in request.messages)
    assert "Return JSON only" in combined_prompt
    assert "required top-level keys are: intents" in combined_prompt
    assert "Do not return top-level fields named intent_type" in combined_prompt
    assert "Allowed intent_type values" in combined_prompt
    assert "entities.reply_text" in combined_prompt
    assert "entities.account_hint" in combined_prompt
    assert "entities.bm_hint" in combined_prompt
    assert "entities.target_status" in combined_prompt
    assert "not to execute provider actions can still be routed" in combined_prompt
    assert "Do not invent account ids" in combined_prompt
    assert "客户要求 recharge act_1001 100 USD" in combined_prompt
    assert "OPENROUTER_API_KEY" not in combined_prompt
    assert "TELEGRAM_BOT_TOKEN" not in combined_prompt


def test_build_router_request_example_matches_router_schema() -> None:
    from app.agents.message_intake_router import build_router_request
    from app.agents.schemas import RouterResult

    request = build_router_request(
        trace_id="trace-router-example",
        message_id="message-router-example",
        customer_id="customer-router-example",
        source_text_summary="Recharge act_1001 100 USD.",
    )
    system_prompt = request.messages[0].content
    match = re.search(r"Example response: (\{.*\})", system_prompt)

    assert match is not None
    example = json.loads(match.group(1))
    result = RouterResult.model_validate(example)

    assert result.intents[0].intent_type == "recharge"
    assert result.requires_manual_review is False
    assert result.redacted_summary


def test_parse_router_result_maps_invalid_output_to_agent_failed() -> None:
    from app.agents.message_intake_router import RouterOutputInvalid, parse_router_result

    with pytest.raises(RouterOutputInvalid) as exc_info:
        parse_router_result("not-json")

    assert exc_info.value.error_code == "agent_output_invalid"
    assert exc_info.value.workflow_status == "agent_failed"
    assert "Router output must be a JSON object" in str(exc_info.value)


def _intent(intent_type: str) -> dict[str, object]:
    return {
        "intent_type": intent_type,
        "confidence": "0.8000",
        "entities": {},
        "risk_flags": [],
        "missing_context": [],
    }
