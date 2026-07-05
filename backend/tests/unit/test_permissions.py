from pytest import raises

from app.services.permissions import (
    Actor,
    PermissionDenied,
    assert_action_allowed,
    can_view_customer_record,
    filter_record_fields,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def test_sales_can_only_view_scoped_customer_records() -> None:
    actor = Actor(
        actor_type="user",
        actor_id="sales-1",
        role="sales",
        customer_ids=frozenset({"customer-1"}),
    )

    assert can_view_customer_record(actor, "customer-1")
    assert not can_view_customer_record(actor, "customer-2")


def test_manager_can_view_all_customer_records() -> None:
    actor = Actor(actor_type="user", actor_id="manager-1", role="manager")

    assert can_view_customer_record(actor, "customer-any")


def test_sensitive_fields_are_masked_by_role() -> None:
    actor = Actor(actor_type="user", actor_id="sales-1", role="sales")

    masked = filter_record_fields(
        actor,
        {
            "status": "pending_confirmation",
            "amount": 1000,
            "raw_text": "customer secret",
        },
    )

    assert masked == {
        "status": "pending_confirmation",
        "amount": "[masked]",
        "raw_text": "[masked]",
    }


def test_agent_cannot_confirm_own_draft_and_denial_writes_audit() -> None:
    actor = Actor(actor_type="agent", actor_id="router-agent", role="agent")
    session = FakeSession()

    with raises(PermissionDenied):
        assert_action_allowed(
            actor,
            "confirm_draft",
            session=session,
            trace_id="trace-1",
            entity_type="service_draft",
        )

    assert len(session.added) == 1
    event = session.added[0]
    assert event.event_type == "permission_denied"
    assert event.actor_type == "agent"
    assert event.permission_snapshot["action"] == "confirm_draft"
    assert event.permission_snapshot["role"] == "agent"
