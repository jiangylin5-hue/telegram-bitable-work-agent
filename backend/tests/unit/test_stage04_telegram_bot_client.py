from app.clients.telegram_bot import TelegramBotClient


class FakeTelegramResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class FakeHttpClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests: list[dict] = []

    def post(self, url: str, *, json: dict, timeout: float):
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        return FakeTelegramResponse(self.payload)


def test_telegram_bot_client_builds_send_message_request() -> None:
    http_client = FakeHttpClient(
        {"ok": True, "result": {"message_id": 42, "text": "secret text"}}
    )
    client = TelegramBotClient(
        bot_token="123456:stage04-token",
        http_client=http_client,
    )

    result = client.send_message(chat_id="test-chat", text="hello")

    assert http_client.requests == [
        {
            "url": "https://api.telegram.org/bot123456:stage04-token/sendMessage",
            "json": {"chat_id": "test-chat", "text": "hello"},
            "timeout": 10.0,
        }
    ]
    assert result.ok is True
    assert result.response_summary == {"ok": True, "telegram_message_id": 42}


def test_telegram_bot_client_redacts_response_summary() -> None:
    http_client = FakeHttpClient(
        {
            "ok": False,
            "description": "Bad token 123456:stage04-token for chat test-chat",
            "error_code": 401,
        }
    )
    client = TelegramBotClient(
        bot_token="123456:stage04-token",
        http_client=http_client,
    )

    result = client.send_message(chat_id="test-chat", text="hello")

    assert result.ok is False
    assert result.response_summary == {"ok": False, "error_code": 401}
    assert "stage04-token" not in str(result.response_summary)
    assert "test-chat" not in str(result.response_summary)


def test_telegram_bot_client_builds_the_only_stage07_main_mini_app_button() -> None:
    http_client = FakeHttpClient({"ok": True, "result": {"message_id": 73}})
    client = TelegramBotClient(
        bot_token="123456:stage04-token",
        http_client=http_client,
    )
    raw_url = "https://t.me/Stage07TestBot?startapp=opaqueToken_123456"

    result = client.send_main_mini_app_link(
        chat_id="test-chat",
        url=raw_url,
    )

    assert http_client.requests[0]["json"] == {
        "chat_id": "test-chat",
        "text": "已生成一个受控工作区入口。",
        "reply_markup": {
            "inline_keyboard": [[{"text": "打开工作区", "url": raw_url}]]
        },
    }
    assert result.response_summary == {"ok": True, "telegram_message_id": 73}
    assert raw_url not in str(result.response_summary)
