from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError


def test_recharge_draft_agent_creates_pending_confirmation_candidate() -> None:
    from app.agents.recharge_draft_agent import build_recharge_draft
    from app.agents.schemas import DraftAgentContext, RouterIntent

    context = _context()
    intent = RouterIntent.model_validate(
        {
            "intent_type": "recharge",
            "intent_index": 0,
            "confidence": "0.9300",
            "entities": {
                "account_hint": "act_1001",
                "amount": "100",
                "currency": "USD",
            },
            "risk_flags": [],
            "missing_context": [],
        }
    )

    candidate = build_recharge_draft(intent, context)

    assert candidate.draft_type == "recharge"
    assert candidate.status == "pending_confirmation"
    assert candidate.intent_type == "recharge"
    assert candidate.intent_index == 0
    assert candidate.agent_name == "recharge_draft_agent"
    assert candidate.confidence == Decimal("0.9300")
    assert candidate.payload == {
        "account_hint": "act_1001",
        "amount": "100",
        "currency": "USD",
        "customer_message_summary": "Customer requested recharge and reply.",
        "provider_execution_allowed": False,
    }
    assert candidate.payload_summary == {
        "account_hint": "act_1001",
        "amount": "100",
        "currency": "USD",
    }
    assert candidate.idempotency_key == (
        f"draft:{context.source_message_id}:recharge:0"
    )


def test_recharge_draft_agent_preserves_missing_fields_and_followup() -> None:
    from app.agents.recharge_draft_agent import build_recharge_draft
    from app.agents.schemas import RouterIntent

    context = _context()
    intent = RouterIntent.model_validate(
        {
            "intent_type": "recharge",
            "intent_index": 1,
            "confidence": "0.6600",
            "entities": {"account_hint": "act_1001"},
            "risk_flags": [],
            "missing_context": ["amount", "currency"],
        }
    )

    candidate = build_recharge_draft(intent, context)

    assert candidate.status == "needs_more_info"
    assert candidate.missing_fields == ["amount", "currency"]
    assert "amount" in candidate.payload["suggested_follow_up_text"]
    assert candidate.idempotency_key == f"draft:{context.source_message_id}:recharge:1"


def test_card_binding_agent_rejects_raw_card_data_without_persisting_secret() -> None:
    from app.agents.card_binding_draft_agent import build_card_binding_draft
    from app.agents.schemas import RouterIntent

    intent = RouterIntent.model_validate(
        {
            "intent_type": "card_binding",
            "intent_index": 0,
            "confidence": "0.8800",
            "entities": {
                "account_hint": "act_2002",
                "payment_profile_hint": "card 4111111111111111 cvv 123",
            },
            "risk_flags": [],
            "missing_context": [],
        }
    )

    candidate = build_card_binding_draft(intent, _context())

    assert candidate.status == "manual_review"
    assert "sensitive_payment_data_detected" in candidate.risk_flags
    assert "4111111111111111" not in str(candidate.payload)
    assert "cvv" not in str(candidate.payload).lower()
    assert candidate.payload["provider_execution_allowed"] is False


def test_bm_invite_agent_marks_missing_invitee_as_needs_more_info() -> None:
    from app.agents.bm_invite_draft_agent import build_bm_invite_draft
    from app.agents.schemas import RouterIntent

    intent = RouterIntent.model_validate(
        {
            "intent_type": "bm_invite",
            "intent_index": 2,
            "confidence": "0.8100",
            "entities": {"bm_hint": "BM-APAC-01"},
            "risk_flags": [],
            "missing_context": ["invitee_hint"],
        }
    )

    candidate = build_bm_invite_draft(intent, _context())

    assert candidate.status == "needs_more_info"
    assert candidate.missing_fields == ["invitee_hint"]
    assert candidate.payload["bm_hint"] == "BM-APAC-01"
    assert candidate.payload["provider_execution_allowed"] is False


def test_customer_reply_agent_creates_reviewable_reply_without_send_request() -> None:
    from app.agents.customer_reply_draft_agent import build_customer_reply_draft
    from app.agents.schemas import RouterIntent

    context = _context()
    intent = RouterIntent.model_validate(
        {
            "intent_type": "customer_reply",
            "intent_index": 3,
            "confidence": "0.7900",
            "entities": {"reply_text": "We are checking the account and will update you."},
            "risk_flags": [],
            "missing_context": [],
        }
    )

    candidate = build_customer_reply_draft(intent, context)

    assert candidate.status == "pending_confirmation"
    assert candidate.payload["reply_text"] == (
        "We are checking the account and will update you."
    )
    assert candidate.payload["send_allowed_scope"] == (
        "staging_allowlisted_test_chat_only"
    )
    assert candidate.payload["send_request_created"] is False
    assert candidate.idempotency_key == (
        f"draft:{context.source_message_id}:customer_reply:3"
    )


def test_stage05_draft_candidate_rejects_unknown_status() -> None:
    from app.agents.schemas import Stage05DraftCandidate

    try:
        Stage05DraftCandidate.model_validate(
            {
                **_candidate_payload(),
                "status": "sent",
            }
        )
    except ValidationError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("Stage05DraftCandidate accepted unsupported status")


def test_service_draft_metadata_migration_adds_stage05_columns() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260707_0013_stage05_service_draft_metadata.py"
    )

    text = migration.read_text()

    assert "down_revision = \"20260707_0012\"" in text
    assert "source_agent_run_id" in text
    assert "intent_index" in text
    assert "payload_summary" in text
    assert "review_reason" in text
    assert "confirmed_at" in text
    assert "fk_service_drafts_source_agent_run_id_agent_runs" in text


def _context():
    from app.agents.schemas import DraftAgentContext

    return DraftAgentContext(
        source_message_id=str(uuid4()),
        customer_id=str(uuid4()),
        trace_id="trace-stage05-draft",
        source_text_summary="Customer requested recharge and reply.",
        source_agent_run_id=str(uuid4()),
    )


def _candidate_payload() -> dict[str, object]:
    return {
        "draft_type": "recharge",
        "status": "pending_confirmation",
        "intent_type": "recharge",
        "intent_index": 0,
        "payload": {"account_hint": "act_1001"},
        "payload_summary": {"account_hint": "act_1001"},
        "missing_fields": [],
        "risk_flags": [],
        "confidence": "0.9000",
        "source_message_id": str(uuid4()),
        "source_agent_run_id": str(uuid4()),
        "created_by_type": "agent",
        "created_by_id": "recharge_draft_agent",
        "agent_name": "recharge_draft_agent",
        "trace_id": "trace-stage05-draft",
        "idempotency_key": f"draft:{uuid4()}:recharge:0",
    }
