from app.schemas.agent_task_spec_v2 import (
    AuthorizedSchemaSnapshot,
    authorized_schema_sha256,
)
from app.schemas.agent_specialist_results import (
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from uuid import UUID
from app.services.agent_claim_graph import (
    ActionDependencyV1,
    ClaimInputV1,
    ObjectiveOutcomeInputV1,
    build_claim_graph,
)
import app.services.agent_composer_v2 as composer_module
from app.services.agent_composer_v2 import ComposerProviderDraftV1, compose_claim_graph
from app.services.agent_composer_provider import ComposerProviderInvocationError
import pytest
from pydantic import ValidationError


SCOPE = "a" * 64
TABLE_ID = UUID("37000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("37000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("37000000-0000-4000-8000-000000000003")


def _facts(
    *,
    records: tuple[dict[str, object], ...] = (),
    aggregates: tuple[dict[str, object], ...] = (),
    evidence: str = "ev-1",
) -> StructuredFactSetV1:
    payload = {
        "version": "structured-fact-set.v1",
        "objective_id": "obj-1",
        "records": records,
        "groups": (),
        "aggregates": aggregates,
        "relation_paths": (),
        "source_versions": (
            {"table_id": TABLE_ID, "record_id": RECORD_ID, "record_version": 2},
        ),
        "evidence_refs": (evidence,),
        "scope_hash": SCOPE,
        "schema_hash": "c" * 64,
        "complete": True,
        "truncated": False,
    }
    payload["content_hash"] = specialist_payload_sha256(payload)
    return StructuredFactSetV1.model_validate(payload)


def _authorized_schema() -> AuthorizedSchemaSnapshot:
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": UUID("10000000-0000-4000-8000-000000000001"),
        "employee_id": UUID("10000000-0000-4000-8000-000000000002"),
        "scope_hash": SCOPE,
        "tables": (),
        "field_policy_version": "stage12-field-policy.v2",
        "field_policy_hash": "b" * 64,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _graph():
    return build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="obj-1",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-1",),
                source_version=2,
            ),
        ),
        outcomes=(ObjectiveOutcomeInputV1("obj-1", "completed", True),),
        actions=(),
        scope_hash=SCOPE,
        source_artifacts=(
            _facts(
                records=(
                    {
                        "record_id": RECORD_ID,
                        "table_id": TABLE_ID,
                        "values": ({"field_id": FIELD_ID, "value": "blocked"},),
                    },
                ),
            ),
        ),
    )


def _two_section_plan_and_graph():
    facts = _facts(
        records=(
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        )
    )
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="obj-1",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-1",),
                source_version=2,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("obj-1", "completed", True),
            ObjectiveOutcomeInputV1("obj-2", "degraded", False, "risk_unavailable"),
        ),
        actions=(),
        scope_hash=SCOPE,
        source_artifacts=(facts,),
    )
    plan = composer_module.ComposerAnswerPlanV2(
        sections=(
            composer_module.ComposerAnswerSectionPlanV2(
                section_id="facts",
                section_kind="facts",
                objective_ids=("obj-1",),
                claim_ids=(graph.claims[0].claim_id,),
                action_slot_ids=(),
                connector_code="direct",
            ),
            composer_module.ComposerAnswerSectionPlanV2(
                section_id="degradation",
                section_kind="degradation",
                objective_ids=("obj-2",),
                claim_ids=(),
                action_slot_ids=(),
                connector_code="however",
            ),
        )
    )
    return plan, graph


