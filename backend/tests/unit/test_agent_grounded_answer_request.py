from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.schemas.agent_specialist_results import (
    DailyBriefV1,
    RiskAssessmentSetV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.agent_task_spec_v2 import (
    ActionSlotV1,
    ActionTargetSelector,
    AuthorizedSchemaSnapshot,
    PlannerCostEstimate,
    SourceSpan,
    TaskObjectiveV2,
    TaskOutputSpec,
    TaskSpecV2,
    authorized_schema_sha256,
)
from app.services.agent_claim_graph import (
    ActionDependencyV1,
    ClaimInputV1,
    ObjectiveOutcomeInputV1,
    build_claim_graph,
)
from app.services.agent_composer_v2 import (
    ComposerObjectiveContextV1,
    ComposerPresentationContextV1,
)
from app.services.agent_grounded_answer_request import build_grounded_answer_request


SCOPE_HASH = "a" * 64
TABLE_ID = UUID("51000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("51000000-0000-4000-8000-000000000002")
FIELD_ID = UUID("51000000-0000-4000-8000-000000000003")


def _schema(*, scope_hash: str = SCOPE_HASH, with_policy: bool = True):
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": UUID("51000000-0000-4000-8000-000000000004"),
        "employee_id": UUID("51000000-0000-4000-8000-000000000005"),
        "scope_hash": scope_hash,
        "tables": (),
        "field_policy_version": "stage12-field-policy.v2" if with_policy else None,
        "field_policy_hash": "b" * 64 if with_policy else None,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _task_spec(schema_hash: str) -> TaskSpecV2:
    span = SourceSpan(start=0, end=5, text="Atlas")
    objective = TaskObjectiveV2(
        objective_id="obj-facts",
        kind="fact_query",
        required=True,
        entity_codes=("Atlas",),
        query_spec_ref=None,
        output_contract="structured_facts",
        planning_outcome="planned",
        denial_reason=None,
        source_spans=(span,),
    )
    return TaskSpecV2(
        version="task-spec.v2",
        authorized_schema_hash=schema_hash,
        query_intents=(),
        objectives=(objective,),
        dependency_edges=(),
        action_slots=(),
        conflict_groups=(),
        output=TaskOutputSpec(
            language="zh-Hans",
            format="conversational",
            include_evidence=True,
        ),
        cost=PlannerCostEstimate(
            lexical_token_count=5,
            bound_field_count=1,
            objective_count=1,
            action_slot_count=0,
            ambiguity_count=0,
            planned_provider_calls=0,
        ),
        provider_call_count=0,
    )


def _facts(
    *, scope_hash: str = SCOPE_HASH, schema_hash: str = "c" * 64
) -> StructuredFactSetV1:
    values = {
        "version": "structured-fact-set.v1",
        "objective_id": "obj-facts",
        "records": (
            {
                "record_id": RECORD_ID,
                "table_id": TABLE_ID,
                "values": ({"field_id": FIELD_ID, "value": "blocked"},),
            },
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": (
            {"table_id": TABLE_ID, "record_id": RECORD_ID, "record_version": 7},
        ),
        "evidence_refs": ("ev-status",),
        "scope_hash": scope_hash,
        "schema_hash": schema_hash,
        "complete": True,
        "truncated": False,
    }
    values["content_hash"] = specialist_payload_sha256(values)
    return StructuredFactSetV1.model_validate(values)


def _authorized_fixture():
    schema = _schema()
    facts = _facts(schema_hash=schema.schema_hash)
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="obj-facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-status",),
                source_version=7,
            ),
        ),
        outcomes=(ObjectiveOutcomeInputV1("obj-facts", "completed", True),),
        actions=(),
        scope_hash=SCOPE_HASH,
        source_artifacts=(facts,),
    )
    presentation = ComposerPresentationContextV1(
        query="列出 Atlas 未完成任务并说明风险",
        objectives=(
            ComposerObjectiveContextV1(
                objective_id="obj-facts",
                kind="fact_query",
                required=True,
            ),
        ),
        subject_labels={f"record:{RECORD_ID}": "Atlas 项目"},
        predicate_labels={f"field:{FIELD_ID}": "任务状态"},
    )
    return (
        presentation.query,
        _task_spec(schema.schema_hash),
        graph,
        schema,
        presentation,
        (facts,),
    )


