from datetime import timedelta
import hashlib
import secrets
from typing import Protocol

from sqlalchemy import select, update

from app.models.stage07_telegram import MiniAppBrowserHandoff, MiniAppBrowserSession
from app.services.stage06_identity import Stage06IdentityError, Stage06RequestIdentity


HANDOFF_TTL = timedelta(minutes=5)
BROWSER_SESSION_TTL = timedelta(hours=8)


class BrowserHandoffError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BrowserHandoffUnitOfWork(Protocol):
    def flush(self) -> None:
        pass


def issue_browser_handoff(
    uow: BrowserHandoffUnitOfWork,
    identity: Stage06RequestIdentity,
    now,
) -> str:
    if identity.source != "telegram_binding" or identity.telegram_user_id is None:
        raise Stage06IdentityError(
            "browser_handoff_telegram_identity_required",
            status_code=403,
        )

    ticket = secrets.token_urlsafe(32)
    handoff = MiniAppBrowserHandoff(
        ticket_hash=_sha256(ticket),
        user_id=identity.user_id,
        telegram_user_id=identity.telegram_user_id,
        expires_at=now + HANDOFF_TTL,
        consumed_at=None,
        revoked_at=None,
    )
    _add_handoff(uow, handoff)
    return ticket


def exchange_browser_handoff(
    uow: BrowserHandoffUnitOfWork,
    ticket: str,
    now,
) -> str:
    ticket_hash = _sha256(ticket)
    handoff = _consume_handoff(uow, ticket_hash, now)
    token = secrets.token_urlsafe(32)
    session = MiniAppBrowserSession(
        token_hash=_sha256(token),
        user_id=handoff.user_id,
        telegram_user_id=handoff.telegram_user_id,
        expires_at=now + BROWSER_SESSION_TTL,
        revoked_at=None,
    )
    _add_session(uow, session)
    return token


def resolve_browser_session_identity(
    uow: BrowserHandoffUnitOfWork,
    token: str,
    now,
) -> Stage06RequestIdentity:
    session = _get_active_session(uow, _sha256(token), now)
    if session is None:
        raise BrowserHandoffError("browser_session_invalid")
    return Stage06RequestIdentity(
        user_id=session.user_id,
        source="browser_session",
        telegram_user_id=session.telegram_user_id,
    )


def _consume_handoff(
    uow: BrowserHandoffUnitOfWork,
    ticket_hash: str,
    now,
) -> MiniAppBrowserHandoff:
    session = getattr(uow, "session", None)
    if session is not None:
        result = session.execute(
            update(MiniAppBrowserHandoff)
            .where(
                MiniAppBrowserHandoff.ticket_hash == ticket_hash,
                MiniAppBrowserHandoff.expires_at > now,
                MiniAppBrowserHandoff.consumed_at.is_(None),
                MiniAppBrowserHandoff.revoked_at.is_(None),
            )
            .values(consumed_at=now)
        )
        if result.rowcount == 1:
            handoff = session.scalar(
                select(MiniAppBrowserHandoff).where(
                    MiniAppBrowserHandoff.ticket_hash == ticket_hash
                )
            )
            assert handoff is not None
            return handoff
        handoff = session.scalar(
            select(MiniAppBrowserHandoff).where(
                MiniAppBrowserHandoff.ticket_hash == ticket_hash
            )
        )
        _raise_handoff_error(handoff, now)

    handoff = next(
        (
            value
            for value in _memory_handoffs(uow)
            if value.ticket_hash == ticket_hash
        ),
        None,
    )
    if (
        handoff is not None
        and handoff.expires_at > now
        and handoff.consumed_at is None
        and handoff.revoked_at is None
    ):
        handoff.consumed_at = now
        return handoff
    _raise_handoff_error(handoff, now)


def _raise_handoff_error(handoff: MiniAppBrowserHandoff | None, now) -> None:
    if handoff is None:
        raise BrowserHandoffError("browser_handoff_invalid")
    if handoff.consumed_at is not None:
        raise BrowserHandoffError("browser_handoff_consumed")
    if handoff.revoked_at is not None:
        raise BrowserHandoffError("browser_handoff_revoked")
    if handoff.expires_at <= now:
        raise BrowserHandoffError("browser_handoff_expired")
    raise BrowserHandoffError("browser_handoff_invalid")


def _add_handoff(
    uow: BrowserHandoffUnitOfWork,
    handoff: MiniAppBrowserHandoff,
) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.add(handoff)
        session.flush()
        return
    _memory_handoffs(uow).append(handoff)


def _add_session(
    uow: BrowserHandoffUnitOfWork,
    browser_session: MiniAppBrowserSession,
) -> None:
    session = getattr(uow, "session", None)
    if session is not None:
        session.add(browser_session)
        session.flush()
        return
    _memory_sessions(uow).append(browser_session)


def _get_active_session(
    uow: BrowserHandoffUnitOfWork,
    token_hash: str,
    now,
) -> MiniAppBrowserSession | None:
    session = getattr(uow, "session", None)
    if session is not None:
        return session.scalar(
            select(MiniAppBrowserSession).where(
                MiniAppBrowserSession.token_hash == token_hash,
                MiniAppBrowserSession.expires_at > now,
                MiniAppBrowserSession.revoked_at.is_(None),
            )
        )
    return next(
        (
            value
            for value in _memory_sessions(uow)
            if (
                value.token_hash == token_hash
                and value.expires_at > now
                and value.revoked_at is None
            )
        ),
        None,
    )


def _memory_handoffs(uow: BrowserHandoffUnitOfWork) -> list[MiniAppBrowserHandoff]:
    values = getattr(uow, "_stage09_browser_handoffs", None)
    if values is None:
        values = []
        setattr(uow, "_stage09_browser_handoffs", values)
    return values


def _memory_sessions(uow: BrowserHandoffUnitOfWork) -> list[MiniAppBrowserSession]:
    values = getattr(uow, "_stage09_browser_sessions", None)
    if values is None:
        values = []
        setattr(uow, "_stage09_browser_sessions", values)
    return values


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
