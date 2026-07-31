from __future__ import annotations

import json

import pytest

from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    specialist_payload_sha256,
)
from app.services.agent_composer_v2 import (
    ComposerSectionOrderingPlanV1,
)
from app.services.agent_specialists_v2.daily import DailySpecialistV2
from app.services.agent_specialists_v2.risk import RiskSpecialistV2
from app.workers import stage12_action_runtime as durable_action_worker

from scripts.stage12_isolated_af_runner import (
    IsolatedAFExecutor,
    run_isolated_af_campaign,
    validate_isolated_execution_request,
)
from scripts.stage12_real_quality_report import build_execution_request
from scripts.stage12_quality_evaluation import build_stage12_truth_cases, score_case_v2


def _case(case_id: str):
    return next(item for item in build_stage12_truth_cases() if item.case_id == case_id)


def _execute_case(case_id: str, *, materialize_actions: bool = False):
    case = _case(case_id)
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=materialize_actions,
    )
    return IsolatedAFExecutor()(request)


class _ObservedComposerProvider:
    def __init__(self) -> None:
        self.call_count = 0
        values = {
            "version": "provider-attempt.v1",
            "role": "composer",
            "profile_id": "composer.zh.baseline.v1",
            "provider": "openrouter-compatible",
            "model_id": "google/gemini-2.5-flash",
            "attempt": 1,
            "status": "completed",
            "failure_code": None,
            "latency_ms": 11,
            "input_tokens": 25,
            "output_tokens": 9,
            "repair": False,
        }
        values["observation_hash"] = specialist_payload_sha256(values)
        self.observations = (ProviderAttemptObservationV1.model_validate(values),)

    def __call__(self, request):
        self.call_count += 1
        handles = tuple(item.section_handle for item in request.candidates)
        return ComposerSectionOrderingPlanV1(
            ordered_section_handles=handles,
            connector_by_handle={
                item.section_handle: (
                    "direct"
                    if index == 0
                    else next(
                        code
                        for code in item.allowed_connector_codes
                        if code != "direct"
                    )
                )
                for index, item in enumerate(request.candidates)
            },
        )


class _InvalidOrderingComposerProvider:
    observations: tuple[ProviderAttemptObservationV1, ...] = ()

    def __call__(self, request):
        first = request.candidates[0].section_handle
        unknown = "section:sha256:" + "f" * 64
        return ComposerSectionOrderingPlanV1.model_construct(
            ordered_section_handles=(first, unknown),
            connector_by_handle={first: "direct", unknown: "however"},
        )


def test_isolated_runner_rejects_gold_action_target_field_and_value_hints() -> None:
    base = {
        "query": "测试",
        "round_id": "round-01",
        "runtime_context": {
            "execution_id": "execution:sha256:" + "a" * 64,
            "materialize_actions": False,
        },
    }
    for key, value in (
        ("expected_result_record_ids", ["MT-001"]),
        ("action_kind", "record.update"),
        ("target_selector", {"record_code": "MT-001"}),
        ("required_fields", ["status"]),
        ("assignments", {"status": "done"}),
    ):
        request = {
            **base,
            "runtime_context": {**base["runtime_context"], key: value},
        }
        with pytest.raises(ValueError, match="isolated_af_truth_hint_forbidden"):
            validate_isolated_execution_request(request)


def test_isolated_runner_executes_raw_join_query_with_sanitized_stage_hashes() -> None:
    case = _case("join_01")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    executor = IsolatedAFExecutor()

    trace = executor(request)
    observation = executor.observations[request["runtime_context"]["execution_id"]]

    assert trace.case_id == request["runtime_context"]["execution_id"]
    assert trace.round_id == "round-01"
    assert trace.planner is not None
    assert trace.query.observation_status == "observed"
    assert trace.durability.terminal is True
    assert observation.status == "completed"
    assert {item.stage for item in observation.stages} == {
        "planner",
        "query",
        "retrieval",
        "specialists",
        "claim_graph",
        "composer",
        "action",
        "total",
    }
    assert all(item.input_hash and item.latency_ms >= 0 for item in observation.stages)
    assert observation.production_write_count == 0
    assert observation.telegram_send_count == 0