def _build(**overrides):
    query, task_spec, graph, schema, presentation, findings = _authorized_fixture()
    values = {
        "query": query,
        "task_spec": task_spec,
        "graph": graph,
        "authorized_schema": schema,
        "presentation": presentation,
        "specialist_findings": findings,
    }
    values.update(overrides)
    return build_grounded_answer_request(**values)


def _action_fixture():
    query, task_spec, graph, schema, presentation, findings = _authorized_fixture()
    action_objective = TaskObjectiveV2(
        objective_id="obj-action",
        kind="record_change",
        required=True,
        entity_codes=("Atlas",),
        query_spec_ref=None,
        output_contract="action_slot",
        planning_outcome="planned",
        denial_reason=None,
        source_spans=(SourceSpan(start=0, end=5, text="Atlas"),),
    )
    action_slot = ActionSlotV1(
        slot_id="slot-update",
        objective_id="obj-action",
        action_kind="record.update",
        target=ActionTargetSelector(
            table_id=TABLE_ID,
            record_codes=("Atlas-1",),
            source_entity_codes=(),
            resolution_status="resolved",
        ),
        assignments=(),
        required_field_keys=(),
        confirmation_policy="required",
        deadline_start_utc=None,
        deadline_end_utc=None,
        conflict_group_id=None,
        planning_outcome="planned",
        denial_reason=None,
    )
    task_values = task_spec.model_dump(mode="python")
    task_values["objectives"] = (*task_spec.objectives, action_objective)
    task_values["action_slots"] = (action_slot,)
    task_values["cost"]["objective_count"] = 2
    task_values["cost"]["action_slot_count"] = 1
    action_task_spec = TaskSpecV2.model_validate(task_values)
    action_graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="obj-facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-status",),
                source_version=7,
            ),
        ),
        outcomes=(
            ObjectiveOutcomeInputV1("obj-facts", "completed", True),
            ObjectiveOutcomeInputV1("obj-action", "proposed", True),
        ),
        actions=(
            ActionDependencyV1(
                slot_id="slot-update",
                proposal_status="proposed",
                required_claim_refs=(),
            ),
        ),
        scope_hash=SCOPE_HASH,
        source_artifacts=findings,
    )
    action_presentation = presentation.model_copy(
        update={
            "objectives": (
                *presentation.objectives,
                ComposerObjectiveContextV1(
                    objective_id="obj-action",
                    kind="record_change",
                    required=True,
                ),
            )
        }
    )
    return (
        query,
        action_task_spec,
        action_graph,
        schema,
        action_presentation,
        findings,
    )