def test_deterministic_section_contract_seals_hashes_and_rejects_tampering() -> None:
    plan, graph = _two_section_plan_and_graph()

    section_set = composer_module.build_deterministic_section_set(plan, graph)

    assert tuple(item.default_rank for item in section_set.sections) == (0, 1)
    assert all(
        item.section_handle.startswith("section:sha256:")
        for item in section_set.sections
    )
    assert section_set == composer_module.build_deterministic_section_set(plan, graph)

    duplicate_payload = section_set.model_dump(mode="python")
    duplicate_payload["sections"][1]["section_handle"] = duplicate_payload["sections"][
        0
    ]["section_handle"]
    with pytest.raises(ValidationError, match="deterministic_section_handle_duplicate"):
        composer_module.DeterministicSectionSetV1.model_validate(duplicate_payload)

    rank_payload = section_set.model_dump(mode="python")
    rank_payload["sections"][1]["default_rank"] = 3
    with pytest.raises(ValidationError, match="deterministic_section_rank_invalid"):
        composer_module.DeterministicSectionSetV1.model_validate(rank_payload)

    with pytest.raises(ValidationError, match="frozen_instance"):
        section_set.sections[0].default_rank = 1

    unknown_payload = section_set.model_dump(mode="python")
    unknown_payload["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        composer_module.DeterministicSectionSetV1.model_validate(unknown_payload)


def test_ordering_request_projection_excludes_private_graph_data() -> None:
    plan, graph = _two_section_plan_and_graph()
    section_set = composer_module.build_deterministic_section_set(plan, graph)

    request = composer_module.build_section_ordering_request(
        section_set,
        graph=graph,
        authorized_schema=_authorized_schema(),
    )

    assert request.default_order == tuple(
        item.section_handle for item in section_set.sections
    )
    assert tuple(item.section_kind for item in request.candidates) == (
        "facts",
        "degradation",
    )
    assert tuple(item.objective_statuses for item in request.candidates) == (
        ("completed",),
        ("degraded",),
    )
    serialized = request.model_dump_json()
    for forbidden in (
        "objective_id",
        "claim_id",
        "action_slot_id",
        "evidence_id",
        "record:",
        "field:",
        "expected_",
        "gold_",
        "query",
    ):
        assert forbidden not in serialized


def test_expand_ordering_plan_restores_only_original_private_sections() -> None:
    plan, graph = _two_section_plan_and_graph()
    section_set = composer_module.build_deterministic_section_set(plan, graph)
    facts, degradation = section_set.sections
    ordering = composer_module.ComposerSectionOrderingPlanV1(
        ordered_section_handles=(
            degradation.section_handle,
            facts.section_handle,
        ),
        connector_by_handle={
            degradation.section_handle: "direct",
            facts.section_handle: "next",
        },
    )

    expanded = composer_module.expand_ordering_plan(section_set, ordering)

    assert tuple(item.section_kind for item in expanded.sections) == (
        "degradation",
        "facts",
    )
    assert expanded.sections[0].objective_ids == plan.sections[1].objective_ids
    assert expanded.sections[0].claim_ids == plan.sections[1].claim_ids
    assert expanded.sections[0].action_slot_ids == plan.sections[1].action_slot_ids
    assert expanded.sections[1].objective_ids == plan.sections[0].objective_ids
    assert expanded.sections[1].claim_ids == plan.sections[0].claim_ids
    assert expanded.sections[1].action_slot_ids == plan.sections[0].action_slot_ids


def test_expand_ordering_plan_rejects_forged_handle_or_connector() -> None:
    plan, graph = _two_section_plan_and_graph()
    section_set = composer_module.build_deterministic_section_set(plan, graph)
    facts, degradation = section_set.sections
    unknown = "section:sha256:" + "f" * 64
    forged_handle = composer_module.ComposerSectionOrderingPlanV1.model_construct(
        ordered_section_handles=(facts.section_handle, unknown),
        connector_by_handle={facts.section_handle: "direct", unknown: "however"},
    )
    forged_connector = composer_module.ComposerSectionOrderingPlanV1.model_construct(
        ordered_section_handles=(facts.section_handle, degradation.section_handle),
        connector_by_handle={
            facts.section_handle: "direct",
            degradation.section_handle: "next",
        },
    )

    with pytest.raises(ValueError, match="composer_section_ordering_invalid"):
        composer_module.expand_ordering_plan(section_set, forged_handle)
    with pytest.raises(ValueError, match="composer_section_ordering_invalid"):
        composer_module.expand_ordering_plan(section_set, forged_connector)


def _four_section_graph_and_presentation():
    facts = _facts(
        records=(
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        )
    )
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-1",),
                source_version=2,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("facts", "completed", True),
            ObjectiveOutcomeInputV1("action", "proposed", True),
            ObjectiveOutcomeInputV1("denied", "denied", False, "policy_denied"),
            ObjectiveOutcomeInputV1("degraded", "failed", False, "risk_failed"),
        ),
        actions=(
            ActionDependencyV1(
                slot_id="act-1",
                proposal_status="proposed",
                required_claim_refs=(),
            ),
        ),
        scope_hash=SCOPE,
        source_artifacts=(facts,),
    )
    presentation = composer_module.ComposerPresentationContextV1(
        query="汇总事实、动作和边界。",
        objectives=(
            composer_module.ComposerObjectiveContextV1(
                objective_id="facts", kind="fact_query", required=True
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="action", kind="record_change", required=True
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="denied", kind="risk_analysis", required=False
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="degraded", kind="risk_analysis", required=False
            ),
        ),
        subject_labels={f"record:{RECORD_ID}": "MT-014"},
        predicate_labels={f"field:{FIELD_ID}": "status"},
    )
    return graph, presentation