def test_isolated_runner_emits_real_composer_provider_metadata() -> None:
    case = _case("join_01")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    provider = _ObservedComposerProvider()
    executor = IsolatedAFExecutor(composer_provider=provider)

    trace = executor(request)
    observation = executor.observations[request["runtime_context"]["execution_id"]]

    assert trace.provider is not None
    assert trace.provider.provider == "openrouter-compatible"
    assert trace.provider.model == "google/gemini-2.5-flash"
    assert trace.provider.profile == "composer.zh.baseline.v1"
    assert provider.call_count == 1
    assert observation.provider_attempts == provider.observations
    assert observation.provider_attempts[0].latency_ms == 11


@pytest.mark.parametrize("case_id", ("mixed_02", "mixed_08"))
def test_invalid_composer_ordering_keeps_complete_safe_trace(case_id: str) -> None:
    case = _case(case_id)
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    executor = IsolatedAFExecutor(composer_provider=_InvalidOrderingComposerProvider())

    trace = executor(request)
    observation = executor.observations[request["runtime_context"]["execution_id"]]

    assert observation.status == "completed"
    assert trace.planner is not None
    assert trace.query.observation_status == "observed"
    assert trace.answer.observation_status == "observed"
    assert trace.answer.render_receipt is not None
    assert trace.safety.unauthorized_effect_count == 0
    assert trace.safety.external_send_count == 0


@pytest.mark.parametrize(
    ("case_id", "handler_type"),
    (
        ("risk_01", RiskSpecialistV2),
        ("daily_01", DailySpecialistV2),
    ),
)
def test_isolated_runner_invokes_distinct_typed_handlers_from_raw_query(
    monkeypatch,
    case_id: str,
    handler_type: type,
) -> None:
    calls = []
    original = handler_type.execute

    def observed_execute(self, command, context):
        calls.append((command.objective_id, command.capability_id))
        return original(self, command, context)

    monkeypatch.setattr(handler_type, "execute", observed_execute)

    trace = _execute_case(case_id)

    assert trace.durability.terminal is True
    assert len(calls) >= 1


def test_risk_specialist_trace_owns_derived_facts_used_by_answer_grounding() -> None:
    case = _case("risk_01")
    trace = _execute_case("risk_01")

    risk_traces = tuple(
        item
        for item in trace.specialists
        if item.capability_id == "platform.risk.analyse"
    )
    assert len(risk_traces) == 1
    assert risk_traces[0].artifact_kind == "risk_assessment_set"
    assert risk_traces[0].derived_facts
    assert {item.predicate for item in risk_traces[0].derived_facts} == {
        "risk_severity"
    }
    assert any(claim.predicate == "risk_severity" for claim in trace.answer.claims)
    assert all(
        fact.fact_id not in {item.fact_id for item in trace.query.facts}
        for fact in risk_traces[0].derived_facts
    )
    score = score_case_v2(case, trace)
    assert score.query.gate_pass is True
    assert score.answer.grounded_claim_precision == 1.0
    assert score.answer.unsupported_claim_rate == 0.0
    assert score.final_answer.factual_correctness is True


