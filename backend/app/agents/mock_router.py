from decimal import Decimal
import re

from app.agents.interfaces import DraftCandidate
from app.services.telegram_ingestion import IngestedMessage

ACCOUNT_PATTERN = re.compile(r"\b(act_[A-Za-z0-9_]+)\b")
AMOUNT_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*(USD|USDT|CNY|RMB|EUR)\b", re.I)


def route_message_to_draft_candidate(message: IngestedMessage) -> DraftCandidate:
    text = message.normalized_text or message.raw_text or message.raw_caption or ""
    normalized = text.lower()
    if (
        "recharge" in normalized
        or (ACCOUNT_PATTERN.search(text) and AMOUNT_PATTERN.search(text))
    ):
        return _route_recharge(text)
    if _looks_like_report_request(normalized):
        return _route_report(normalized)
    if _looks_like_inventory_request(normalized):
        return _route_inventory(text)

    return DraftCandidate(
        draft_type="customer_reply",
        status="needs_review",
        intent_type="unknown",
        payload={},
        missing_fields=["intent_type"],
        confidence=Decimal("0.3000"),
    )


def _route_recharge(text: str) -> DraftCandidate:
    account_match = ACCOUNT_PATTERN.search(text)
    amount_match = AMOUNT_PATTERN.search(text)
    payload: dict[str, str] = {}
    missing_fields: list[str] = []

    if account_match is None:
        missing_fields.append("account_id")
    else:
        payload["account_id"] = account_match.group(1)

    if amount_match is None:
        missing_fields.extend(["amount", "currency"])
    else:
        payload["amount"] = amount_match.group(1)
        payload["currency"] = amount_match.group(2).upper()

    return DraftCandidate(
        draft_type="recharge",
        status="pending_confirmation" if not missing_fields else "needs_more_info",
        intent_type="recharge",
        payload=payload,
        missing_fields=missing_fields,
        confidence=Decimal("0.9000") if not missing_fields else Decimal("0.6500"),
        amount=payload.get("amount"),
        currency=payload.get("currency"),
        account_hint=payload.get("account_id"),
    )


def _route_inventory(text: str) -> DraftCandidate:
    account_match = ACCOUNT_PATTERN.search(text)
    account_hint = None if account_match is None else account_match.group(1)
    payload = {"request_type": "unused_account"}
    if account_hint is not None:
        payload["account_hint"] = account_hint
    return DraftCandidate(
        draft_type="account_inventory_request",
        status="pending_confirmation",
        intent_type="account_inventory_request",
        payload=payload,
        missing_fields=[],
        confidence=Decimal("0.8000"),
        account_hint=account_hint,
    )


def _route_report(normalized_text: str) -> DraftCandidate:
    report_type = "company_daily" if "company" in normalized_text else "customer_daily"
    return DraftCandidate(
        draft_type=f"{report_type}_report",
        status="pending_confirmation",
        intent_type="report_request",
        payload={"report_type": report_type},
        missing_fields=[],
        confidence=Decimal("0.8200"),
    )


def _looks_like_inventory_request(normalized_text: str) -> bool:
    return (
        "unused account" in normalized_text
        or "inventory account" in normalized_text
        or "new account" in normalized_text
        or "account inventory" in normalized_text
    )


def _looks_like_report_request(normalized_text: str) -> bool:
    return "daily report" in normalized_text or "report" in normalized_text
