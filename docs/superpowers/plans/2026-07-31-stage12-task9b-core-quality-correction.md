# Stage12 Task9B Core Quality Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct Planner, Authorized Query and ActionSlot semantics so the frozen 48 raw-query Cases can satisfy the Stage12 seven-dimensional final-answer hard gate without runtime Gold access.

**Architecture:** Preserve the existing `Query -> TaskSpec -> AuthorizedQueryPlan -> StructuredQueryResult -> ActionSlot/AuthorizedCandidateSet -> ClaimGraph -> Composer` pipeline. Fix semantic classification and role projection at their owning layers, then keep the isolated runner as a faithful trace adapter rather than a Case-specific repair surface.

**Tech Stack:** Python 3.12+, Pydantic v2, FastAPI service contracts, SQLAlchemy/PostgreSQL-compatible table services, pytest, Black.

## Current Status

- Task 1 Planner correction: `completed`
- Task 2 Authorized Query correction: `completed`
- Task 3 ActionSlot correction: `completed`
- Task 4 deterministic technical gate: `completed`
- Final result: final-answer `48/48`, safety `48/48`, complete release `26/48`
- Next gate: Human Gold `0/48`, then real Provider `0/3`
- Evidence: `project-docs/08-implementation/evidence/stage12-task9b-core-quality-correction-2026-07-31.md`

## Global Constraints

- Implement only the approved Task9B boundary in `STAGE_12_TASK9B_CORE_QUALITY_CORRECTION_SOURCE_OF_TRUTH.md`.
- Runtime code must not read Case IDs, expected truth, Gold audit data or score output.
- Do not change schema, migration head, public API, permission model, model/provider/profile or production activation.
- Write and observe one failing test before each production behavior change.
- Isolated acceptance must keep confirmed Action, business write, external notification and Telegram send at zero.
- Human Gold and exactly three real Provider rounds remain blocked until deterministic technical gates pass.
- Do not introduce `BusinessContextPack` or generic Agent memory anywhere in Stage12. The user explicitly moved business-context architecture to a future, separately designed and approved stage.
- **OUT-OF-SCOPE FREEZE:** any implementation, persistence, API/schema/permission contract, retrieval injection or acceptance dependency for business context is forbidden in this Stage12 plan.

---

### Task 1: Planner semantic Objective correction

**Files:**
- Modify: `backend/app/services/agent_query_lexical.py`
- Modify: `backend/app/services/agent_task_planner_v2.py`
- Test: `backend/tests/unit/test_agent_task_planner_v2.py`
- Test: `backend/tests/unit/test_stage12_isolated_af_runner.py`

**Interfaces:**
- Consumes: `PlannerRequestV2`, `LexicalQuery`, authorized schema/entity snapshot.
- Produces: `plan_task_v2(request) -> TaskSpecArtifact` with semantic Objectives, dependencies and logical ActionSlots.

- [ ] **Step 1: Write failing risk-boundary tests**

Add literal behavior tests proving that risk comparison, risk discrepancy, risk grouping/aggregation and risk-based ordering create `risk_analysis`, while linked-risk listing and Action-subordinate “解释风险依据” do not create an extra analysis Objective.

```python
@pytest.mark.parametrize("query", (
    "找出有 high 风险但状态不是 blocked 的事项。",
    "按风险级别汇总开放风险数量，并列出支撑记录编号。",
    "汇总今日阻塞项，按风险排序，生成管理日报。",
))
def test_analytical_risk_requests_create_one_risk_objective(query):
    spec = _plan(query)
    assert [item.kind for item in spec.objectives].count("risk_analysis") == 1

def test_action_risk_justification_does_not_create_standalone_analysis():
    spec = _plan("将 MT-017 的 priority 提议调整为 high，并解释风险依据。")
    assert [item.kind for item in spec.objectives] == ["fact_query", "record_change"]
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest -q tests/unit/test_agent_task_planner_v2.py -k "analytical_risk or risk_justification"`

Expected: analytical cases lack `risk_analysis`, while the Action-subordinate query currently adds one.

- [ ] **Step 3: Implement clause-aware risk semantics**

Add a private semantic classifier that uses lexical clauses, requested aggregation/comparison/group/order operations and Action spans. It returns true only for an independent analytical risk request. Replace the direct `any(token.kind == "risk_intent")` Objective branch with this classifier; retain source spans from the matching clauses.

- [ ] **Step 4: Verify Planner risk GREEN and existing field-value regressions**

Run: `python -m pytest -q tests/unit/test_agent_task_planner_v2.py -k "risk or field_values"`

