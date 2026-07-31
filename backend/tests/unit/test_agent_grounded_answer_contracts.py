from __future__ import annotations

import json
from typing import get_args

import pytest
from pydantic import ValidationError

from app.schemas.agent_grounded_answer_v2 import (
    GroundedAnswerPlanV2,
    GroundedAnswerSectionV2,
    GroundedAnswerStatementV2,
    GroundedComposerResultV2,
    ProviderResponseFingerprintV1,
)
from app.schemas.agent_specialist_results import ProviderFailureCode


def _valid_fact_statement() -> GroundedAnswerStatementV2:
    return GroundedAnswerStatementV2(
        statement_kind="fact",
        text="Atlas 项目有 2 个高优先级且未完成的工作项。",
        claim_handles=("claim:sha256:" + "a" * 64,),
        evidence_handles=("evidence:sha256:" + "b" * 64,),
        action_handles=(),
    )


def _walk_schema(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_schema(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_schema(child)


def test_provider_response_schema_has_only_closed_fixed_property_objects() -> None:
    schema = GroundedAnswerPlanV2.model_json_schema()

    object_nodes = [
        node for node in _walk_schema(schema) if node.get("type") == "object"
    ]

    assert object_nodes
    assert all(node.get("additionalProperties") is False for node in object_nodes)
    assert '"additionalProperties": {' not in json.dumps(schema, sort_keys=True)


def test_provider_response_properties_have_model_guidance_descriptions() -> None:
    schema = GroundedAnswerPlanV2.model_json_schema()

    properties = [
        property_schema
        for node in _walk_schema(schema)
        for property_schema in (
            node.get("properties", {}).values()
            if isinstance(node.get("properties"), dict)
            else ()
        )
    ]

    assert properties
    assert all(property_schema.get("description") for property_schema in properties)


@pytest.mark.parametrize("statement_kind", ["fact", "analysis", "recommendation"])
def test_grounded_factual_statement_requires_claim_and_evidence_references(
    statement_kind: str,
) -> None:
    with pytest.raises(ValidationError, match="grounded_statement_claim_required"):
        GroundedAnswerStatementV2(
            statement_kind=statement_kind,
            text="Atlas 项目有 2 个高优先级且未完成的工作项。",
            claim_handles=(),
            evidence_handles=(),
            action_handles=(),
        )


def test_action_status_statement_requires_an_action_reference() -> None:
    with pytest.raises(ValidationError, match="grounded_statement_action_required"):
        GroundedAnswerStatementV2(
            statement_kind="action_status",
            text="该更新仍在等待确认。",
            claim_handles=(),
            evidence_handles=(),
            action_handles=(),
        )


def test_grounded_plan_rejects_duplicate_section_kind() -> None:
    section = GroundedAnswerSectionV2(
        section_kind="answer",
        heading="结论",
        statements=(_valid_fact_statement(),),
    )

    with pytest.raises(ValidationError, match="grounded_answer_section_kind_duplicate"):
        GroundedAnswerPlanV2(sections=(section, section))


def test_grounded_result_contract_exposes_real_answer_source_and_provider_status() -> (
    None
):
    assert GroundedComposerResultV2.model_fields["answer_source"].annotation is not None
    assert (
        GroundedComposerResultV2.model_fields["provider_result_status"].annotation
        is not None
    )
    schema = GroundedComposerResultV2.model_json_schema()
    assert set(schema["properties"]["answer_source"]["enum"]) == {
        "real_provider",
        "deterministic_fallback",
    }


def test_provider_fingerprint_cannot_store_raw_prompt_or_response() -> None:
    fields = set(ProviderResponseFingerprintV1.model_fields)

    assert {
        "top_level_type",
        "top_level_keys",
        "response_bytes",
        "response_sha256",
        "validation_error_types",
        "validation_paths",
    } <= fields
    assert not fields & {
        "prompt",
        "raw_prompt",
        "response",
        "raw_response",
        "content",
        "previous_output",
    }


def test_grounding_and_fallback_have_distinct_failure_codes() -> None:
    codes = set(get_args(ProviderFailureCode))

    assert "provider_grounding_invalid" in codes
    assert "deterministic_fallback_used" in codes
    assert "provider_schema_invalid" in codes
