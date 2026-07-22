import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.runtime.stage08_context_contracts import (
    ContextBudget,
    ContextBudgetUsage,
    ContextPack,
    ContextPlan,
    ContextPlanningRequest,
    ContextSourcePlan,
    EvidenceItem,
    EvidenceScope,
    EvidenceVersion,
    ResolvedBusinessScope,
    validate_context_pack,
    validate_context_plan,
)


def _budget(**overrides):
    values = {
        "max_table_records": 20,
        "max_memory_items": 12,
        "max_evidence_items": 24,
        "max_item_chars": 2000,
        "max_total_chars": 12000,
    }
    values.update(overrides)
    return ContextBudget(**values)


def _request(**overrides):
    values = {
        "workspace_id": uuid4(),
        "employee_id": uuid4(),
        "intent": "business_fact",
        "view_ids": (uuid4(),),
        "allow_general_advice": True,
        "budget": _budget(),
    }
    values.update(overrides)
    return ContextPlanningRequest(**values)


def _plan(*, intent="general_advice", sources=None, budget=None) -> ContextPlan:
    workspace_id = uuid4()
    if sources is None:
        sources = (
            ContextSourcePlan(
                source_kind="general_advice",
                priority=1,
                max_items=1,
                reason_code="general_advice_requested",
            ),
        )
    return ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=workspace_id,
        employee_id=uuid4(),
        actor_user_id="viewer",
        intent=intent,
        business_scope=ResolvedBusinessScope(
            workspace_id=workspace_id, relation_kind="none"
        ),
        budget=budget or _budget(),
        sources=sources,
    )


def _evidence(*, label="business_data", content=None, ordinal=1) -> EvidenceItem:
    source_type, version_kind = {
        "business_data": ("platform_record", "record"),
        "confirmed_memory": ("memory_item", "memory"),
        "general_advice": ("policy_marker", "contract"),
    }[label]
    return EvidenceItem(
        evidence_id=f"{label}:{ordinal:02d}",
        label=label,
        source_type=source_type,
        scope=EvidenceScope(workspace_id=uuid4()),
        version=EvidenceVersion(kind=version_kind, value=1),
        source_version=1 if source_type == "platform_record" else None,
        content={} if content is None else content,
        truncated=False,
        truncated_paths=(),
    )


def _usage(evidence: tuple[EvidenceItem, ...]) -> ContextBudgetUsage:
    return ContextBudgetUsage(
        table_records_considered=sum(
            item.source_type == "platform_record" for item in evidence
        ),
        table_records_selected=sum(
            item.source_type == "platform_record" for item in evidence
        ),
        memory_items_considered=sum(
            item.source_type == "memory_item" for item in evidence
        ),
        memory_items_selected=sum(
            item.source_type == "memory_item" for item in evidence
        ),
        evidence_items=len(evidence),
        content_chars=sum(
            len(json.dumps(item.content, sort_keys=True, separators=(",", ":")))
            for item in evidence
        ),
        truncated_items=sum(item.truncated for item in evidence),
        omitted_items=0,
    )


def test_context_budget_enforces_c1_hard_limits_and_strict_integers() -> None:
    for field, value in (
        ("max_table_records", 21),
        ("max_memory_items", 13),
        ("max_evidence_items", 25),
        ("max_item_chars", 2001),
        ("max_total_chars", 12001),
        ("max_table_records", True),
    ):
        with pytest.raises(ValidationError):
            _budget(**{field: value})


@pytest.mark.parametrize(
    "forbidden",
    (
        "prompt",
        "raw_text",
        "group_chat_ref",
        "message_ids",
        "retrieval_query",
        "actor",
        "permission_snapshot",
    ),
)
def test_context_request_rejects_raw_group_and_retrieval_inputs(forbidden: str) -> None:
    base = _request().model_dump(mode="python")
    with pytest.raises(ValidationError):
        ContextPlanningRequest.model_validate({**base, forbidden: "secret"})