def _specialist_fixture(kind: str):
    query, task_spec, _, schema, presentation, _ = _authorized_fixture()
    objective_kind = "risk_analysis" if kind == "risk" else "daily_summary"
    task_values = task_spec.model_dump(mode="python")
    task_values["objectives"][0]["kind"] = objective_kind
    task_values["objectives"][0]["output_contract"] = f"{kind}_result"
    typed_task_spec = TaskSpecV2.model_validate(task_values)
    typed_presentation = presentation.model_copy(
        update={
            "objectives": (
                ComposerObjectiveContextV1(
                    objective_id="obj-facts",
                    kind=objective_kind,
                    required=True,
                ),
            )
        }
    )
    facts = _facts(schema_hash=schema.schema_hash)
    if kind == "risk":
        values = {
            "version": "risk-assessment-set.v1",
            "objective_id": "obj-facts",
            "fact_set_hash": facts.content_hash,
            "policy_version": "risk-policy.v1",
            "available_evidence_ids": ("ev-status",),
            "assessments": (
                {
                    "assessment_id": "risk-1",
                    "subject_ref": str(RECORD_ID),
                    "severity": "high",
                    "reason_codes": ("blocked",),
                    "evidence_ids": ("ev-status",),
                },
            ),
            "scope_hash": SCOPE_HASH,
            "provider_call_count": 1,
        }
        values["content_hash"] = specialist_payload_sha256(values)
        specialist = RiskAssessmentSetV1.model_validate(values)
        claim = ClaimInputV1(
            objective_id="obj-facts",
            subject_ref=f"record:{RECORD_ID}",
            predicate="risk_severity",
            value="high",
            evidence_ids=("ev-status",),
            source_version=7,
        )
        typed_presentation = typed_presentation.model_copy(
            update={"predicate_labels": {"risk_severity": "风险等级"}}
        )
        source_artifacts = (facts, specialist)
    else:
        values = {
            "version": "daily-brief.v1",
            "objective_id": "obj-facts",
            "fact_set_hash": facts.content_hash,
            "risk_set_hash": None,
            "available_evidence_ids": ("ev-status",),
            "statements": (
                {
                    "statement_id": "daily-1",
                    "kind": "fact",
                    "text": "Atlas 项目今日仍处于 blocked 状态。",
                    "evidence_ids": ("ev-status",),
                    "aggregate_id": None,
                },
            ),
            "as_of_utc": datetime(2026, 7, 31, tzinfo=timezone.utc),
            "scope_hash": SCOPE_HASH,
            "provider_call_count": 1,
        }
        values["content_hash"] = specialist_payload_sha256(values)
        specialist = DailyBriefV1.model_validate(values)
        claim = ClaimInputV1(
            objective_id="obj-facts",
            subject_ref=f"record:{RECORD_ID}",
            predicate=f"field:{FIELD_ID}",
            value="blocked",
            evidence_ids=("ev-status",),
            source_version=7,
        )
        source_artifacts = (facts,)
    graph = build_claim_graph(
        claims=(claim,),
        outcomes=(ObjectiveOutcomeInputV1("obj-facts", "completed", True),),
        actions=(),
        scope_hash=SCOPE_HASH,
        source_artifacts=source_artifacts,
    )
    return (
        query,
        typed_task_spec,
        graph,
        schema,
        typed_presentation,
        (facts, specialist),
    )


def test_request_projects_authorized_claims_without_gold_or_private_ids() -> None:
    request = _build()

    payload = request.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert request.query == "列出 Atlas 未完成任务并说明风险"
    assert request.claims[0].subject_label == "Atlas 项目"
    assert request.claims[0].predicate_label == "任务状态"
    assert request.claims[0].value_text == "blocked"
    assert request.objectives[0].objective_handle == "o001"
    assert request.claims[0].claim_handle == "c001"
    assert request.claims[0].evidence_handles == ("e001",)
    assert request.claims[0].source_versions == ("v001",)
    assert request.citations[0].source_version == "v002"
    assert request.citations[0].display_label == "证据 1"
    assert request.version == "grounded-answer-provider-request.v3"
    assert len(request.render_slots) == 1
    assert request.render_slots[0].slot_handle == "s001"
    assert request.render_slots[0].statement_kind == "fact"
    assert request.render_slots[0].claim_handles == ("c001",)
    assert request.render_slots[0].evidence_handles == ("e001",)
    assert request.render_slots[0].action_handles == ()
    assert request.content_hash == specialist_payload_sha256(
        request.model_dump(mode="json", exclude={"content_hash"})
    )
    for forbidden in (
        str(RECORD_ID),
        str(FIELD_ID),
        "ev-status",
        "customer_secret",
        "expected_answer",
        "expected_action",
        "case_id",
        "gold_truth",
    ):
        assert forbidden not in encoded


def test_request_local_references_are_stable_and_canonical_ids_stay_private() -> None:
    first = _build()
    second = _build()

    assert first == second
    assert first.content_hash == second.content_hash
    encoded = first.model_dump_json()
    assert "sha256:" not in encoded
    assert "claim:status" not in encoded
    assert str(RECORD_ID) not in encoded
    assert str(FIELD_ID) not in encoded