def test_ordering_connectors_render_only_fixed_chinese_prefixes() -> None:
    graph, presentation = _four_section_graph_and_presentation()

    def provider(request):
        handles = {
            item.section_kind: item.section_handle for item in request.candidates
        }
        return composer_module.ComposerSectionOrderingPlanV1(
            ordered_section_handles=(
                handles["facts"],
                handles["actions"],
                handles["denial"],
                handles["degradation"],
            ),
            connector_by_handle={
                handles["facts"]: "direct",
                handles["actions"]: "next",
                handles["denial"]: "however",
                handles["degradation"]: "safety_boundary",
            },
        )

    result = compose_claim_graph(
        graph,
        provider=provider,
        authorized_schema=_authorized_schema(),
        presentation=presentation,
    )

    assert result.answer.splitlines()[0].startswith("已验证事实：")
    assert result.answer.splitlines()[1].startswith("接下来，待确认动作：")
    assert result.answer.splitlines()[2].startswith("不过，无法执行：")
    assert result.answer.splitlines()[3].startswith("安全边界：降级说明：")


@pytest.mark.parametrize(
    "failure_code",
    (
        "provider_schema_invalid",
        "provider_semantic_invalid",
        "provider_timeout",
        "provider_rate_limited",
        "provider_quota_exhausted",
        "provider_http_error",
        "deadline_exhausted",
    ),
)
def test_ordering_provider_failure_preserves_complete_deterministic_receipt(
    failure_code: str,
) -> None:
    graph, presentation = _four_section_graph_and_presentation()
    deterministic = compose_claim_graph(graph, presentation=presentation)

    def provider(_request):
        raise ComposerProviderInvocationError(failure_code)

    result = compose_claim_graph(
        graph,
        provider=provider,
        authorized_schema=_authorized_schema(),
        presentation=presentation,
    )

    assert (
        result.render_receipt.covered_objective_ids
        == deterministic.render_receipt.covered_objective_ids
    )
    assert (
        result.render_receipt.covered_claim_ids
        == deterministic.render_receipt.covered_claim_ids
    )
    assert (
        result.render_receipt.covered_action_slot_ids
        == deterministic.render_receipt.covered_action_slot_ids
    )
    assert result.provider_call_count == 1
    assert failure_code in result.degradation_codes
    assert result.answer == deterministic.answer


