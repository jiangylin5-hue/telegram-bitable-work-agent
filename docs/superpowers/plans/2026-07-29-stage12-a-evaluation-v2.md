# Stage12-A Evaluation V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` and `superpowers:test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trustworthy, versioned Stage12-A evaluator for the existing 48 Chinese coordination cases, audit and correct the Gold truth, score each runtime layer from typed trace/artifact evidence, eliminate answer-regex and Gold-candidate leakage, and prove the evaluator with focused deterministic evidence without changing production runtime behavior. The large three-round real-LLM campaign is deliberately deferred to final Stage12 acceptance after the technical architecture work.

**Architecture:** Keep Stage11/r76 runtime and r75 evidence immutable. Add an evaluation-only V2 contract and scorer pipeline under `backend/scripts/`, with a checked-in 48-case JSON truth set and audit manifest. The V2 runner consumes a normalized `RuntimeTraceV2`; missing Stage11 evidence is reported as `not_observed` rather than reconstructed from answer text. Action end-to-end mode receives only the user query, authorized runtime candidate evidence and persisted action results; Gold values are passed exclusively to scorers after execution.

**Tech Stack:** Python 3.12+, Pydantic 2.x, pytest 8.x, existing FastAPI/SQLAlchemy/PostgreSQL/Redis/SSE/OpenRouter Stage11 runtime, JSON/Markdown evidence.

**Implementation status:** Focused foundation accepted on 2026-07-29. The user prioritized technical architecture and deferred the large real-LLM campaign. PostgreSQL replay is also deferred because the configured local role cannot create the pgvector extension. No commit is created here because the root handoff requires one final delivery commit after the broader Stage12 package.

## Global Constraints

- Scope is Stage12-A only. Do not implement TaskSpec V2 runtime, Authorized Query Engine, Embedding V2, Specialist V2, durable Action worker, Mini App UI, migration, API contract, permission-model change or deployment.
- Preserve `project-docs/08-implementation/evidence/stage11-r75-real-48case-report-2026-07-28.{json,md}` byte-for-byte.
- Preserve the effective authority intersection `agent_configured_scope ∩ caller_user_scope ∩ telegram_chat_scope` and all Stage11 Tool Gateway confirmation/external-send boundaries.
- Never infer retrieval candidates, selected evidence or result records from final answer regexes. Missing trace fields must remain explicitly `not_observed` and fail the corresponding release gate.
- End-to-end Action evaluation must never inject Gold `action_kind`, target, fields or values into Planner/Provider/candidate resolution. Gold is visible only to the scorer after runtime execution.
- Component-mode Provider evaluation may use a declared candidate fixture, but its metrics must be labeled `component` and never merged into end-to-end Action accuracy.
- Deterministic layers run once during Stage12-A. The full 48-case real-LLM layer runs at least three rounds and reports mean, minimum, standard deviation and Provider failure rate during final Stage12 acceptance after B–F.
- Permission safety and external-send safety are hard gates at `1.00`; no Overall score may offset them.
- The evaluation fixture uses fixed timezone `Asia/Shanghai`, fixed evaluation clock `2026-07-29T00:00:00+08:00`, fixed schema version and fixed source hashes.
- Do not print, persist or commit secrets, browser session tokens, raw provider credentials, raw hidden fields, real customer data or Telegram identifiers.
- Existing dirty Stage12 documentation belongs to the user. Preserve it and make only Stage12-A-aligned additions or status updates.
- Do not create intermediate Git commits. The active handoff requires one complete delivery commit only after implementation, tests, real evaluation, audit and documentation are complete.

---

### Task 1: Freeze Evaluation V2 contracts and report schema

**Files:**

- Create: `backend/scripts/stage12_quality_evaluation.py`
- Create: `backend/tests/unit/test_stage12_quality_evaluation_contracts.py`

**Interfaces:**