def test_request_rejects_missing_field_policy_proof() -> None:
    schema = _schema(with_policy=False)
    task_spec = _task_spec(schema.schema_hash)

    with pytest.raises(ValueError, match="grounded_request_field_policy_required"):
        _build(authorized_schema=schema, task_spec=task_spec)


def test_request_rejects_scope_and_schema_drift() -> None:
    schema = _schema(scope_hash="d" * 64)
    task_spec = _task_spec(schema.schema_hash)

    with pytest.raises(ValueError, match="grounded_request_scope_mismatch"):
        _build(authorized_schema=schema, task_spec=task_spec)

    query, task_spec, graph, original_schema, presentation, findings = (
        _authorized_fixture()
    )
    mismatched_facts = _facts(
        scope_hash=original_schema.scope_hash,
        schema_hash="e" * 64,
    )
    with pytest.raises(ValueError, match="grounded_request_schema_mismatch"):
        build_grounded_answer_request(
            query=query,
            task_spec=task_spec,
            graph=graph,
            authorized_schema=original_schema,
            presentation=presentation,
            specialist_findings=(mismatched_facts,),
        )


def test_request_rejects_missing_safe_label_and_unknown_evidence() -> None:
    query, task_spec, graph, schema, presentation, findings = _authorized_fixture()
    missing_label = presentation.model_copy(update={"subject_labels": {}})
    with pytest.raises(ValueError, match="grounded_request_safe_label_missing"):
        build_grounded_answer_request(
            query=query,
            task_spec=task_spec,
            graph=graph,
            authorized_schema=schema,
            presentation=missing_label,
            specialist_findings=findings,
        )

    unknown_evidence = _facts(schema_hash=schema.schema_hash).model_dump(mode="python")
    unknown_evidence["evidence_refs"] = ("ev-other",)
    unknown_evidence["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in unknown_evidence.items() if key != "content_hash"}
    )
    invalid_finding = StructuredFactSetV1.model_validate(unknown_evidence)
    with pytest.raises(ValueError, match="grounded_request_evidence_unknown"):
        build_grounded_answer_request(
            query=query,
            task_spec=task_spec,
            graph=graph,
            authorized_schema=schema,
            presentation=presentation,
            specialist_findings=(invalid_finding,),
        )


def test_request_projects_only_valid_claims_from_mixed_status_graph() -> None:
    query, task_spec, graph, schema, presentation, findings = _authorized_fixture()
    values = graph.model_dump(mode="python")
    values["claims"] = (
        values["claims"][0],
        {
            **values["claims"][0],
            "claim_id": "claim:conflicted-risk",
            "predicate": "risk_severity",
            "value": "high",
            "evidence_ids": ("ev-conflicted-risk",),
            "status": "conflicted",
        },
    )
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    mixed_graph = graph.model_validate(values)
    mixed_presentation = presentation.model_copy(
        update={
            "predicate_labels": {
                **presentation.predicate_labels,
                "risk_severity": "风险等级",
            }
        }
    )

    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=mixed_graph,
        authorized_schema=schema,
        presentation=mixed_presentation,
        specialist_findings=findings,
    )

    assert len(request.claims) == 1
    assert request.claims[0].status == "valid"
    assert tuple(item.evidence_handle for item in request.citations) == ("e001",)
    encoded = request.model_dump_json()
    assert "风险等级" not in encoded
    assert "high" not in encoded
    assert "ev-conflicted-risk" not in encoded