def test_invalid_ordering_falls_back_to_complete_deterministic_receipt() -> None:
    graph, presentation = _four_section_graph_and_presentation()
    deterministic = compose_claim_graph(graph, presentation=presentation)

    def provider(request):
        first = request.candidates[0].section_handle
        unknown = "section:sha256:" + "f" * 64
        return composer_module.ComposerSectionOrderingPlanV1.model_construct(
            ordered_section_handles=(first, unknown),
            connector_by_handle={first: "direct", unknown: "however"},
        )

    result = compose_claim_graph(
        graph,
        provider=provider,
        authorized_schema=_authorized_schema(),
        presentation=presentation,
    )

    assert result.status == "degraded"
    assert set(result.degradation_codes) == {
        "policy_denied",
        "provider_semantic_invalid",
        "risk_failed",
    }
    assert result.render_receipt == deterministic.render_receipt
    assert result.answer == deterministic.answer


def test_deterministic_composer_returns_grounded_chinese_result() -> None:
    graph = _graph()
    result = compose_claim_graph(graph)

    assert result.status == "completed"
    assert result.provider_call_count == 0
    assert result.claim_ids == (graph.claims[0].claim_id,)
    assert result.evidence_ids == ("ev-1",)
    assert "blocked" in result.answer


def test_composer_preserves_provider_failure_taxonomy_in_safe_fallback() -> None:
    graph = _graph()

    def unavailable(_request):
        raise ComposerProviderInvocationError("provider_rate_limited")

    result = compose_claim_graph(
        graph,
        provider=unavailable,
        authorized_schema=_authorized_schema(),
    )

    assert result.status == "degraded"
    assert result.provider_call_count == 1
    assert "provider_rate_limited" in result.degradation_codes
    assert result.render_receipt is not None


def test_bounded_provider_plan_renders_safe_labels_and_hashed_receipt() -> None:
    graph = _graph()
    presentation = composer_module.ComposerPresentationContextV1(
        query="查询 MT-014 当前状态。",
        objectives=(
            composer_module.ComposerObjectiveContextV1(
                objective_id="obj-1",
                kind="fact_query",
                required=True,
            ),
        ),
        subject_labels={f"record:{RECORD_ID}": "MT-014"},
        predicate_labels={f"field:{FIELD_ID}": "status"},
    )

    def provider(request):
        assert not hasattr(request, "presentation")
        handle = request.candidates[0].section_handle
        return composer_module.ComposerSectionOrderingPlanV1(
            ordered_section_handles=(handle,),
            connector_by_handle={handle: "direct"},
        )

    result = compose_claim_graph(
        graph,
        provider=provider,
        authorized_schema=_authorized_schema(),
        presentation=presentation,
    )

    assert result.status == "completed"
    assert result.provider_call_count == 1
    assert "MT-014" in result.answer
    assert "status" in result.answer
    assert "blocked" in result.answer
    assert "record:" not in result.answer
    assert "field:" not in result.answer
    assert result.render_receipt.covered_objective_ids == ("obj-1",)
    assert result.render_receipt.covered_claim_ids == (graph.claims[0].claim_id,)
    assert result.render_receipt.covered_action_slot_ids == ()
    assert result.render_receipt.section_kinds == ("facts",)
    assert result.render_receipt.language == "zh-Hans"
    assert result.render_receipt.claim_graph_hash == graph.content_hash
    assert result.render_receipt.answer_hash
    assert result.render_receipt.content_hash


def test_provider_plan_cannot_omit_graph_objective_coverage() -> None:
    graph = _graph()

    def provider(_request):
        return composer_module.ComposerAnswerPlanV2(
            sections=(
                composer_module.ComposerAnswerSectionPlanV2(
                    section_id="facts",
                    section_kind="facts",
                    objective_ids=(),
                    claim_ids=(graph.claims[0].claim_id,),
                    action_slot_ids=(),
                    connector_code="direct",
                ),
            ),
        )

    result = compose_claim_graph(
        graph,
        provider=provider,
        authorized_schema=_authorized_schema(),
    )

    assert result.status == "degraded"
    assert result.degradation_codes == ("provider_semantic_invalid",)
    assert result.provider_call_count == 1
    assert result.render_receipt.covered_objective_ids == ("obj-1",)