@pytest.mark.parametrize(
    ("case_id", "action_kind", "existing_record_target"),
    (
        ("draft_01", "record.update", True),
        ("draft_04", "record.create", False),
        ("task_01", "task.create", False),
    ),
)
def test_action_kinds_use_durable_specialist_without_fake_record_identity(
    monkeypatch,
    case_id: str,
    action_kind: str,
    existing_record_target: bool,
) -> None:
    calls = []
    original = durable_action_worker.propose_durable_action

    def observed_proposal(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(
        durable_action_worker,
        "propose_durable_action",
        observed_proposal,
    )
    case = _case(case_id)
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    executor = IsolatedAFExecutor()

    trace = executor(request)
    observation = executor.observations[request["runtime_context"]["execution_id"]]

    assert trace.actions
    assert calls
    assert calls[0]["candidate_set"].action_kind == action_kind
    assert calls[0]["candidate_set"].target_table_ids
    if existing_record_target:
        assert calls[0]["candidate_set"].candidates
        assert calls[0]["private_payload"].target_record_ids
    else:
        assert calls[0]["candidate_set"].candidates == ()
        assert calls[0]["private_payload"].target_record_ids == ()
        assert all(
            assignment.record_id is None
            for assignment in calls[0]["private_payload"].assignments
        )
    assert "platform.action.propose" in (
        observation.trace_ledger.latency.specialist_ms_by_capability
    )


def test_isolated_runner_emits_complete_approved_observability_ledger() -> None:
    case = _case("daily_01")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    provider = _ObservedComposerProvider()
    executor = IsolatedAFExecutor(composer_provider=provider)

    trace = executor(request)
    observation = executor.observations[request["runtime_context"]["execution_id"]]
    ledger = observation.trace_ledger

    assert ledger.planner_version == "task-spec.v2"
    assert len(ledger.task_spec_hash) == 64
    assert ledger.objective_count == len(trace.planner.objectives)
    assert len(ledger.query_plan_hash) == 64
    assert set(ledger.candidate_count_by_source) == {"entity_linker", "retrieval"}
    assert ledger.selected_evidence_count == len(
        trace.retrieval.selected_evidence_record_ids
    )
    assert ledger.relation_traversal_count == len(trace.query.relation_paths)
    assert ledger.provider_attempt_count == 1
    assert ledger.input_tokens == 25
    assert ledger.output_tokens == 9
    assert sum(ledger.objective_status_counts.values()) == len(trace.planner.objectives)
    assert sum(ledger.action_slot_status_counts.values()) == len(trace.actions)
    assert ledger.scope_revalidation_count >= 2
    assert ledger.latency.admission_ms >= 0
    assert ledger.latency.planning_ms >= 0
    assert ledger.latency.schema_resolution_ms >= 0
    assert ledger.latency.structured_query_ms >= 0
    assert ledger.latency.semantic_retrieval_ms >= 0
    assert ledger.latency.specialist_ms_by_capability
    assert ledger.latency.provider_ms_by_role == {"composer": 11}
    assert ledger.latency.fan_in_ms >= 0
    assert ledger.latency.action_persistence_ms >= 0
    assert ledger.latency.total_ms >= 0


def test_isolated_runner_deduplicates_overlapping_facts_across_query_intents() -> None:
    case = _case("join_08")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    executor = IsolatedAFExecutor()

    trace = executor(request)
    observation = executor.observations[request["runtime_context"]["execution_id"]]

    assert observation.status == "completed"
    fact_ids = tuple(item.fact_id for item in trace.query.facts)
    assert len(fact_ids) == len(set(fact_ids))


def test_isolated_runner_materializes_only_unconfirmed_action_proposals() -> None:
    case = _case("draft_04")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    executor = IsolatedAFExecutor()

    trace = executor(request)
    observation = executor.observations[request["runtime_context"]["execution_id"]]

    assert observation.status == "completed"
    assert trace.actions
    assert observation.confirmed_action_count == 0
    assert observation.production_write_count == 0
    assert observation.telegram_send_count == 0
    assert all(item.external_effect_count == 0 for item in trace.actions)
    assert all(
        item.persistence_status in {"pending_confirmation", "denied", "degraded"}
        for item in trace.actions
    )


def test_isolated_action_status_reaches_final_answer_receipt() -> None:
    case = _case("draft_04")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    trace = IsolatedAFExecutor()(request)

    assert trace.actions
    assert trace.answer.render_receipt is not None
    expected_slots = {item.slot.slot_id for item in trace.actions if item.slot}
    assert set(trace.answer.render_receipt.covered_action_slot_ids) == expected_slots
    assert "actions" in trace.answer.render_receipt.section_kinds
    assert "未执行" in trace.answer.rendered_answer


def test_isolated_permission_denial_is_derived_and_disclosed() -> None:
    case = _case("permission_01")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    trace = IsolatedAFExecutor()(request)

    assert trace.safety.permission_outcome == "denied"
    assert trace.query.observation_status == "observed"
    assert trace.query.complete is True
    assert trace.query.result_record_ids == ()
    assert trace.retrieval.observation_status == "observed"
    assert trace.retrieval.complete is True
    assert trace.answer.render_receipt is not None
    assert "denial" in trace.answer.render_receipt.section_kinds
    assert "拒绝" in trace.answer.rendered_answer


@pytest.mark.parametrize("case_id", ("draft_01", "task_01", "reminder_01"))
def test_action_only_entity_lookup_is_evidence_not_answer_result(case_id: str) -> None:
    trace = _execute_case(case_id, materialize_actions=True)

    assert trace.query.result_record_ids == ()
    assert trace.query.evidence_record_ids


def test_filtered_action_only_targets_are_evidence_not_results() -> None:
    trace = _execute_case("reminder_03", materialize_actions=True)

    assert trace.query.result_record_ids == ()
    assert set(trace.query.evidence_record_ids) >= {
        "MT-001",
        "MT-004",
        "MT-012",
        "MT-014",
    }


@pytest.mark.parametrize(
    ("case_id", "owner_code", "source_code"),
    (
        ("reminder_01", "OWNER-ATLAS", "MT-001"),
        ("reminder_02", "OWNER-BEACON", "MT-004"),
        ("reminder_04", "OWNER-FJORD", "MT-017"),
    ),
)
def test_direct_reminder_trace_preserves_authorized_owner_and_source(
    case_id: str,
    owner_code: str,
    source_code: str,
) -> None:
    trace = _execute_case(case_id, materialize_actions=True)

    assert trace.actions[0].slot is not None
    assert trace.actions[0].slot.target_selector == {
        "owner_code": owner_code,
        "source_record_codes": [source_code],
    }


def test_explicit_daily_summary_keeps_filtered_records_as_results() -> None:
    trace = _execute_case("mixed_03", materialize_actions=True)

    assert set(trace.query.result_record_ids) == {
        "MT-001",
        "MT-004",
        "MT-012",
        "MT-014",
        "MT-017",
    }


def test_task_action_trace_projects_authorized_linked_assignments_to_codes() -> None:
    trace = _execute_case("task_01", materialize_actions=True)

    assert len(trace.actions) == 1
    assert trace.actions[0].proposed_values["project_link"] == ["PRJ-ATLAS"]
    assert trace.actions[0].proposed_values["assignee"] == ["OWNER-ATLAS"]


def test_date_aware_action_replan_preserves_case_clock_and_deadlines() -> None:
    task_trace = _execute_case("task_02", materialize_actions=True)
    reminder_trace = _execute_case("reminder_01", materialize_actions=True)

    task = task_trace.actions[0]
    reminder = reminder_trace.actions[0]
    assert task.slot is not None
    assert reminder.slot is not None
    assert task.proposed_values["due_date"] == "2026-07-29"
    assert task.slot.deadline_start_utc.isoformat() == "2026-07-28T16:00:00+00:00"
    assert task.slot.deadline_end_utc.isoformat() == "2026-07-29T16:00:00+00:00"
    assert reminder.proposed_values == {}
    assert reminder.slot.deadline_start_utc == task.slot.deadline_start_utc
    assert reminder.slot.deadline_end_utc == task.slot.deadline_end_utc


def test_isolated_denied_action_still_reaches_final_receipt_without_admission() -> None:
    case = _case("permission_02")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    trace = IsolatedAFExecutor()(request)

    assert len(trace.actions) == 1
    assert trace.actions[0].persistence_status == "denied"
    assert trace.actions[0].proposed_values == {}
    assert trace.actions[0].external_effect_count == 0
    assert trace.answer.render_receipt is not None
    assert len(trace.answer.render_receipt.covered_action_slot_ids) == 1
    assert "action_denied" in trace.answer.render_receipt.disclosure_codes


def test_isolated_optional_specialist_failure_is_explicitly_degraded() -> None:
    case = _case("fault_01")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    trace = IsolatedAFExecutor()(request)

    assert trace.answer.claims
    assert trace.answer.render_receipt is not None
    assert "degradation" in trace.answer.render_receipt.section_kinds
    assert "降级" in trace.answer.rendered_answer


def test_isolated_required_version_failure_refuses_stale_action() -> None:
    case = _case("fault_02")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    trace = IsolatedAFExecutor()(request)

    assert len(trace.actions) == 1
    assert trace.actions[0].target_code == "MT-014"
    assert trace.actions[0].record_version == 1
    assert trace.actions[0].persistence_status == "denied"
    assert trace.actions[0].denial_reason == "record_version_conflict"
    assert trace.actions[0].fault_mode == "record_version_drift"
    assert trace.actions[0].proposed_values == {}
    assert trace.answer.render_receipt is not None
    assert "action_denied" in trace.answer.render_receipt.disclosure_codes
    assert "已拒绝" in trace.answer.rendered_answer
    assert "已生成待确认提议" not in trace.answer.rendered_answer


def test_isolated_partial_permission_retains_facts_and_discloses_boundary() -> None:
    case = _case("permission_04")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    trace = IsolatedAFExecutor()(request)

    assert trace.safety.permission_outcome == "partial"
    assert trace.answer.claims
    assert trace.answer.render_receipt is not None
    assert "denial" in trace.answer.render_receipt.section_kinds
    assert "degradation" not in trace.answer.render_receipt.section_kinds


def test_isolated_mixed_action_permission_is_derived_as_partial() -> None:
    case = _case("mixed_06")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    trace = IsolatedAFExecutor()(request)

    assert trace.safety.permission_outcome == "partial"
    assert {item.persistence_status for item in trace.actions} == {
        "denied",
        "pending_confirmation",
    }
    assert any(
        item.denial_reason == "field_permission_denied" for item in trace.actions
    )
    assert trace.answer.render_receipt is not None
    assert "action_denied" in trace.answer.render_receipt.disclosure_codes


def test_isolated_reminder_request_is_never_reported_as_sent() -> None:
    case = _case("reminder_03")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=True,
    )
    trace = IsolatedAFExecutor()(request)

    assert len(trace.actions) == len(case.expected_task_spec.action_slots)
    assert trace.safety.external_send_count == 0
    assert trace.answer.render_receipt is not None
    assert "actions" in trace.answer.render_receipt.section_kinds
    assert len(trace.answer.render_receipt.covered_action_slot_ids) == len(
        trace.actions
    )
    assert "未执行" in trace.answer.rendered_answer
    assert "已发送" not in trace.answer.rendered_answer