def test_context_request_rejects_duplicate_or_excess_views_and_invalid_intent_shape() -> None:
    view_id = uuid4()
    with pytest.raises(ValidationError, match="context_view_ids_invalid"):
        _request(view_ids=(view_id, view_id))
    with pytest.raises(ValidationError, match="context_view_ids_invalid"):
        _request(view_ids=(uuid4(), uuid4(), uuid4(), uuid4()))
    with pytest.raises(ValidationError, match="context_intent_shape_invalid"):
        _request(intent="business_fact", view_ids=())
    with pytest.raises(ValidationError, match="context_intent_shape_invalid"):
        _request(intent="general_advice", view_ids=(uuid4(),))
    narrowed = _request(
        intent="memory_lookup", view_ids=(), customer_record_id=uuid4()
    )
    assert narrowed.customer_record_id is not None


def test_context_source_plan_enforces_kind_specific_shape_and_reason() -> None:
    with pytest.raises(ValidationError, match="context_source_shape_invalid"):
        ContextSourcePlan(
            source_kind="table_view",
            priority=1,
            max_items=3,
            reason_code="business_fact_requested",
        )
    with pytest.raises(ValidationError, match="context_source_reason_mismatch"):
        ContextSourcePlan(
            source_kind="business_memory",
            priority=2,
            max_items=3,
            reason_code="business_fact_requested",
        )


def test_evidence_label_type_scope_and_version_must_match() -> None:
    base = {
        "evidence_id": "business_data:01",
        "label": "business_data",
        "source_type": "platform_record",
        "scope": EvidenceScope(workspace_id=uuid4()),
        "version": EvidenceVersion(kind="record", value=1),
        "source_version": 1,
        "content": {"name": "safe"},
        "truncated": False,
        "truncated_paths": (),
    }
    with pytest.raises(ValidationError, match="context_evidence_label_mismatch"):
        EvidenceItem(**{**base, "source_type": "memory_item"})
    with pytest.raises(ValidationError, match="context_evidence_version_mismatch"):
        EvidenceItem(**{**base, "version": EvidenceVersion(kind="memory", value=1)})
    with pytest.raises(ValidationError):
        EvidenceScope.model_validate(
            {"workspace_id": uuid4(), "group_chat_ref": "never"}
        )
    with pytest.raises(ValidationError, match="context_evidence_id_invalid"):
        EvidenceItem(**{**base, "evidence_id": f"business_data:{uuid4()}"})


def test_reserved_evidence_labels_are_rejected_by_c1() -> None:
    with pytest.raises(ValidationError, match="context_evidence_label_mismatch"):
        EvidenceItem(
            evidence_id="business_data:01",
            label="retrieved_material",
            source_type="platform_record",
            scope=EvidenceScope(workspace_id=uuid4()),
            version=EvidenceVersion(kind="record", value=1),
            source_version=1,
            content={},
            truncated=False,
            truncated_paths=(),
        )


def test_service_revalidation_rejects_model_construct_bypass() -> None:
    request = _request()
    plan = ContextPlan.model_construct(
        contract_version="stage08-context-plan.v1",
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        actor_user_id="viewer",
        intent="general_advice",
        business_scope=ResolvedBusinessScope(
            workspace_id=request.workspace_id, relation_kind="none"
        ),
        budget=ContextBudget.model_construct(
            max_table_records=999,
            max_memory_items=12,
            max_evidence_items=24,
            max_item_chars=2000,
            max_total_chars=12000,
        ),
        sources=(),
    )
    with pytest.raises(ValidationError):
        validate_context_plan(plan)