def test_deterministic_answer_discloses_optional_failure_and_pending_action() -> None:
    facts = _facts(
        records=(
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        )
    )
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-1",),
                source_version=2,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("facts", "completed", True),
            ObjectiveOutcomeInputV1("risk", "failed", False, "risk_failed"),
            ObjectiveOutcomeInputV1("action", "proposed", True),
        ),
        actions=(
            ActionDependencyV1(
                slot_id="act-1",
                proposal_status="proposed",
                required_claim_refs=(),
            ),
        ),
        scope_hash=SCOPE,
        source_artifacts=(facts,),
    )
    presentation = composer_module.ComposerPresentationContextV1(
        query="说明风险并生成待确认动作。",
        objectives=(
            composer_module.ComposerObjectiveContextV1(
                objective_id="facts", kind="fact_query", required=True
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="risk", kind="risk_analysis", required=False
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="action", kind="record_change", required=True
            ),
        ),
        subject_labels={f"record:{RECORD_ID}": "MT-014"},
        predicate_labels={f"field:{FIELD_ID}": "status"},
    )

    result = compose_claim_graph(graph, presentation=presentation)

    assert result.status == "degraded"
    assert "降级说明" in result.answer
    assert "risk_failed" in result.answer
    assert "待确认动作" in result.answer
    assert "act-1" in result.answer
    assert "尚未执行" in result.answer
    assert set(result.render_receipt.covered_objective_ids) == {
        "facts",
        "risk",
        "action",
    }
    assert result.render_receipt.covered_action_slot_ids == ("act-1",)
    assert set(result.render_receipt.disclosure_codes) >= {
        "risk_failed",
        "action_proposed",
    }


def test_answer_plan_rejects_duplicate_section_identity() -> None:
    with pytest.raises(
        ValidationError, match="composer_plan_section_identity_duplicate"
    ):
        composer_module.ComposerAnswerPlanV2(
            sections=(
                composer_module.ComposerAnswerSectionPlanV2(
                    section_id="same",
                    section_kind="facts",
                    objective_ids=("obj-1",),
                    claim_ids=("claim-1",),
                    action_slot_ids=(),
                    connector_code="direct",
                ),
                composer_module.ComposerAnswerSectionPlanV2(
                    section_id="same",
                    section_kind="actions",
                    objective_ids=("obj-2",),
                    claim_ids=(),
                    action_slot_ids=("act-1",),
                    connector_code="safety_boundary",
                ),
            ),
        )


def test_answer_plan_rejects_duplicate_section_kind_before_render_receipt() -> None:
    with pytest.raises(ValidationError, match="composer_plan_section_kind_duplicate"):
        composer_module.ComposerAnswerPlanV2(
            sections=(
                composer_module.ComposerAnswerSectionPlanV2(
                    section_id="facts-1",
                    section_kind="facts",
                    objective_ids=("obj-1",),
                    claim_ids=("claim-1",),
                    action_slot_ids=(),
                    connector_code="direct",
                ),
                composer_module.ComposerAnswerSectionPlanV2(
                    section_id="facts-2",
                    section_kind="facts",
                    objective_ids=("obj-2",),
                    claim_ids=("claim-2",),
                    action_slot_ids=(),
                    connector_code="next",
                ),
            ),
        )


def test_unknown_presentation_label_is_rejected_before_provider_call() -> None:
    graph = _graph()
    calls = []
    presentation = composer_module.ComposerPresentationContextV1(
        query="查询当前状态。",
        objectives=(
            composer_module.ComposerObjectiveContextV1(
                objective_id="obj-1", kind="fact_query", required=True
            ),
        ),
        subject_labels={"record:hidden": "客户密钥"},
        predicate_labels={f"field:{FIELD_ID}": "status"},
    )

    def provider(request):
        calls.append(request)
        raise AssertionError("unscoped presentation must not reach Provider")

    with pytest.raises(ValueError, match="composer_presentation_scope_invalid"):
        compose_claim_graph(
            graph,
            provider=provider,
            authorized_schema=_authorized_schema(),
            presentation=presentation,
        )

    assert calls == []