- Produces `EvaluationCaseV2`, `ExpectedTaskSpec`, `ExpectedObjective`, `ExpectedPredicate`, `ExpectedDependencyEdge`, `ExpectedQueryResult`, `ExpectedAggregate`, `ExpectedActionSlot`, `GoldAudit`, `RuntimeTraceV2`, `RuntimePlannerTrace`, `RuntimeQueryTrace`, `RuntimeAnswerTrace`, `RuntimeActionTrace`, `RuntimeSafetyTrace`, `RuntimeDurabilityTrace`, and `RuntimeLatencyTrace` Pydantic models. Score/report models are introduced test-first in Tasks 3–5 with the behavior they represent.
- Produces `load_truth_cases(path: Path) -> tuple[EvaluationCaseV2, ...]` and `canonical_sha256(value: object) -> str`.
- All models use `ConfigDict(extra="forbid", frozen=True, strict=True)` and version literals.

- [x] **Step 1: Write failing contract tests**

  Cover strict extra-field rejection, duplicate IDs, invalid dependency references, invalid predicate operator/type combinations, overlapping required/forbidden results, ActionSlot canonical enums, lowercase 64-hex hashes, fixed timezone/clock and JSON round-trip stability. Each expected value is a literal fixture independent of production helpers.

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest tests/unit/test_stage12_quality_evaluation_contracts.py -q`

  Expected: collection fails because `scripts.stage12_quality_evaluation` does not exist.

- [x] **Step 3: Implement the minimal strict contracts**

  Use these stable literals:

  ```python
  ObjectiveKind = Literal[
      "fact_query", "risk_analysis", "daily_summary", "record_change",
      "task_creation", "reminder_request", "restricted_request",
      "conflict_resolution",
  ]
  ActionKind = Literal["record.create", "record.update", "task.create", "reminder.request"]
  PermissionOutcome = Literal["allowed", "partial", "denied"]
  ObservationStatus = Literal["observed", "not_observed", "not_applicable"]
  EVALUATION_TIMEZONE = "Asia/Shanghai"
  EVALUATION_CLOCK = "2026-07-29T00:00:00+08:00"
  ```

  `ExpectedQueryResult` separates `required_result_records`, `allowed_evidence_records`, `forbidden_result_records`, `relation_paths` and typed `aggregates`. `RuntimeTraceV2` keeps Planner, Query, Retrieval, Answer, Action, Safety, Durability and segmented-latency observations separate.

- [x] **Step 4: Run focused tests and verify GREEN**

  Run: `python -m pytest tests/unit/test_stage12_quality_evaluation_contracts.py -q`

  Expected: all contract tests pass with no warnings.

- [x] **Step 5: Refactor without behavior change**

  Keep model validators focused: identity/graph validation, truth-set disjointness, metric bounds and version/hash validation. Re-run the same command.

### Task 2: Convert and manually audit all 48 Gold cases

**Files:**

- Create: `backend/tests/fixtures/stage12_complex_cases_v2.json`
- Create: `backend/tests/fixtures/stage12_complex_cases_v2.audit.json`
- Create: `backend/tests/unit/test_stage12_quality_truth_cases.py`
- Modify: `backend/scripts/stage12_quality_evaluation.py`

**Interfaces:**

- Produces `build_stage12_truth_cases() -> tuple[EvaluationCaseV2, ...]`.
- Produces `validate_truth_set(cases: tuple[EvaluationCaseV2, ...]) -> None`.
- Produces `audit_truth_set(cases: tuple[EvaluationCaseV2, ...], legacy_cases: tuple[ComplexCoordinationCase, ...], fixture_snapshot: Mapping[str, object]) -> GoldAuditReport` where hashes are calculated from canonical JSON and no Gold result is generated by an LLM.

- [x] **Step 1: Write failing 48-case conversion and audit tests**

  Assert: exactly 48 unique IDs and Chinese queries; category distribution remains `8/6/6/6/4/4/4/2/8`; every Objective and edge is normalized; every action uses canonical enum; required/allowed/forbidden result sets are disjoint; every case has a source fixture hash, schema version, audit status and reviewer field; aggregate cases have typed truth; permission cases have explicit outcomes.

  Add explicit regression assertions:

  ```python
  assert by_id["risk_02"].expected_query_result.required_result_records == ("MT-017",)
  assert "MT-008" in by_id["risk_02"].expected_query_result.forbidden_result_records
  assert len(by_id["mixed_08"].expected_task_spec.action_slots) == 2
  assert by_id["mixed_08"].expected_task_spec.action_slots[0].expected_outcome == "denied"
  assert by_id["mixed_08"].expected_task_spec.action_slots[1].expected_outcome == "pending_confirmation"
  ```

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest tests/unit/test_stage12_quality_truth_cases.py -q`

  Expected: fails because the V2 truth and audit files do not exist.

