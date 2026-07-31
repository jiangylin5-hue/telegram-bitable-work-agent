from __future__ import annotations

from collections.abc import Callable
import re
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas.agent_specialist_results import ProviderFailureCode


ResponseLanguage = Literal["zh-Hans", "other"]
PayloadT = TypeVar("PayloadT", bound=BaseModel)
_HAN_RE = re.compile(r"[\u3400-\u9fff]")
_COMPLETION_CLAIM_RE = re.compile(
    r"(?:已经|已)(?:完成|更新|创建|发送|执行|写入|修改|提醒)"
)


class ProviderValidationError(ValueError):
    def __init__(self, code: ProviderFailureCode, path: str) -> None:
        super().__init__(code)
        self.code = code
        self.path = path


def parse_and_validate_provider_response(
    content: str,
    *,
    payload_type: type[PayloadT],
    allowed_evidence_ids: frozenset[str],
    response_language: ResponseLanguage,
    semantic_validator: Callable[[PayloadT], object] | None = None,
    forbid_completion_claims: bool = False,
) -> PayloadT:
    if not isinstance(content, str) or not content or len(content) > 20_000:
        raise ProviderValidationError("provider_schema_invalid", "$")
    try:
        payload = payload_type.model_validate_json(content)
    except ValidationError as exc:
        path = "$"
        errors = exc.errors(include_url=False)
        if errors and errors[0].get("loc"):
            path += "".join(f".{part}" for part in errors[0]["loc"])
        raise ProviderValidationError("provider_schema_invalid", path) from exc
    evidence_ids = getattr(payload, "evidence_ids", ())
    if not isinstance(evidence_ids, tuple) or not set(evidence_ids).issubset(
        allowed_evidence_ids
    ):
        raise ProviderValidationError("provider_citation_invalid", "$.evidence_ids")
    answer = getattr(payload, "answer", None)
    if semantic_validator is not None:
        try:
            semantic_validator(payload)
        except ProviderValidationError:
            raise
        except Exception as exc:
            raise ProviderValidationError("provider_semantic_invalid", "$") from exc
    if (
        forbid_completion_claims
        and isinstance(answer, str)
        and _COMPLETION_CLAIM_RE.search(answer)
    ):
        raise ProviderValidationError("provider_semantic_invalid", "$.answer")
    if response_language == "zh-Hans" and (
        not isinstance(answer, str) or _HAN_RE.search(answer) is None
    ):
        raise ProviderValidationError("provider_language_invalid", "$.answer")
    return payload


__all__ = [
    "ProviderValidationError",
    "ResponseLanguage",
    "parse_and_validate_provider_response",
]