def test_provider_plan_cannot_omit_action_status_coverage() -> None:
    facts = _facts(
        records=(
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        )
    )
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-1",),
                source_version=2,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("facts", "completed", True),
            ObjectiveOutcomeInputV1("action", "proposed", True),
        ),
        actions=(
            ActionDependencyV1(
                slot_id="act-1",
                proposal_status="proposed",
                required_claim_refs=(),
            ),
        ),
        scope_hash=SCOPE,
        source_artifacts=(facts,),
    )
    presentation = composer_module.ComposerPresentationContextV1(
        query="查询并创建待确认动作。",
        objectives=(
            composer_module.ComposerObjectiveContextV1(
                objective_id="facts", kind="fact_query", required=True
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="action", kind="record_change", required=True
            ),
        ),
        subject_labels={f"record:{RECORD_ID}": "MT-014"},
        predicate_labels={f"field:{FIELD_ID}": "status"},
    )

    def provider(_request):
        return composer_module.ComposerAnswerPlanV2(
            sections=(
                composer_module.ComposerAnswerSectionPlanV2(
                    section_id="facts",
                    section_kind="facts",
                    objective_ids=("facts", "action"),
                    claim_ids=(graph.claims[0].claim_id,),
                    action_slot_ids=(),
                    connector_code="direct",
                ),
            ),
        )

    result = compose_claim_graph(
        graph,
        provider=provider,
        authorized_schema=_authorized_schema(),
        presentation=presentation,
    )

    assert result.status == "degraded"
    assert result.degradation_codes == ("provider_semantic_invalid",)
    assert result.render_receipt.covered_action_slot_ids == ("act-1",)
    assert "尚未执行" in result.answer


@pytest.mark.parametrize(
    ("proposal_status", "objective_state", "expected_text", "disclosure_code"),
    (
        ("denied", "denied", "已拒绝，未执行", "action_denied"),
        ("deferred", "proposed", "已延后，未执行", "action_deferred"),
    ),
)
def test_deterministic_answer_discloses_non_executed_action_status(
    proposal_status: str,
    objective_state: str,
    expected_text: str,
    disclosure_code: str,
) -> None:
    facts = _facts(
        records=(
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        )
    )
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-1",),
                source_version=2,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("facts", "completed", True),
            ObjectiveOutcomeInputV1(
                "action",
                objective_state,
                True,
                "field_permission_denied" if objective_state == "denied" else None,
            ),
        ),
        actions=(
            ActionDependencyV1(
                slot_id="act-1",
                proposal_status=proposal_status,
                required_claim_refs=(),
                reason_code=(
                    "field_permission_denied"
                    if proposal_status == "denied"
                    else "dependency_pending"
                ),
            ),
        ),
        scope_hash=SCOPE,
        source_artifacts=(facts,),
    )
    presentation = composer_module.ComposerPresentationContextV1(
        query="生成受控动作。",
        objectives=(
            composer_module.ComposerObjectiveContextV1(
                objective_id="facts", kind="fact_query", required=True
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="action", kind="record_change", required=True
            ),
        ),
        subject_labels={f"record:{RECORD_ID}": "MT-014"},
        predicate_labels={f"field:{FIELD_ID}": "status"},
    )

    result = compose_claim_graph(graph, presentation=presentation)

    assert expected_text in result.answer
    assert disclosure_code in result.render_receipt.disclosure_codes