- [x] **Step 3: Build the literal V2 truth set from the fixed synthetic fixture**

  Convert legacy Objective names using this exact mapping:

  ```text
  fact -> fact_query
  risk -> risk_analysis
  daily_summary -> daily_summary
  record_change -> record_change
  task -> task_creation
  reminder -> reminder_request
  restricted_data -> restricted_request
  conflict -> conflict_resolution
  ```

  Convert action names using this exact mapping:

  ```text
  create_record -> record.create
  update_record -> record.update
  create_task -> task.create
  request_reminder -> reminder.request
  ```

  For every case, record exact predicates, relation paths, group/aggregate truth, result/evidence/forbidden identities, action assignments required for scoring and permission outcome. The fixture is literal checked-in JSON; loaders do not silently repair it.

- [x] **Step 4: Create the audit manifest**

  For each case store `case_id`, `legacy_hash`, `v2_hash`, `fixture_hash`, `reviewer`, `review_method`, `reviewed_at`, `change_reason` and `status`. `risk_02` must record the correction from `MT-008` to `MT-017`; unchanged cases record `converted_and_source_checked`. Initial reviewer value is `codex-source-audit`, and final Stage12-A acceptance must truthfully state that user/human sign-off is pending unless the user explicitly reviews the manifest.

- [x] **Step 5: Run truth tests and legacy compatibility tests**

  Run: `python -m pytest tests/unit/test_stage12_quality_truth_cases.py tests/unit/test_stage11_complex_coordination_eval.py -q`

  Expected: all tests pass; the legacy Stage11 source and r75 evidence remain unchanged.

### Task 3: Implement independent Planner, Query and Retrieval scorers

**Files:**

- Modify: `backend/scripts/stage12_quality_evaluation.py`
- Create: `backend/tests/unit/test_stage12_quality_planner_query_retrieval_scores.py`

**Interfaces:**

- Produces `score_planner(case, trace) -> PlannerScore`.
- Produces `score_query(case, trace) -> QueryScore`.
- Produces `score_retrieval(case, trace, *, k: int = 20) -> RetrievalScore`.
- Produces the strict `PlannerScore`, `QueryScore` and `RetrievalScore` Pydantic contracts required by those functions.
- Canonical Objective key is `(kind, normalized_entity_scope, normalized_output_contract)`; dependency edges include `(from_key, to_key, required)`.

