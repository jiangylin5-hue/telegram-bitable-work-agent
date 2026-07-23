from datetime import UTC, datetime, timedelta
import hashlib

import pytest

from app.services.stage06_identity import Stage06IdentityError, Stage06RequestIdentity
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from app.services.stage09_browser_handoffs import (
    BrowserHandoffError,
    exchange_browser_handoff,
    issue_browser_handoff,
    resolve_browser_session_identity,
)


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
IDENTITY = Stage06RequestIdentity(
    user_id="member-1",
    source="telegram_binding",
    telegram_user_id="telegram-123",
)


def test_issue_stores_only_ticket_hash() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()

    ticket = issue_browser_handoff(uow, IDENTITY, NOW)

    handoff = uow._stage09_browser_handoffs[0]
    assert handoff.ticket_hash == hashlib.sha256(ticket.encode("utf-8")).hexdigest()
    assert ticket not in repr(handoff)
    assert handoff.expires_at == NOW + timedelta(minutes=5)


def test_issue_requires_verified_telegram_identity() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()

    with pytest.raises(Stage06IdentityError) as denied:
        issue_browser_handoff(
            uow,
            Stage06RequestIdentity("member-1", "development_header"),
            NOW,
        )

    assert denied.value.code == "browser_handoff_telegram_identity_required"


def test_exchange_consumes_ticket_only_once_and_returns_browser_session_identity() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    ticket = issue_browser_handoff(uow, IDENTITY, NOW)

    session_token = exchange_browser_handoff(uow, ticket, NOW)
    identity = resolve_browser_session_identity(uow, session_token, NOW)

    assert identity == Stage06RequestIdentity(
        user_id="member-1",
        source="browser_session",
        telegram_user_id="telegram-123",
    )
    with pytest.raises(BrowserHandoffError) as denied:
        exchange_browser_handoff(uow, ticket, NOW)
    assert denied.value.code == "browser_handoff_consumed"


@pytest.mark.parametrize("state", ["expired", "revoked"])
def test_exchange_rejects_expired_and_revoked_tickets(state: str) -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    ticket = issue_browser_handoff(uow, IDENTITY, NOW)
    handoff = uow._stage09_browser_handoffs[0]
    if state == "expired":
        reference_time = NOW + timedelta(minutes=5)
    else:
        handoff.revoked_at = NOW
        reference_time = NOW

    with pytest.raises(BrowserHandoffError) as denied:
        exchange_browser_handoff(uow, ticket, reference_time)

    assert denied.value.code == f"browser_handoff_{state}"