def test_plan_rejects_source_limits_that_exceed_its_budget() -> None:
    workspace_id = uuid4()
    with pytest.raises(ValidationError, match="context_plan_budget_invalid"):
        ContextPlan(
            contract_version="stage08-context-plan.v1",
            workspace_id=workspace_id,
            employee_id=uuid4(),
            actor_user_id="viewer",
            intent="business_fact",
            business_scope=ResolvedBusinessScope(
                workspace_id=workspace_id, relation_kind="none"
            ),
            budget=_budget(max_table_records=1),
            sources=(
                ContextSourcePlan(
                    source_kind="table_view",
                    priority=1,
                    view_id=uuid4(),
                    source_version=1,
                    max_items=2,
                    reason_code="business_fact_requested",
                ),
            ),
        )


def test_plan_rejects_intent_source_matrix_priority_and_table_count_bypasses() -> None:
    table_sources = tuple(
        ContextSourcePlan(
            source_kind="table_view",
            priority=1,
            view_id=uuid4(),
            source_version=1,
            max_items=1,
            reason_code="business_fact_requested",
        )
        for _ in range(4)
    )
    memory = ContextSourcePlan(
        source_kind="business_memory",
        priority=2,
        max_items=1,
        reason_code="memory_requested",
    )
    with pytest.raises(ValidationError, match="context_plan_sources_invalid"):
        _plan(intent="memory_lookup", sources=table_sources + (memory,))
    with pytest.raises(ValidationError, match="context_plan_sources_invalid"):
        _plan(intent="business_fact", sources=table_sources)
    with pytest.raises(ValidationError, match="context_source_reason_mismatch"):
        ContextSourcePlan(
            source_kind="business_memory",
            priority=1,
            max_items=1,
            reason_code="memory_requested",
        )


def test_plan_rejects_aggregate_source_budget_and_constructed_expansion() -> None:
    sources = tuple(
        ContextSourcePlan(
            source_kind="table_view",
            priority=1,
            view_id=uuid4(),
            source_version=1,
            max_items=1,
            reason_code="business_fact_requested",
        )
        for _ in range(2)
    )
    with pytest.raises(ValidationError, match="context_plan_budget_invalid"):
        _plan(
            intent="business_fact",
            sources=sources,
            budget=_budget(max_table_records=1),
        )
    valid = _plan(intent="memory_lookup", sources=(ContextSourcePlan(
        source_kind="business_memory",
        priority=2,
        max_items=1,
        reason_code="memory_requested",
    ),))
    invalid = ContextPlan.model_construct(
        contract_version=valid.contract_version,
        workspace_id=valid.workspace_id,
        employee_id=valid.employee_id,
        actor_user_id=valid.actor_user_id,
        intent=valid.intent,
        business_scope=valid.business_scope,
        budget=valid.budget,
        sources=sources + valid.sources,
    )
    with pytest.raises(ValidationError, match="context_plan_sources_invalid"):
        validate_context_plan(invalid)


@pytest.mark.parametrize(
    "content",
    (
        {"title": lambda: f"record:{uuid4()}"},
        {f"record:{uuid4()}": "value"},
        {"token": "secret"},
        {"permissions": {"viewer": "read"}},
        {"sourceRefs": []},
        {"source_reference": "internal"},
        {"identity-token": "secret"},
        {"identity_profile": "internal"},
        {"id": "opaque-internal-id"},
        {"record_id": "opaque-internal-id"},
        {"memory-id": "opaque-internal-id"},
        {"RecordID": "opaque-internal-id"},
    ),
)
def test_evidence_rejects_embedded_uuid_and_sensitive_metadata(content) -> None:
    resolved = {
        key: value() if callable(value) else value for key, value in content.items()
    }
    with pytest.raises(ValidationError, match="context_evidence_content_forbidden"):
        _evidence(content=resolved)