- [x] **Step 1: Write failing scorer tests with hand-derived literals**

  Cover exact Objective/DAG match, extra Objective precision loss, missing Objective recall loss, Predicate exact mismatch, ActionSlot exclusion from Planner objective score, Query filter exactness, typed aggregate exactness, join-path exactness, per-table recall, allowed-evidence precision, forbidden-result violation, `not_observed` propagation and `K` denominator behavior.

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest tests/unit/test_stage12_quality_planner_query_retrieval_scores.py -q`

  Expected: fails because scorers are not implemented.

- [x] **Step 3: Implement the formulas from `02_EVALUATION_V2.md`**

  Retrieval reads only `RuntimeQueryTrace.candidate_record_ids`, `selected_evidence_ids`, table identity and relation traversal. It must never inspect `RuntimeAnswerTrace.rendered_answer`. For missing evidence, return `observation_status="not_observed"`, `gate_pass=False` and nullable metric values rather than a fabricated zero or one.

- [x] **Step 4: Run focused tests and mutation-check realistic faults**

  Run the focused command, then mentally/explicitly mutate extra objective, wrong edge, wrong predicate value, missing table candidates and wrong aggregate type; each mutation must be caught by at least one test.

### Task 4: Implement Answer, Action, Safety, Durability and latency scorers

**Files:**

- Modify: `backend/scripts/stage12_quality_evaluation.py`
- Create: `backend/tests/unit/test_stage12_quality_answer_action_safety_scores.py`

**Interfaces:**

- Produces `score_answer(case, trace) -> AnswerScore` based on typed `claims[]`, not answer text.
- Produces `score_actions(case, trace, *, mode: Literal["end_to_end", "component"]) -> ActionScore` with separate slot/target/field/value/confirmation/proposal/persistence/external-effect metrics.
- Produces `score_safety`, `score_durability`, `score_latency` and `score_case_v2`.
- Produces the strict `AnswerScore`, `ActionScore`, `SafetyScore`, `DurabilityScore`, `LatencyScore` and `CaseScoreV2` Pydantic contracts required by those functions.

- [x] **Step 1: Write failing tests**

  Cover supported/unsupported claims, required-fact recall, aggregate exactness, Slot exact but wrong target, target correct but wrong field, field correct but wrong value, confirmation-policy mismatch, proposal schema failure, persistence failure, duplicate side effect, permission denial with zero effects, Telegram send hard failure, terminal/recovery/idempotency, and segmented P50/P95/P99.

- [x] **Step 2: Run tests and verify RED**

  Run: `python -m pytest tests/unit/test_stage12_quality_answer_action_safety_scores.py -q`

  Expected: fails because the score functions do not exist.

- [x] **Step 3: Implement independent metrics and hard gates**

  `score_case_v2` may calculate an informational trend score, but `release_gate_pass` is the conjunction of every named release gate. Permission or external-send safety below `1.00` always fails. `component` Action results live under a separate report key and cannot populate end-to-end accuracy.

- [x] **Step 4: Run focused tests and verify GREEN**

  Run the focused command and then Tasks 1–4 unit tests together.

### Task 5: Build Stage11 trace/artifact adapter and leak-free report runner

**Files:**

- Create: `backend/scripts/stage12_stage11_trace_adapter.py`
- Create: `backend/scripts/stage12_real_quality_report.py`
- Create: `backend/tests/unit/test_stage12_stage11_trace_adapter.py`
- Create: `backend/tests/unit/test_stage12_real_quality_report.py`
- Modify only if tests prove necessary: `backend/scripts/stage11_real_complex_report.py`

**Interfaces:**

- Produces `collect_stage11_runtime_trace(run_id: UUID, ...) -> RuntimeTraceV2` by reading durable run/command/event/artifact/idempotency/action/audit state.
- Produces `run_v2_report(..., rounds: int, materialize_actions: bool) -> EvaluationReportV2`.
- Produces `validate_no_gold_leak(execution_request: object, case: EvaluationCaseV2) -> None` as a test helper guarding execution payloads.
- Produces the strict `EvaluationReportV2` and `GoldAuditReport` Pydantic contracts used by CLI/report serialization.

- [x] **Step 1: Write failing adapter tests with real in-memory/runtime UOW objects**

  Assert capability/objective/artifact/event/action/durability evidence maps into typed trace fields; absent candidate IDs remain `not_observed`; safe-view citations do not become candidate IDs; raw answer codes are ignored; scope and external-send deltas are captured.

- [x] **Step 2: Write failing no-oracle Action runner tests**

  Capture every request sent to Planner/Action Provider/candidate resolver. Assert none contains Gold action kind, Gold target, Gold required fields, Gold expected values or expected status unless those values independently appear in authorized runtime evidence. Assert the scorer receives Gold only after execution completes.

- [x] **Step 3: Run tests and verify RED**

  Run: `python -m pytest tests/unit/test_stage12_stage11_trace_adapter.py tests/unit/test_stage12_real_quality_report.py -q`

- [x] **Step 4: Implement the Stage11 adapter without production contract changes**

  Read existing PostgreSQL durable rows and validated `stage08-idempotency:*` artifacts. Do not add migration/API/SSE/runtime payload fields. If Stage11 did not persist candidate/evidence identities, emit `not_observed` and let the V2 baseline fail that gate explicitly.

- [x] **Step 5: Implement the leak-free library runner and freeze deferred real-run mode**

  The focused foundation exposes strict loaders, audit recomputation and `run_v2_report` as library interfaces. The historical r75 evidence is recorded as immutable and its unavailable Query/Retrieval/typed-claim/ActionSlot layers remain `not_observed`. A live API CLI is intentionally not added before the B–F runtime contracts exist; the later real campaign must use fresh per-round idempotency keys, revoke temporary sessions in `finally`, never confirm drafts and never send Telegram.

- [x] **Step 6: Run focused tests and verify GREEN**

  Run the focused command plus all Stage12-A unit tests.

### Task 6: Produce focused deterministic V2 evidence and freeze the deferred real-LLM protocol

**Files:**

- Create: `project-docs/08-implementation/evidence/stage12-a-evaluation-v2-baseline-2026-07-29.json`
- Create: `project-docs/08-implementation/evidence/stage12-a-evaluation-v2-baseline-2026-07-29.md`
- Deferred until post-architecture Stage12 acceptance: three versioned per-round JSON files and one aggregate Markdown/JSON report.

**Interfaces:**

- Evidence records truth/audit hashes, commit/diff identity, fixture/schema versions, query, TaskSpec observation, QueryPlan observation, candidate IDs, selected evidence IDs, claims, actions, persistence, safety deltas, Provider/model/profile, segmented latency and unavailable reasons.

- [x] **Step 1: Validate truth and audit files**

  Validate through the strict loaders and `audit_truth_set`; require 48/48 schema-valid cases and explicit audit rows.

- [x] **Step 2: Record the immutable r75 report as a non-convertible historical baseline**

  Verify retrieval/query/claim/action-slot layers absent from r75 are marked `not_observed`, not inferred. Do not fabricate a V2 score from the coarse report.

- [x] **Step 3: Run deterministic component baseline once**

  Evaluate contract validation, Gold hashes and scorer fixtures. Any nondeterminism fails immediately.

- [x] **Step 4: Freeze, but do not execute, the post-architecture real-LLM command and evidence contract**

  Document that the later run must use the existing ignored env file by path only; never print or copy its contents. It must keep the production public allowlist, Telegram configuration and deployment unchanged, report each round independently and aggregate mean/minimum/standard deviation/failure rate. Stage12-A acceptance records this execution as explicitly deferred by user priority, not passed.

- [x] **Step 5: Verify hard safety deltas**

  Require permission safety `1.00`, external-send safety `1.00`, Telegram send count `0`, and all materialized drafts/reminders remaining pending/blocked. Any failure stops acceptance.

### Task 7: Full regression, requirement-by-requirement acceptance and handoff

**Files:**

- Create: `project-docs/08-implementation/STAGE_12_A_EVALUATION_V2_ACCEPTANCE.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/README.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/02_EVALUATION_V2.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md`
- Modify: `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/README.md`
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`

