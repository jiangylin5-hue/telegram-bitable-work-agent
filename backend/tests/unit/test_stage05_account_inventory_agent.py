from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pytest import raises

from app.agents.schemas import DraftAgentContext, RouterIntent
from app.models.accounts import AccountInventory
from app.services.account_inventory import InMemoryAccountInventoryUnitOfWork
from app.services.permissions import Actor, PermissionDenied


def test_account_assignment_agent_creates_review_draft_without_inventory_mutation() -> None:
    from app.agents.account_inventory_agent import build_account_assignment_draft

    candidate_account_id = uuid4()
    context = _context()
    intent = RouterIntent.model_validate(
        {
            "intent_type": "account_assignment",
            "intent_index": 0,
            "confidence": "0.8700",
            "entities": {
                "request_type": "account_assignment",
                "candidate_account_inventory_ids": [str(candidate_account_id)],
            },
            "risk_flags": [],
            "missing_context": [],
        }
    )
    uow = InMemoryAccountInventoryUnitOfWork()

    candidate = build_account_assignment_draft(intent, context)

    assert candidate.draft_type == "account_assignment"
    assert candidate.status == "pending_confirmation"
    assert candidate.created_by_id == "account_inventory_agent"
    assert candidate.payload["candidate_account_inventory_ids"] == [
        str(candidate_account_id)
    ]
    assert candidate.payload["requires_human_confirmation"] is True
    assert candidate.payload["provider_execution_allowed"] is False
    assert uow.inventory_accounts == []
    assert uow.assignments == []
    assert uow.status_events == []


def test_high_confidence_blocked_exception_marks_status_event_and_audit() -> None:
    from app.agents.account_inventory_agent import plan_account_status_exception
    from app.services.account_inventory import mark_account_exception_from_agent

    source_message_id = uuid4()
    account = _account(status="allocated")
    uow = InMemoryAccountInventoryUnitOfWork(inventory_accounts=[account])
    decision = plan_account_status_exception(
        RouterIntent.model_validate(
            {
                "intent_type": "account_status_exception",
                "confidence": "0.9400",
                "entities": {
                    "account_inventory_id": str(account.id),
                    "target_status": "blocked",
                    "reason": "customer message says account is blocked",
                },
                "risk_flags": ["account_blocked_reported"],
                "missing_context": [],
            }
        )
    )

    assert decision.status_action is not None
    result = mark_account_exception_from_agent(
        uow,
        actor=_agent_actor(),
        account_inventory_id=account.id,
        target_status=decision.status_action.target_status,
        confidence=decision.status_action.confidence,
        risk_flags=decision.status_action.risk_flags,
        source_message_id=source_message_id,
        reason=decision.status_action.reason,
        trace_id="trace-account-exception",
    )

    assert result.changed is True
    assert result.account.inventory_status == "blocked"
    assert result.event is not None
    assert result.event.event_type == "blocked"
    assert result.event.before_status == "allocated"
    assert result.event.after_status == "blocked"
    assert result.event.confidence == Decimal("0.9400")
    assert result.event.risk_flags == ["account_blocked_reported"]
    assert result.event.source_entity_type == "message"
    assert result.event.source_entity_id == source_message_id
    assert uow.audit_events[-1].event_type == "account.exception_marked"
    assert uow.audit_events[-1].after_state["replacement_action"] == "none"


def test_high_confidence_risk_control_exception_is_allowed() -> None:
    from app.agents.account_inventory_agent import plan_account_status_exception
    from app.services.account_inventory import mark_account_exception_from_agent

    account = _account(status="activated")
    uow = InMemoryAccountInventoryUnitOfWork(inventory_accounts=[account])
    decision = plan_account_status_exception(
        RouterIntent.model_validate(
            {
                "intent_type": "account_status_exception",
                "confidence": "0.9300",
                "entities": {
                    "account_inventory_id": str(account.id),
                    "target_status": "risk_controlled",
                    "reason": "customer message reports risk control",
                },
                "risk_flags": ["risk_control_confirmed"],
                "missing_context": [],
            }
        )
    )

    assert decision.status_action is not None
    result = mark_account_exception_from_agent(
        uow,
        actor=_agent_actor(),
        account_inventory_id=account.id,
        target_status=decision.status_action.target_status,
        confidence=decision.status_action.confidence,
        risk_flags=decision.status_action.risk_flags,
        source_message_id=uuid4(),
        reason=decision.status_action.reason,
        trace_id="trace-risk-control",
    )

    assert result.account.inventory_status == "risk_controlled"
    assert uow.status_events[-1].event_type == "risk_controlled"