def test_context_pack_binds_evidence_to_plan_and_exact_usage() -> None:
    advice_plan = _plan()
    business = _evidence(content={"title": "safe"})
    business = business.model_copy(
        update={"scope": EvidenceScope(workspace_id=advice_plan.workspace_id)}
    )
    chars = len(json.dumps(business.content, sort_keys=True, separators=(",", ":")))
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=advice_plan,
            status="internal_evidence",
            evidence=(business,),
            omissions=(),
            usage=ContextBudgetUsage(
                table_records_considered=1,
                table_records_selected=1,
                memory_items_considered=0,
                memory_items_selected=0,
                evidence_items=1,
                content_chars=chars,
                truncated_items=0,
                omitted_items=0,
            ),
        )

    table_source = ContextSourcePlan(
        source_kind="table_view",
        priority=1,
        view_id=uuid4(),
        source_version=1,
        max_items=1,
        reason_code="business_fact_requested",
    )
    table_plan = _plan(intent="business_fact", sources=(table_source,))
    business = business.model_copy(
        update={
            "scope": EvidenceScope(
                workspace_id=table_plan.workspace_id,
                base_id=uuid4(),
                table_id=uuid4(),
                view_id=table_source.view_id,
            )
        }
    )
    with pytest.raises(ValidationError, match="context_pack_usage_invalid"):
        ContextPack(
            plan=table_plan,
            status="internal_evidence",
            evidence=(business,),
            omissions=(),
            usage=ContextBudgetUsage(
                table_records_considered=1,
                table_records_selected=0,
                memory_items_considered=0,
                memory_items_selected=0,
                evidence_items=1,
                content_chars=chars,
                truncated_items=1,
                omitted_items=0,
            ),
        )


def test_validate_context_pack_rejects_constructed_sensitive_evidence() -> None:
    plan = _plan()
    unsafe = EvidenceItem.model_construct(
        evidence_id="general_advice:01",
        label="general_advice",
        source_type="policy_marker",
        scope=EvidenceScope(workspace_id=plan.workspace_id),
        version=EvidenceVersion(kind="contract", value=1),
        content={"apiToken": "secret"},
        truncated=False,
        truncated_paths=(),
    )
    pack = ContextPack.model_construct(
        plan=plan,
        status="general_advice_only",
        evidence=(unsafe,),
        omissions=(),
        usage=ContextBudgetUsage(
            table_records_considered=0,
            table_records_selected=0,
            memory_items_considered=0,
            memory_items_selected=0,
            evidence_items=1,
            content_chars=len('{"apiToken":"secret"}'),
            truncated_items=0,
            omitted_items=0,
        ),
    )
    with pytest.raises(ValidationError, match="context_evidence_content_forbidden"):
        validate_context_pack(pack)


def test_context_pack_rejects_table_evidence_outside_exact_planned_source() -> None:
    workspace_id = uuid4()
    planned_view_id = uuid4()
    unplanned_view_id = uuid4()
    source = ContextSourcePlan(
        source_kind="table_view",
        priority=1,
        view_id=planned_view_id,
        source_version=7,
        max_items=1,
        reason_code="business_fact_requested",
    )
    plan = ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=workspace_id,
        employee_id=uuid4(),
        actor_user_id="viewer",
        intent="business_fact",
        business_scope=ResolvedBusinessScope(
            workspace_id=workspace_id, relation_kind="none"
        ),
        budget=_budget(max_table_records=1),
        sources=(source,),
    )
    attack = tuple(
        _evidence(ordinal=index).model_copy(
            update={
                "source_version": 7,
                "scope": EvidenceScope(
                    workspace_id=workspace_id,
                    base_id=uuid4(),
                    table_id=uuid4(),
                    view_id=unplanned_view_id,
                )
            }
        )
        for index in (1, 2)
    )
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=plan,
            status="internal_evidence",
            evidence=attack,
            omissions=(),
            usage=_usage(attack),
        )
    over_count = tuple(
        item.model_copy(
            update={
                "scope": item.scope.model_copy(update={"view_id": planned_view_id})
            }
        )
        for item in attack
    )
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=plan,
            status="internal_evidence",
            evidence=over_count,
            omissions=(),
            usage=_usage(over_count),
        )
    wrong_source_version = (over_count[0].model_copy(
        update={"source_version": source.source_version + 1}
    ),)
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=plan,
            status="internal_evidence",
            evidence=wrong_source_version,
            omissions=(),
            usage=_usage(wrong_source_version),
        )