Expected: all selected tests pass.

- [ ] **Step 5: Write failing restricted/default-fact and expansion tests**

```python
def test_restricted_write_without_read_has_no_synthetic_fact_objective():
    spec = _plan("把无权编辑的 MT-001 internal_note 改为已处理。")
    assert [item.kind for item in spec.objectives] == ["restricted_request", "record_change"]

def test_outside_scope_query_preserves_denied_fact_risk_and_task_intents():
    spec = _plan("查询当前 workspace 之外项目的风险并生成任务。")
    assert [item.kind for item in spec.objectives] == [
        "restricted_request", "fact_query", "risk_analysis", "task_creation"
    ]

def test_multi_target_task_slots_share_one_logical_objective():
    spec = _plan("为 Atlas 和 Beacon 分别创建一个跟进任务草稿")
    task_objectives = [item for item in spec.objectives if item.kind == "task_creation"]
    assert len(task_objectives) == 1
    assert {slot.objective_id for slot in spec.action_slots} == {
        task_objectives[0].objective_id
    }
```

- [ ] **Step 6: Run the new tests and verify RED**

Run: `python -m pytest -q tests/unit/test_agent_task_planner_v2.py -k "restricted_write_without_read or outside_scope_query or multi_target_task_slots"`

Expected: current unconditional fact creation and per-expanded-slot Objective creation fail the assertions.

- [ ] **Step 7: Implement semantic default-fact suppression and logical-action grouping**

Create the fact Objective only when the query has a read/analysis/summary need or an Action requires factual grounding. Create one action Objective per lexical action candidate before `_expand_separate_candidate`; all expanded slots reference it. Keep conflict Objective generation per conflicting logical action and preserve the eight-Objective/eight-slot bounds.

- [ ] **Step 8: Run Planner unit regression**

Run: `python -m pytest -q tests/unit/test_agent_query_lexical.py tests/unit/test_agent_task_planner_v2.py tests/unit/test_agent_task_spec_v2.py`

Expected: all tests pass with no warnings.

### Task 2: Authorized Query result, join and aggregate semantics

**Files:**
- Modify: `backend/app/services/agent_task_planner_v2.py`
- Modify: `backend/app/services/authorized_query_compiler.py`
- Modify: `backend/app/services/authorized_table_query.py`
- Modify: `backend/scripts/stage12_isolated_af_runner.py`
- Test: `backend/tests/unit/test_authorized_query_compiler.py`
- Test: `backend/tests/unit/test_authorized_table_query.py`
- Test: `backend/tests/unit/test_stage12_query_engine_evaluation.py`
- Test: `backend/tests/unit/test_stage12_isolated_af_runner.py`

**Interfaces:**
- Consumes: `TaskSpecV2.query_intents`, `AuthorizedQueryPlanV1`, `StructuredQueryResultV1`.
- Produces: requested records in `result_record_ids`, contextual records in `evidence_record_ids`, exact relation paths and canonical aggregate group keys.

- [ ] **Step 1: Write failing ungrouped aggregate normalization test**

```python
def test_ungrouped_aggregate_projects_null_group_key():
    trace = _execute_case("daily_04").query
    aggregate = next(item for item in trace.aggregates if item.name == "blocked_work_items")
    assert aggregate.group_key is None
```

- [ ] **Step 2: Run normalization test and verify RED**

Run: `python -m pytest -q tests/unit/test_stage12_isolated_af_runner.py -k ungrouped_aggregate`

Expected: `group_key` is the literal string `"null"`.

- [ ] **Step 3: Implement canonical JSON null normalization**

Change `_normalized_group_key` so `json.loads("null")` returns `None`, parsed strings return strings and non-string structured group keys remain in their canonical serialized form accepted by the trace contract.

- [ ] **Step 4: Verify aggregate GREEN**

Run: `python -m pytest -q tests/unit/test_stage12_isolated_af_runner.py -k "ungrouped_aggregate or aggregate"`

Expected: all selected tests pass.

- [ ] **Step 5: Write failing requested-result role tests**

Add raw-query tests with hand-derived identities:

```python
@pytest.mark.parametrize("case_id, required", (
    ("join_03", {"RISK-001", "RISK-002", "RISK-004", "MT-001", "MT-002", "MT-004", "PRJ-ATLAS", "PRJ-BEACON"}),
    ("join_04", {"MT-013", "MT-014", "MT-015"}),
    ("join_05", {"MT-016", "MT-017"}),
    ("mixed_02", {"MT-014", "PRJ-EMBER"}),
    ("mixed_04", {"PRJ-ATLAS", "PRJ-BEACON", "MT-001", "MT-004"}),
    ("mixed_06", {"MT-012"}),
    ("mixed_08", {"MT-017"}),
))
def test_requested_result_roles_survive_join_and_action_context(case_id, required):
    trace = _execute_case(case_id).query
    assert set(trace.result_record_ids) == required
    assert not set(trace.result_record_ids) & set(trace.evidence_record_ids)
```

- [ ] **Step 6: Run role tests and verify RED**

Run: `python -m pytest -q tests/unit/test_stage12_isolated_af_runner.py -k requested_result_roles`

Expected: all seven current role mismatches are visible without score inspection.

- [ ] **Step 7: Implement projection-owned result roles**

Preserve enough execution metadata to distinguish explicitly requested identity projections, requested linked target projections and context-only roots. In query execution, select the requested presentation table without dropping source-version and relation proofs. In the runner adapter, derive result roles from projected records/groups/explicit identity projections; remove the rule that demotes every entity when an Action Objective exists.

- [ ] **Step 8: Add join zero-match and relation-proof regression tests**

Assert that Ember/Fjord target work items remain results, the root project remains evidence where applicable, zero linked-risk aggregates remain exact and relation paths retain their direction.

- [ ] **Step 9: Run Query engine regression**

Run: `python -m pytest -q tests/unit/test_authorized_query_compiler.py tests/unit/test_authorized_table_query.py tests/unit/test_stage12_query_engine_evaluation.py tests/unit/test_stage12_isolated_af_runner.py -k "query or join or aggregate or result_role"`

Expected: selected Query tests pass and no forbidden/evidence identity appears as a result.

### Task 3: ActionSlot parsing and authorized expansion

**Files:**
- Modify: `backend/app/services/agent_task_planner_v2.py`
- Modify: `backend/app/services/agent_action_candidates.py`
- Modify: `backend/app/services/stage12_action_admission.py`
- Modify: `backend/scripts/stage12_isolated_af_runner.py`
- Test: `backend/tests/unit/test_agent_task_planner_v2.py`
- Test: `backend/tests/unit/test_stage12_action_candidates.py`
- Test: `backend/tests/unit/test_stage12_action_admission.py`
- Test: `backend/tests/unit/test_stage12_isolated_af_runner.py`

**Interfaces:**
- Consumes: `ActionSlotV1`, `StructuredQueryResultV1`, current field policy and source versions.
- Produces: `DurableAuthorizedCandidateSetV1`, durable Action rows and `RuntimeActionTrace` with safe targets, requested fields and exact controlled status.

- [ ] **Step 1: Write failing safe trace identity tests**

```python
def test_explicit_update_trace_preserves_target_and_denied_field():
    trace = _execute_case("mixed_06")
    update = next(item for item in trace.actions if item.slot.action_kind == "record.update")
    assert update.target_code == "MT-012"
    assert update.selected_fields == ("blocked_reason",)
    assert update.persistence_status == "denied"
    assert update.denial_reason == "field_permission_denied"

def test_conflict_trace_preserves_target_field_and_reason():
    trace = _execute_case("mixed_08")
    update = next(item for item in trace.actions if item.slot.action_kind == "record.update")
    assert (update.target_code, update.selected_fields) == ("MT-017", ("status",))
    assert update.denial_reason == "conflicting_assignments"
```

- [ ] **Step 2: Run trace tests and verify RED**

Run: `python -m pytest -q tests/unit/test_stage12_isolated_af_runner.py -k "preserves_target_and_denied_field or conflict_trace"`

Expected: target is `None` and denied selected fields are empty.

- [ ] **Step 3: Preserve safe target and requested field metadata**

Project explicit `record_codes` into `RuntimeActionTrace.target_code`. For denied/conflicted slots, use the Planner's `required_field_keys` for safe requested-field evidence while leaving proposed values empty when field authorization denies them.

- [ ] **Step 4: Verify trace identity GREEN**

Run the same focused command; expect both tests to pass.

- [ ] **Step 5: Write failing ambiguity, relation-binding and no-send reminder tests**