def test_request_degrades_completed_objective_with_only_conflicted_claims() -> None:
    query, task_spec, graph, schema, presentation, findings = _authorized_fixture()
    risk_objective = TaskObjectiveV2(
        objective_id="obj-risk",
        kind="risk_analysis",
        required=True,
        entity_codes=("Atlas",),
        query_spec_ref=None,
        output_contract="risk_result",
        planning_outcome="planned",
        denial_reason=None,
        source_spans=(SourceSpan(start=0, end=5, text="Atlas"),),
    )
    task_values = task_spec.model_dump(mode="python")
    task_values["objectives"] = (*task_spec.objectives, risk_objective)
    task_values["cost"]["objective_count"] = 2
    task_spec = TaskSpecV2.model_validate(task_values)
    graph_values = graph.model_dump(mode="python")
    graph_values["claims"] = (
        graph_values["claims"][0],
        {
            **graph_values["claims"][0],
            "claim_id": "claim:risk-high",
            "predicate": "risk_severity",
            "value": "high",
            "evidence_ids": ("ev-risk",),
            "objective_ids": ("obj-risk",),
            "status": "conflicted",
        },
        {
            **graph_values["claims"][0],
            "claim_id": "claim:risk-medium",
            "predicate": "risk_severity",
            "value": "medium",
            "evidence_ids": ("ev-risk",),
            "objective_ids": ("obj-risk",),
            "status": "conflicted",
        },
    )
    graph_values["objective_statuses"] = (
        *graph_values["objective_statuses"],
        {
            "objective_id": "obj-risk",
            "status": "completed",
            "reason_code": None,
        },
    )
    graph_values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in graph_values.items() if key != "content_hash"}
    )
    graph = graph.model_validate(graph_values)
    presentation = presentation.model_copy(
        update={
            "objectives": (
                *presentation.objectives,
                ComposerObjectiveContextV1(
                    objective_id="obj-risk",
                    kind="risk_analysis",
                    required=True,
                ),
            ),
            "predicate_labels": {
                **presentation.predicate_labels,
                "risk_severity": "风险等级",
            },
        }
    )

    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=findings,
    )

    projected = next(item for item in request.objectives if item.kind == "risk_analysis")
    assert projected.status == "degraded"
    assert projected.reason_code == "conflicted_claim"
    assert all(item.status == "valid" for item in request.claims)


def test_request_projects_only_pending_action_status_without_private_target() -> None:
    query, task_spec, graph, schema, presentation, findings = _action_fixture()

    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=findings,
    )

    assert len(request.actions) == 1
    assert request.actions[0].status == "proposed"
    assert request.actions[0].safe_summary == "已生成待确认提议，尚未执行。"
    encoded = request.model_dump_json()
    assert "slot-update" not in encoded
    assert "Atlas-1" not in encoded


@pytest.mark.parametrize(
    ("kind", "expected_kind", "expected_text"),
    (
        ("risk", "risk", "风险评估等级为 high。"),
        ("daily", "daily", "Atlas 项目的任务状态为blocked。"),
    ),
)
def test_request_projects_typed_specialist_findings(
    kind: str, expected_kind: str, expected_text: str
) -> None:
    query, task_spec, graph, schema, presentation, findings = _specialist_fixture(kind)

    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=findings,
    )

    projected = [
        item
        for item in request.specialist_findings
        if item.finding_kind == expected_kind
    ]
    assert len(projected) == 1
    assert projected[0].safe_text == expected_text
    assert projected[0].claim_handles
    assert projected[0].evidence_handles
    if kind == "daily":
        assert not any(
            item.finding_kind == "tabular" for item in request.specialist_findings
        )


def test_request_projects_disjoint_fact_and_risk_finding_closures() -> None:
    query, task_spec, _, schema, presentation, findings = _specialist_fixture("risk")
    facts, risks = findings
    graph = build_claim_graph(
        claims=(
            ClaimInputV1(
                objective_id="obj-facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate=f"field:{FIELD_ID}",
                value="blocked",
                evidence_ids=("ev-status",),
                source_version=7,
            ),
            ClaimInputV1(
                objective_id="obj-facts",
                subject_ref=f"record:{RECORD_ID}",
                predicate="risk_severity",
                value="high",
                evidence_ids=("ev-status",),
                source_version=7,
            ),
        ),
        outcomes=(ObjectiveOutcomeInputV1("obj-facts", "completed", True),),
        actions=(),
        scope_hash=SCOPE_HASH,
        source_artifacts=(facts, risks),
    )
    presentation = presentation.model_copy(
        update={
            "predicate_labels": {
                f"field:{FIELD_ID}": "任务状态",
                "risk_severity": "风险等级",
            }
        }
    )

    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=findings,
    )

    tabular = next(
        item for item in request.specialist_findings if item.finding_kind == "tabular"
    )
    risk = next(
        item for item in request.specialist_findings if item.finding_kind == "risk"
    )
    assert set(tabular.claim_handles).isdisjoint(risk.claim_handles)
    assert set(tabular.claim_handles) | set(risk.claim_handles) == {
        item.claim_handle for item in request.claims
    }
    synthesis_slots = [
        item
        for item in request.render_slots
        if item.statement_kind in {"fact", "analysis", "recommendation"}
    ]
    assert len(synthesis_slots) == 1
    assert synthesis_slots[0].finding_handles == (
        tabular.finding_handle,
        risk.finding_handle,
    )
    assert synthesis_slots[0].claim_handles == tuple(
        item.claim_handle for item in request.claims
    )
    assert synthesis_slots[0].evidence_handles == tuple(
        item.evidence_handle for item in request.citations
    )


