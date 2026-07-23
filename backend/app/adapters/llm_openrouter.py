import json
from typing import Any

import httpx

from app.agents.interfaces import LLMMessage, StructuredLLMRequest, StructuredLLMResult
from app.core.config import get_settings


class OpenRouterStructuredLLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        http_client: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.openrouter_api_key
        self.model_name = model_name or settings.openrouter_model
        self.base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=30)

    def generate_json(self, request: StructuredLLMRequest) -> StructuredLLMResult:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for OpenRouter calls")

        model_name = request.model_name or self.model_name
        response = self.http_client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": [_message_payload(message) for message in request.messages],
                "response_format": _strict_response_format(request.response_schema),
            },
        )
        response.raise_for_status()
        payload = response.json()
        raw_text = payload["choices"][0]["message"]["content"]
        return StructuredLLMResult(
            content=_parse_json_object(raw_text),
            model_provider="openrouter",
            model_name=model_name,
            prompt_version=request.prompt_version,
            request_id=payload.get("id"),
            usage=payload.get("usage"),
            raw_text=raw_text,
        )


def _message_payload(message: LLMMessage) -> dict[str, str]:
    return {"role": message.role, "content": message.content}


def _strict_response_format(schema: dict[str, object]) -> dict[str, object]:
    if not isinstance(schema, dict):
        raise TypeError("Structured LLM response_schema must be an object")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "structured_llm_response",
            "strict": True,
            "schema": schema,
        },
    }


def _parse_json_object(raw_text: str) -> dict[str, object]:
    value = json.loads(raw_text)
    if not isinstance(value, dict):
        raise ValueError("OpenRouter response content must be a JSON object")
    return value