def test_uncertain_account_risk_enters_manual_review_without_mutation() -> None:
    from app.agents.account_inventory_agent import plan_account_status_exception

    account = _account(status="allocated")
    uow = InMemoryAccountInventoryUnitOfWork(inventory_accounts=[account])
    decision = plan_account_status_exception(
        RouterIntent.model_validate(
            {
                "intent_type": "account_status_exception",
                "confidence": "0.6200",
                "entities": {
                    "account_inventory_id": str(account.id),
                    "target_status": "risk_controlled",
                    "reason": "customer says account is unstable",
                },
                "risk_flags": ["account_unstable_reported"],
                "missing_context": [],
            }
        )
    )

    assert decision.status_action is None
    assert "low_confidence" in decision.manual_review_reasons
    assert account.inventory_status == "allocated"
    assert uow.status_events == []


def test_forbidden_status_transition_is_rejected_without_event() -> None:
    from app.services.account_inventory import (
        InventoryStateError,
        mark_account_exception_from_agent,
    )

    account = _account(status="unused")
    uow = InMemoryAccountInventoryUnitOfWork(inventory_accounts=[account])

    with raises(InventoryStateError):
        mark_account_exception_from_agent(
            uow,
            actor=_agent_actor(),
            account_inventory_id=account.id,
            target_status="allocated",
            confidence=Decimal("0.9900"),
            risk_flags=["account_blocked_reported"],
            source_message_id=uuid4(),
            reason="forbidden transition",
            trace_id="trace-forbidden",
        )

    assert account.inventory_status == "unused"
    assert uow.status_events == []


def test_non_inventory_agent_cannot_auto_mark_account_exception() -> None:
    from app.services.account_inventory import mark_account_exception_from_agent

    account = _account(status="allocated")
    uow = InMemoryAccountInventoryUnitOfWork(inventory_accounts=[account])

    with raises(PermissionDenied):
        mark_account_exception_from_agent(
            uow,
            actor=Actor(actor_type="agent", actor_id="recharge_draft_agent", role="agent"),
            account_inventory_id=account.id,
            target_status="blocked",
            confidence=Decimal("0.9900"),
            risk_flags=["account_blocked_reported"],
            source_message_id=uuid4(),
            reason="wrong agent",
            trace_id="trace-denied",
        )

    assert account.inventory_status == "allocated"
    assert uow.status_events == []
    assert uow.audit_events[-1].event_type == "permission_denied"


def test_duplicate_exception_signal_does_not_create_duplicate_mutation() -> None:
    from app.services.account_inventory import mark_account_exception_from_agent

    account = _account(status="allocated")
    uow = InMemoryAccountInventoryUnitOfWork(inventory_accounts=[account])
    source_message_id = uuid4()

    first = mark_account_exception_from_agent(
        uow,
        actor=_agent_actor(),
        account_inventory_id=account.id,
        target_status="disabled",
        confidence=Decimal("0.9500"),
        risk_flags=["account_disabled_reported"],
        source_message_id=source_message_id,
        reason="disabled by platform",
        trace_id="trace-duplicate",
    )
    second = mark_account_exception_from_agent(
        uow,
        actor=_agent_actor(),
        account_inventory_id=account.id,
        target_status="disabled",
        confidence=Decimal("0.9500"),
        risk_flags=["account_disabled_reported"],
        source_message_id=source_message_id,
        reason="disabled by platform",
        trace_id="trace-duplicate",
    )

    assert first.changed is True
    assert second.changed is False
    assert second.event is None
    assert account.inventory_status == "disabled"
    assert len(uow.status_events) == 1


def test_account_status_event_metadata_migration_adds_confidence_and_risk_flags() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260707_0015_stage05_account_status_event_metadata.py"
    )

    text = migration.read_text()

    assert "down_revision = \"20260707_0013\"" in text
    assert "account_status_events" in text
    assert "confidence" in text
    assert "risk_flags" in text


def _context() -> DraftAgentContext:
    return DraftAgentContext(
        source_message_id=str(uuid4()),
        customer_id=str(uuid4()),
        trace_id="trace-account-inventory-agent",
        source_text_summary="Customer asked for account inventory help.",
        source_agent_run_id=str(uuid4()),
    )


def _account(*, status: str) -> AccountInventory:
    return AccountInventory(
        id=uuid4(),
        platform="meta",
        external_account_id="act_stage05_001",
        inventory_status=status,
        production_batch_id="batch-stage05",
    )


def _agent_actor() -> Actor:
    return Actor(
        actor_type="agent",
        actor_id="account_inventory_agent",
        role="agent",
    )