def test_request_without_actions_cannot_expose_an_action_render_slot() -> None:
    request = _build()

    assert request.actions == ()
    assert all(item.statement_kind != "action_status" for item in request.render_slots)
    assert all(item.section_kind != "actions" for item in request.render_slots)


@pytest.mark.parametrize(
    ("kind", "expected_text"),
    (
        ("risk", "授权风险评估已完成，未发现需要列出的风险。"),
        ("daily", "授权日报已完成，当前没有额外可展示条目。"),
    ),
)
def test_request_projects_completed_empty_specialist_result(
    kind: str, expected_text: str
) -> None:
    query, task_spec, graph, schema, presentation, findings = _specialist_fixture(kind)
    specialist = findings[1]
    values = specialist.model_dump(mode="python")
    values["assessments" if kind == "risk" else "statements"] = ()
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    specialist = type(specialist).model_validate(values)
    if kind == "risk":
        _, _, graph, _, fact_presentation, _ = _authorized_fixture()
        presentation = presentation.model_copy(
            update={"predicate_labels": fact_presentation.predicate_labels}
        )

    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=(findings[0], specialist),
    )

    projected = [
        item
        for item in request.specialist_findings
        if item.finding_kind == kind
    ]
    assert len(projected) == 1
    assert projected[0].safe_text == expected_text
    assert projected[0].claim_handles


def test_request_does_not_expose_daily_internal_aggregate_representation() -> None:
    query, task_spec, graph, schema, presentation, findings = _specialist_fixture(
        "daily"
    )
    daily = findings[1]
    values = daily.model_dump(mode="python")
    values["statements"][0]["text"] = (
        '聚合 aggregate-unfinished-by-project（分组 '
        '[[{"id":"51000000-0000-4000-8000-000000000099",'
        '"label":"PRJ-ATLAS"}]]）：3'
    )
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    daily = DailyBriefV1.model_validate(values)

    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=(findings[0], daily),
    )

    encoded = request.model_dump_json()
    assert "aggregate-unfinished-by-project" not in encoded
    assert "51000000-0000-4000-8000-000000000099" not in encoded
    assert '"label"' not in encoded
    assert any(
        item.finding_kind == "daily"
        and item.safe_text == "Atlas 项目的任务状态为blocked。"
        for item in request.specialist_findings
    )


def test_request_rejects_specialist_artifact_hash_drift() -> None:
    query, task_spec, graph, schema, presentation, findings = _specialist_fixture(
        "risk"
    )
    risk = findings[1]
    values = risk.model_dump(mode="python")
    values["fact_set_hash"] = "f" * 64
    values["content_hash"] = specialist_payload_sha256(
        {key: value for key, value in values.items() if key != "content_hash"}
    )
    mismatched_risk = RiskAssessmentSetV1.model_validate(values)

    with pytest.raises(
        ValueError, match="grounded_request_specialist_binding_mismatch"
    ):
        build_grounded_answer_request(
            query=query,
            task_spec=task_spec,
            graph=graph,
            authorized_schema=schema,
            presentation=presentation,
            specialist_findings=(findings[0], mismatched_risk),
        )