@pytest.mark.parametrize("case_id", ("join_01", "join_08"))
def test_isolated_relation_outputs_preserve_required_result_identities(
    case_id: str,
) -> None:
    case = _case(case_id)
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={"workspace_mode": "fresh_in_memory"},
        materialize_actions=False,
    )
    trace = IsolatedAFExecutor()(request)

    assert set(trace.query.result_record_ids) == set(
        case.expected_query_result.required_result_records
    )
    assert set(trace.query.evidence_record_ids) <= set(
        case.expected_query_result.allowed_evidence_records
    )
    assert set(trace.query.relation_paths) == set(
        case.expected_query_result.relation_paths
    )


def test_ungrouped_aggregate_projects_null_group_key() -> None:
    trace = _execute_case("daily_04")
    aggregate = next(
        item for item in trace.query.aggregates if item.name == "blocked_work_items"
    )

    assert aggregate.group_key is None


def test_daily_aggregate_claims_preserve_semantic_output_names() -> None:
    trace = _execute_case("daily_01")
    aggregate_claims = {
        (item.subject, item.predicate, item.value)
        for item in trace.answer.claims
        if item.claim_type == "aggregate"
    }

    assert aggregate_claims == {
        ("completed", "__all__", 5),
        ("in_progress", "__all__", 4),
        ("blocked", "__all__", 4),
    }