def test_validate_context_pack_rejects_constructed_unplanned_table_evidence() -> None:
    workspace_id = uuid4()
    planned_view_id = uuid4()
    source = ContextSourcePlan(
        source_kind="table_view",
        priority=1,
        view_id=planned_view_id,
        source_version=5,
        max_items=1,
        reason_code="business_fact_requested",
    )
    plan = ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=workspace_id,
        employee_id=uuid4(),
        actor_user_id="viewer",
        intent="business_fact",
        business_scope=ResolvedBusinessScope(
            workspace_id=workspace_id, relation_kind="none"
        ),
        budget=_budget(max_table_records=1),
        sources=(source,),
    )
    evidence = tuple(
        EvidenceItem.model_construct(
            evidence_id=f"business_data:{index:02d}",
            label="business_data",
            source_type="platform_record",
            scope=EvidenceScope(
                workspace_id=workspace_id,
                base_id=uuid4(),
                table_id=uuid4(),
                view_id=uuid4(),
            ),
            version=EvidenceVersion(kind="record", value=1),
            source_version=5,
            content={"title": "safe"},
            truncated=False,
            truncated_paths=(),
        )
        for index in (1, 2)
    )
    pack = ContextPack.model_construct(
        plan=plan,
        status="internal_evidence",
        evidence=evidence,
        omissions=(),
        usage=_usage(evidence),
    )
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        validate_context_pack(pack)


@pytest.mark.parametrize("missing", ("base_id", "table_id", "view_id"))
def test_context_pack_requires_complete_table_source_scope(missing: str) -> None:
    workspace_id = uuid4()
    view_id = uuid4()
    plan = ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=workspace_id,
        employee_id=uuid4(),
        actor_user_id="viewer",
        intent="business_fact",
        business_scope=ResolvedBusinessScope(
            workspace_id=workspace_id, relation_kind="none"
        ),
        budget=_budget(max_table_records=1),
        sources=(
            ContextSourcePlan(
                source_kind="table_view",
                priority=1,
                view_id=view_id,
                source_version=3,
                max_items=1,
                reason_code="business_fact_requested",
            ),
        ),
    )
    scope_values = {
        "workspace_id": workspace_id,
        "base_id": uuid4(),
        "table_id": uuid4(),
        "view_id": view_id,
    }
    scope_values[missing] = None
    evidence = (_evidence().model_copy(
        update={"scope": EvidenceScope(**scope_values), "source_version": 3}
    ),)
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=plan,
            status="internal_evidence",
            evidence=evidence,
            omissions=(),
            usage=_usage(evidence),
        )


def test_context_pack_enforces_memory_source_limit_and_business_scope() -> None:
    workspace_id = uuid4()
    customer_id = uuid4()
    project_id = uuid4()
    plan = ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=workspace_id,
        employee_id=uuid4(),
        actor_user_id="viewer",
        intent="memory_lookup",
        business_scope=ResolvedBusinessScope(
            workspace_id=workspace_id,
            customer_record_id=customer_id,
            customer_version=1,
            project_record_id=project_id,
            project_version=1,
            relation_kind="visible_linked_record",
        ),
        budget=_budget(max_memory_items=2),
        sources=(
            ContextSourcePlan(
                source_kind="business_memory",
                priority=2,
                max_items=1,
                reason_code="memory_requested",
            ),
        ),
    )
    memory = tuple(
        _evidence(label="confirmed_memory", ordinal=index).model_copy(
            update={
                "scope": EvidenceScope(
                    workspace_id=workspace_id,
                    customer_record_id=customer_id,
                    project_record_id=project_id,
                )
            }
        )
        for index in (1, 2)
    )
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=plan,
            status="internal_evidence",
            evidence=memory,
            omissions=(),
            usage=_usage(memory),
        )
    wrong_scope = (memory[0].model_copy(
        update={"scope": EvidenceScope(workspace_id=workspace_id)}
    ),)
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=plan,
            status="internal_evidence",
            evidence=wrong_scope,
            omissions=(),
            usage=_usage(wrong_scope),
        )


