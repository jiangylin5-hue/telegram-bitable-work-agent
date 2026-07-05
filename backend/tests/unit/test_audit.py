from app.services.audit import record_audit_event


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def test_record_audit_event_adds_redacted_event() -> None:
    session = FakeSession()

    event = record_audit_event(
        session,
        trace_id="trace-1",
        actor_type="user",
        actor_id="finance-1",
        event_type="payment_profile_checked",
        entity_type="payment_profile",
        before_state={
            "raw_card_number": "4111111111111111",
            "nested": {"cvv": "123"},
            "status": "available",
        },
        after_state={"status": "used"},
        permission_snapshot={"role": "finance"},
    )

    assert session.added == [event]
    assert event.before_state == {
        "raw_card_number": "[redacted]",
        "nested": {"cvv": "[redacted]"},
        "status": "available",
    }
    assert event.after_state == {"status": "used"}
    assert event.permission_snapshot == {"role": "finance"}