@pytest.mark.parametrize(
    "case_id, required",
    (
        (
            "join_03",
            {
                "RISK-001",
                "RISK-002",
                "RISK-004",
                "MT-001",
                "MT-002",
                "MT-004",
                "PRJ-ATLAS",
                "PRJ-BEACON",
            },
        ),
        ("join_04", {"MT-013", "MT-014", "MT-015"}),
        ("join_05", {"MT-016", "MT-017"}),
        ("mixed_02", {"MT-014", "PRJ-EMBER"}),
        ("mixed_04", {"PRJ-ATLAS", "PRJ-BEACON", "MT-001", "MT-004"}),
        ("mixed_06", {"MT-012"}),
        ("mixed_08", {"MT-017"}),
    ),
)
def test_requested_result_roles_survive_join_and_action_context(
    case_id: str,
    required: set[str],
) -> None:
    trace = _execute_case(case_id)

    assert set(trace.query.result_record_ids) == required
    assert not set(trace.query.result_record_ids) & set(trace.query.evidence_record_ids)


def test_explicit_update_trace_preserves_target_and_denied_field() -> None:
    trace = _execute_case("mixed_06", materialize_actions=True)
    update = next(
        item
        for item in trace.actions
        if item.slot is not None and item.slot.action_kind == "record.update"
    )

    assert update.target_code == "MT-012"
    assert update.selected_fields == ("blocked_reason",)
    assert update.persistence_status == "denied"
    assert update.denial_reason == "field_permission_denied"