def test_deterministic_answer_discloses_conflicted_claim_and_action() -> None:
    blocked = _facts(
        records=(
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        ),
        evidence="ev-blocked",
    )
    done = _facts(
        records=(
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "done"},),
            },
        ),
        evidence="ev-done",
    )
    subject = f"record:{RECORD_ID}"
    predicate = f"field:{FIELD_ID}"
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="facts",
                subject_ref=subject,
                predicate=predicate,
                value="blocked",
                evidence_ids=("ev-blocked",),
                source_version=2,
            ),
            ClaimInputV1(
                objective_id="facts",
                subject_ref=subject,
                predicate=predicate,
                value="done",
                evidence_ids=("ev-done",),
                source_version=2,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("facts", "completed", True),
            ObjectiveOutcomeInputV1("action", "proposed", True),
        ),
        actions=(
            ActionDependencyV1(
                slot_id="act-1",
                proposal_status="proposed",
                required_claim_refs=((subject, predicate),),
            ),
        ),
        scope_hash=SCOPE,
        source_artifacts=(blocked, done),
    )
    presentation = composer_module.ComposerPresentationContextV1(
        query="发现冲突后不要执行动作。",
        objectives=(
            composer_module.ComposerObjectiveContextV1(
                objective_id="facts", kind="fact_query", required=True
            ),
            composer_module.ComposerObjectiveContextV1(
                objective_id="action", kind="record_change", required=True
            ),
        ),
        subject_labels={subject: "MT-014"},
        predicate_labels={predicate: "status"},
    )

    result = compose_claim_graph(graph, presentation=presentation)

    assert result.status == "degraded"
    assert "降级说明" in result.answer
    assert "conflicted_claim" in result.answer
    assert "存在冲突，未执行" in result.answer
    assert set(result.render_receipt.disclosure_codes) >= {
        "conflicted_claim",
        "action_conflicted",
    }


def test_provider_unsupported_claim_falls_back_with_semantic_failure() -> None:
    graph = _graph()

    def unsupported(request):
        assert request.field_policy_hash == "b" * 64
        return ComposerProviderDraftV1(
            answer="项目已经完成。",
            claim_ids=("invented-claim",),
            evidence_ids=("ev-1",),
        )

    result = compose_claim_graph(
        graph,
        provider=unsupported,
        authorized_schema=_authorized_schema(),
    )

    assert result.status == "degraded"
    assert result.provider_call_count == 1
    assert result.degradation_codes == ("provider_semantic_invalid",)
    assert "已经完成" not in result.answer


def test_provider_is_not_called_without_stage12_field_policy_proof() -> None:
    calls = []

    def provider(request):
        calls.append(request)
        raise AssertionError("provider must not receive an unproven field scope")

    result = compose_claim_graph(_graph(), provider=provider)

    assert calls == []
    assert result.status == "degraded"
    assert result.provider_call_count == 0
    assert result.degradation_codes == ("policy_denied",)


def test_provider_cannot_add_bankruptcy_or_budget_prose_with_valid_ids() -> None:
    graph = _graph()

    def hallucinated(_request):
        return ComposerProviderDraftV1(
            answer="该公司即将破产，预算已经全部耗尽。",
            claim_ids=(graph.claims[0].claim_id,),
            evidence_ids=("ev-1",),
        )

    result = compose_claim_graph(
        graph,
        provider=hallucinated,
        authorized_schema=_authorized_schema(),
    )

    assert result.status == "degraded"
    assert result.degradation_codes == ("provider_semantic_invalid",)
    assert "破产" not in result.answer
    assert "预算" not in result.answer


def test_optional_failure_preserves_valid_facts_in_degraded_result() -> None:
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="facts",
                subject_ref="aggregate:daily",
                predicate="value",
                value=3,
                evidence_ids=("ev-fact",),
                source_version=2,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("facts", "completed", True),
            ObjectiveOutcomeInputV1("risk", "failed", False, "risk_failed"),
        ),
        actions=(),
        scope_hash=SCOPE,
        source_artifacts=(
            _facts(
                aggregates=({"aggregate_id": "daily", "group_key": None, "value": 3},),
                evidence="ev-fact",
            ),
        ),
    )

    result = compose_claim_graph(graph)

    assert result.status == "degraded"
    assert result.evidence_ids == ("ev-fact",)
    assert "3" in result.answer
    assert "risk_failed" in result.degradation_codes
