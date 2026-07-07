from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class TelegramHttpClient(Protocol):
    def post(self, url: str, *, json: dict[str, Any], timeout: float):
        ...


@dataclass(frozen=True)
class TelegramBotSendResult:
    ok: bool
    response_summary: dict[str, object]


class TelegramBotClient:
    def __init__(
        self,
        *,
        bot_token: str,
        http_client: TelegramHttpClient | None = None,
        base_url: str = "https://api.telegram.org",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.bot_token = bot_token
        self.http_client = http_client or httpx.Client()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def send_message(self, *, chat_id: str, text: str) -> TelegramBotSendResult:
        response = self.http_client.post(
            f"{self.base_url}/bot{self.bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=self.timeout_seconds,
        )
        payload = response.json()
        return TelegramBotSendResult(
            ok=payload.get("ok") is True,
            response_summary=_response_summary(payload),
        )


def _response_summary(payload: dict[str, Any]) -> dict[str, object]:
    if payload.get("ok") is True:
        result = payload.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        return {"ok": True, "telegram_message_id": message_id}

    summary: dict[str, object] = {"ok": False}
    error_code = payload.get("error_code")
    if error_code is not None:
        summary["error_code"] = error_code
    return summary