def test_conflict_trace_preserves_target_field_and_reason() -> None:
    trace = _execute_case("mixed_08", materialize_actions=True)
    update = next(
        item
        for item in trace.actions
        if item.slot is not None and item.slot.action_kind == "record.update"
    )

    assert (update.target_code, update.selected_fields) == ("MT-017", ("status",))
    assert update.persistence_status == "denied"
    assert update.denial_reason == "conflicting_assignments"


def test_multi_target_slots_share_one_objective_without_command_collision() -> None:
    trace = _execute_case("mixed_04", materialize_actions=True)
    tasks = [
        item
        for item in trace.actions
        if item.slot is not None and item.slot.action_kind == "task.create"
    ]

    assert len(tasks) == 2
    assert len({item.slot.objective_id for item in tasks}) == 1
    assert trace.answer.render_receipt is not None


def test_highest_risk_tie_is_denied_without_inventing_target() -> None:
    trace = _execute_case("mixed_01", materialize_actions=True)
    task = next(
        item
        for item in trace.actions
        if item.slot is not None and item.slot.action_kind == "task.create"
    )

    assert task.target_code is None
    assert task.persistence_status == "denied"
    assert task.denial_reason == "ambiguous_highest_risk_target"
    assert task.proposed_values == {}
    assert task.slot.target_selector == {
        "table_key": "tasks",
        "source_record_codes": ["MT-001", "MT-004", "MT-012", "MT-014"],
    }


def test_relation_derived_task_binding_uses_project_field() -> None:
    trace = _execute_case("mixed_02", materialize_actions=True)
    task = next(
        item
        for item in trace.actions
        if item.slot is not None and item.slot.action_kind == "task.create"
    )

    assert set(task.selected_fields) == {
        "title",
        "project_link",
        "priority",
        "status",
    }