@pytest.mark.parametrize(
    "update",
    (
        {"content": {"internal_evidence": True}},
        {"version": EvidenceVersion(kind="contract", value=2)},
        {"scope": EvidenceScope(workspace_id=uuid4(), base_id=uuid4())},
        {"truncated": True, "truncated_paths": ("$.internal_evidence",)},
    ),
)
def test_context_pack_requires_fixed_policy_marker(update: dict[str, object]) -> None:
    plan = _plan()
    marker = _evidence(label="general_advice").model_copy(
        update={
            "scope": EvidenceScope(workspace_id=plan.workspace_id),
            "content": {"internal_evidence": False},
            **update,
        }
    )
    evidence = (marker,)
    with pytest.raises(ValidationError, match="context_pack_source_invalid"):
        ContextPack(
            plan=plan,
            status="general_advice_only",
            evidence=evidence,
            omissions=(),
            usage=_usage(evidence),
        )


def test_context_pack_rejects_constructed_item_over_its_item_budget() -> None:
    source = ContextSourcePlan(
        source_kind="table_view",
        priority=1,
        view_id=uuid4(),
        source_version=1,
        max_items=1,
        reason_code="business_fact_requested",
    )
    plan = _plan(
        intent="business_fact",
        sources=(source,),
        budget=_budget(max_table_records=1, max_item_chars=128),
    )
    evidence = _evidence(content={"title": "x" * 200}).model_copy(
        update={
            "scope": EvidenceScope(
                workspace_id=plan.workspace_id,
                base_id=uuid4(),
                table_id=uuid4(),
                view_id=source.view_id,
            )
        }
    )
    chars = len(json.dumps(evidence.content, sort_keys=True, separators=(",", ":")))
    with pytest.raises(ValidationError, match="context_pack_usage_invalid"):
        ContextPack(
            plan=plan,
            status="internal_evidence",
            evidence=(evidence,),
            omissions=(),
            usage=ContextBudgetUsage(
                table_records_considered=1,
                table_records_selected=1,
                memory_items_considered=0,
                memory_items_selected=0,
                evidence_items=1,
                content_chars=chars,
                truncated_items=0,
                omitted_items=0,
            ),
        )


def test_context_pack_validates_counts_status_and_content_budget() -> None:
    request = _request(intent="general_advice", view_ids=())
    plan = ContextPlan(
        contract_version="stage08-context-plan.v1",
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        actor_user_id="viewer",
        intent="general_advice",
        business_scope=ResolvedBusinessScope(
            workspace_id=request.workspace_id, relation_kind="none"
        ),
        budget=request.budget,
        sources=(
            ContextSourcePlan(
                source_kind="general_advice",
                priority=1,
                max_items=1,
                reason_code="general_advice_requested",
            ),
        ),
    )
    evidence = EvidenceItem(
        evidence_id="general_advice:01",
        label="general_advice",
        source_type="policy_marker",
        scope=EvidenceScope(workspace_id=request.workspace_id),
        version=EvidenceVersion(kind="contract", value=1),
        content={"internal_evidence": False},
        truncated=False,
        truncated_paths=(),
    )
    with pytest.raises(ValidationError, match="context_pack_usage_invalid"):
        ContextPack(
            plan=plan,
            status="general_advice_only",
            evidence=(evidence,),
            omissions=(),
            usage=ContextBudgetUsage(
                table_records_considered=0,
                table_records_selected=0,
                memory_items_considered=0,
                memory_items_selected=0,
                evidence_items=0,
                content_chars=27,
                truncated_items=0,
                omitted_items=0,
            ),
        )