```python
def test_highest_risk_tie_is_denied_without_inventing_target():
    trace = _execute_case("mixed_01")
    task = next(item for item in trace.actions if item.slot.action_kind == "task.create")
    assert task.persistence_status == "denied"
    assert task.denial_reason == "ambiguous_highest_risk_target"

def test_relation_derived_task_binding_preserves_project_and_work_item_fields():
    trace = _execute_case("mixed_02")
    task = next(item for item in trace.actions if item.slot.action_kind == "task.create")
    assert set(task.selected_fields) == {"title", "project_link", "priority", "status"}

def test_no_send_reminders_are_blocked_not_generic_denied():
    trace = _execute_case("mixed_03")
    reminders = [item for item in trace.actions if item.slot.action_kind == "reminder.request"]
    assert len(reminders) == 5
    assert {item.persistence_status for item in reminders} == {"blocked"}
    assert all(item.external_effect_count == 0 for item in reminders)
```

- [ ] **Step 6: Run semantic Action tests and verify RED**

Run: `python -m pytest -q tests/unit/test_stage12_isolated_af_runner.py -k "highest_risk_tie or relation_derived_task or no_send_reminders"`

Expected: current code proposes the ambiguous task, selects the wrong source field and emits generic denials for reminders.

- [ ] **Step 7: Implement authorized candidate semantics**

For deferred create actions, inspect only the authorized structured result and relation proof: bind work-item/project source fields from matching tables; deny tied maximum candidates; expand `each_result` deterministically. Represent explicit no-send reminder admission as a durable blocked proposal with zero send authority. Do not add a send command.

- [ ] **Step 8: Run Action unit/API regression**

Run: `python -m pytest -q tests/unit/test_stage12_action_candidates.py tests/unit/test_stage12_action_admission.py tests/unit/test_stage12_action_materialization.py tests/unit/test_stage12_isolated_af_runner.py -k "action or reminder or target or conflict"`

Expected: all selected tests pass; confirmation/write/send counts remain zero.

### Task 4: Raw-query cross-layer acceptance

**Files:**
- Modify: `backend/tests/unit/test_stage12_isolated_af_runner.py`
- Modify: `backend/scripts/stage12_quality_evaluation.py` only if a scorer defect is independently proven; changing truth is forbidden
- Create: `project-docs/08-implementation/evidence/stage12-task9b-core-quality-correction-2026-07-31.md`
- Modify: `project-docs/08-implementation/STAGE_12_ARCHITECTURE_CORRECTION_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/README.md`
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`

**Interfaces:**
- Consumes: frozen 48 `EvaluationCaseV2` records and raw-query `IsolatedAFExecutor`.
- Produces: per-dimension counts, failing Case IDs/reasons, regression evidence and the next gate decision.

- [ ] **Step 1: Add a full-set hard-gate regression test**

The test executes all 48 raw queries without injecting truth and asserts receipt completeness, safety `48/48`, final-answer hard gate `48/48`, and zero confirmed/write/send effects. If complete Case release gates remain below `48/48`, the assertion reports exact component reasons instead of modifying Gold.

- [ ] **Step 2: Run full-set regression and verify RED before the final fixes**

Run: `python -m pytest -q tests/unit/test_stage12_isolated_af_runner.py -k full_final_answer_gate`

Expected: the existing 18 final-answer failures are reported.

- [ ] **Step 3: Complete only mechanism-level fixes exposed by the test**

Apply minimal changes in Tasks 1–3. Any new architecture, schema, API, permission or provider decision stops execution for user confirmation.

- [ ] **Step 4: Run deterministic 48 Case audit**

Run the raw-query report/scorer for one deterministic round and record all seven dimension counts plus complete Case release-gate count. Expected final-answer result: `48/48`; safety result: `48/48`.

- [ ] **Step 5: Run focused and Stage12 regression**

```text
python -m pytest -q tests/unit/test_agent_query_lexical.py tests/unit/test_agent_task_planner_v2.py tests/unit/test_authorized_query_compiler.py tests/unit/test_authorized_table_query.py tests/unit/test_stage12_action_candidates.py tests/unit/test_stage12_action_admission.py tests/unit/test_stage12_isolated_af_runner.py
python -m pytest tests/unit -q -k stage12
python -m black --check <changed Python files>
python -m compileall -q <changed Python modules and tests>
```

- [ ] **Step 6: Run safety and hygiene checks**

Scan changed files for Provider keys/tokens, Case IDs in production modules, forbidden Gold imports, trailing whitespace and temporary files. Ruff remains a passing claim only if the module is available and the command succeeds.

- [ ] **Step 7: Update evidence and stage truth**

Record actual Changed files, Verification, Skipped tests, Remaining risks and Temporary cleanup. Keep Human Gold at `0/48` and real Provider rounds at zero until the user separately signs the reviewer manifest.