def test_no_send_reminders_are_blocked_not_generic_denied() -> None:
    trace = _execute_case("mixed_03", materialize_actions=True)
    reminders = [
        item
        for item in trace.actions
        if item.slot is not None and item.slot.action_kind == "reminder.request"
    ]

    assert len(reminders) == 5
    assert {item.persistence_status for item in reminders} == {"blocked"}
    assert all(item.external_effect_count == 0 for item in reminders)


def test_expanded_reminder_trace_projects_authorized_concrete_targets() -> None:
    case = _case("reminder_03")
    trace = _execute_case("reminder_03", materialize_actions=True)

    expected = {
        json.dumps(item.target_selector, ensure_ascii=False, sort_keys=True)
        for item in case.expected_task_spec.action_slots
    }
    actual = {
        json.dumps(item.slot.target_selector, ensure_ascii=False, sort_keys=True)
        for item in trace.actions
        if item.slot is not None
    }

    assert actual == expected
    assert {item.target_code for item in trace.actions} == {
        "MT-001",
        "MT-004",
        "MT-012",
        "MT-014",
    }


def test_report_reminders_preserve_results_evidence_and_expand_targets() -> None:
    trace = _execute_case("mixed_07", materialize_actions=True)

    assert set(trace.query.result_record_ids) == {
        "PRJ-ATLAS",
        "PRJ-BEACON",
        "PRJ-FJORD",
        "MT-001",
        "MT-004",
        "MT-017",
    }
    assert set(trace.query.evidence_record_ids) == {"RISK-001", "RISK-004"}
    assert len(trace.actions) == 3
    assert {item.persistence_status for item in trace.actions} == {"blocked"}


def test_isolated_campaign_writes_atomic_sanitized_round_and_aggregate_artifacts(
    tmp_path,
) -> None:
    aggregate = run_isolated_af_campaign(
        output_dir=tmp_path,
        rounds=1,
        materialize_actions=True,
    )

    round_text = (tmp_path / "round-01.json").read_text(encoding="utf-8")
    aggregate_text = (tmp_path / "aggregate.json").read_text(encoding="utf-8")
    markdown = (tmp_path / "aggregate.md").read_text(encoding="utf-8")
    combined = round_text + aggregate_text

    assert aggregate["case_count"] == 48
    assert aggregate["completed_count"] == 48
    assert aggregate["failed_count"] == 0
    assert aggregate["production_write_count"] == 0
    assert aggregate["telegram_send_count"] == 0
    assert "execution:sha256:" in round_text
    assert '"query":' not in combined
    assert '"expected' not in combined
    assert '"gold' not in combined
    assert "48/48" in markdown
    assert not tuple(tmp_path.glob("*.tmp"))


def test_full_final_answer_gate_covers_all_48_cases_and_total_latency() -> None:
    executor = IsolatedAFExecutor()
    failures = {}

    for case in build_stage12_truth_cases():
        request = build_execution_request(
            case,
            round_id="round-01",
            runtime_context={"workspace_mode": "fresh_in_memory"},
            materialize_actions=True,
        )
        trace = executor(request)
        score = score_case_v2(case, trace)
        dimensions = {
            "planner": score.planner.gate_pass,
            "query": score.query.gate_pass,
            "retrieval": score.retrieval.gate_pass,
            "answer": score.answer.gate_pass,
            "final_answer": score.final_answer.gate_pass,
            "action": score.action.gate_pass,
            "safety": score.safety.gate_pass,
            "durability": score.durability.gate_pass,
            "release": score.release_gate_pass,
        }
        failed_dimensions = tuple(
            name for name, passed in dimensions.items() if not passed
        )
        if failed_dimensions:
            failures[case.case_id] = failed_dimensions
        assert "total" in trace.latency.segments_ms

    assert failures == {}
    assert len(executor.observations) == 48
    assert (
        sum(item.confirmed_action_count for item in executor.observations.values()) == 0
    )
    assert (
        sum(item.production_write_count for item in executor.observations.values()) == 0
    )
    assert sum(item.telegram_send_count for item in executor.observations.values()) == 0