- [x] **Step 1: Run focused Stage12-A tests**

  Run all new Stage12-A unit files and record exact counts/duration.

- [x] **Step 2: Run full backend regression**

  Run the repository's full pytest suite, preserving the existing real-subprocess test handling. Record passes, skips, deselections, warnings and unavailable tools exactly.

- [x] **Step 3: Run static and repository checks**

  Run `python -m compileall app scripts`, `git diff --check`, Alembic head check and secret/path audit. Run `ruff` only if installed; otherwise record it as skipped without claiming lint passed.

- [x] **Step 4: Audit every Stage12-A requirement against direct evidence**

  The acceptance matrix must enumerate all six Stage12-A implementation steps, the Evaluation V2 formulas, hard gates, 48-case Gold audit, no-oracle Action test, one focused deterministic run, the explicitly deferred three real rounds, r75 immutability, temporary cleanup and remaining gaps. Each row is `PASS`, `FAIL`, `BLOCKED`, `DEFERRED` or `NOT_APPLICABLE` with command, result and artifact path.

- [x] **Step 5: Update active truth and handoff honestly**

  Do not state the Evaluation V2 foundation accepted unless every revised exit condition has direct evidence. Human Gold sign-off must remain explicitly pending unless the user reviews the manifest. The deferred full real-Provider campaign does not block Stage12-B, but it must remain an open Stage12 final-acceptance gate.

- [x] **Step 6: Perform final diff and scope review**

  Confirm no Stage12-B–F runtime code, migration, API, permission, frontend, deployment or external-send change entered the diff. Preserve unrelated/user-owned changes.

- [ ] **Step 7: Commit only after the full package is accepted**

  Create one final commit only after all tests, real evidence, audit, documentation and cleanup pass. Do not push, deploy or update the PR without separate current authorization.
