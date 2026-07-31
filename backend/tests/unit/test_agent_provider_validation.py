from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from app.services.agent_provider_validation import (
    ProviderValidationError,
    parse_and_validate_provider_response,
)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["completed", "proposed"]
    answer: str
    evidence_ids: tuple[str, ...]


def test_provider_validation_accepts_grounded_chinese_payload() -> None:
    payload = parse_and_validate_provider_response(
        '{"status":"completed","answer":"当前有一项阻塞记录。","evidence_ids":["ev-01"]}',
        payload_type=_Payload,
        allowed_evidence_ids=frozenset({"ev-01"}),
        response_language="zh-Hans",
    )
    assert payload.evidence_ids == ("ev-01",)


@pytest.mark.parametrize(
    ("content", "code"),
    (
        ("not-json", "provider_schema_invalid"),
        (
            '{"status":"completed","answer":"中文","evidence_ids":["ev-99"]}',
            "provider_citation_invalid",
        ),
        (
            '{"status":"completed","answer":"Only English","evidence_ids":[]}',
            "provider_language_invalid",
        ),
    ),
)
def test_provider_validation_classifies_schema_citation_and_language(
    content: str, code: str
) -> None:
    with pytest.raises(ProviderValidationError) as captured:
        parse_and_validate_provider_response(
            content,
            payload_type=_Payload,
            allowed_evidence_ids=frozenset({"ev-01"}),
            response_language="zh-Hans",
        )
    assert captured.value.code == code
    assert captured.value.path.startswith("$")


def test_provider_validation_rejects_false_completion_claim_and_semantic_scope() -> (
    None
):
    with pytest.raises(ProviderValidationError) as captured:
        parse_and_validate_provider_response(
            '{"status":"proposed","answer":"已经更新完成。","evidence_ids":["ev-01"]}',
            payload_type=_Payload,
            allowed_evidence_ids=frozenset({"ev-01"}),
            response_language="zh-Hans",
            forbid_completion_claims=True,
        )
    assert captured.value.code == "provider_semantic_invalid"

    def reject(_payload):
        raise ProviderValidationError("field_not_allowed", "$.assignments.status")

    with pytest.raises(ProviderValidationError) as captured:
        parse_and_validate_provider_response(
            '{"status":"proposed","answer":"建议更新。","evidence_ids":["ev-01"]}',
            payload_type=_Payload,
            allowed_evidence_ids=frozenset({"ev-01"}),
            response_language="zh-Hans",
            semantic_validator=reject,
        )
    assert captured.value.code == "field_not_allowed"
    assert captured.value.path == "$.assignments.status"
