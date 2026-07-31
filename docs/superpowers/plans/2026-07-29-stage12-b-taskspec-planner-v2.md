# Stage12-B TaskSpec V2 and Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strict, permission-bounded `TaskSpec V2` planner that deterministically extracts Chinese query structure, emits multiple independent `ActionSlot`s, localizes conflicts and permission denials, and can shadow Stage11 without changing the plan that production dispatches.

**Architecture:** The planner is a pipeline of pure bounded stages: canonicalize and lex → bind only against an already-authorized schema snapshot → segment clauses → construct candidates → optionally resolve enumerated ambiguity → normalize/validate/cost → serialize a hash-stable artifact. Stage11 `build_task_plan` remains the sole dispatch plan during B; an opt-in workspace allowlisted shadow adapter records only sanitized hashes and metric deltas. Stage12-C owns QueryPlan execution and is explicitly outside this plan.

**Tech Stack:** Python 3.12+, Pydantic 2.x strict/frozen contracts, existing Stage06 platform UOW and authorization services, existing Stage11 task gateway, pytest 8.x.

**Confirmed boundary refinement (2026-07-29):** The user confirmed that Planner remains record-scan-free. A data-dependent action target is represented in B by `query_spec_ref + expansion_policy + resolution_status=deferred_query_result`; C computes the authorized result set and F expands concrete action candidates. B scores only the planning-time fields it owns; concrete result-dependent targets and persistence remain final C/F gates.

## Global Constraints

- Stage12-A acceptance is the prerequisite and remains evaluation-only.
- Scope is Stage12-B only. Do not implement Authorized Query Engine operators, record scans, Join execution, aggregation execution, Embedding/Chunk V2, Specialist V2, Provider answer changes, durable action worker, Mini App changes, migration, public API/SSE schema changes, deployment or Telegram send.
- Production dispatch continues to consume only `TaskPlan` from `build_task_plan`; `TaskSpecV2` is shadow-only throughout Stage12-B.
- Planner V2 must not expand a data-dependent target from fixture/Gold records. `ActionTargetSelector` supports `query_spec_ref`, `expansion_policy=none|each_result|each_distinct_owner` and `deferred_query_result` for this handoff.
- Schema binding consumes only fields/tables/choices already filtered by `workspace membership ∩ employee accessible_tables ∩ caller field visibility`. The Planner Provider may choose only from supplied candidate IDs.
- No raw SQL, database credentials, hidden field values, record contents, Provider keys or unrestricted external tools enter Planner input.
- `risk_analysis` is semantic: `high`, `blocked`, `blocked_reason`, `回滚` or `评审` alone must not create it.
- One user action produces one `ActionSlot`; repeated same-kind actions for distinct targets must remain distinct.
- Conflicting assignments deny only the affected slot. Independent task/reminder slots continue.
- Unknown/ambiguous table, field, target or date produces `clarification_required` or objective-local denial; never guess.
- Objective count ≤ 8, ActionSlot count ≤ 8, planned Provider calls ≤ 4. Exceeding a bound produces a typed budget denial.
- Timezone is explicit. Tests use `Asia/Shanghai` and `2026-07-29T00:00:00+08:00`.
- All behavioral changes follow TDD: observe the intended RED before minimal implementation.
- Do not make intermediate commits. The active handoff requires one final commit only after the broader approved delivery package.

---

## File responsibility map

| File | Responsibility |
| --- | --- |
| `backend/app/schemas/agent_task_spec_v2.py` | Strict runtime-neutral contracts and semantic invariants |
| `backend/app/services/agent_query_lexical.py` | Unicode/date/identifier/action/safety lexical extraction with source spans |
| `backend/app/services/agent_schema_binding.py` | Authorized schema snapshot construction and exact/alias/enum binding |
| `backend/app/services/agent_task_planner_v2.py` | Clause candidates, optional constrained ambiguity resolution, normalization, validation, cost and artifact hash |
| `backend/app/services/agent_task_planner_shadow.py` | V1/V2 comparison and sanitized shadow observation; never dispatches V2 |
| `backend/app/core/config.py` | Default-off shadow flag and workspace allowlist validation |
| `backend/app/api/routes/agent_runs.py` | After existing authorization, invoke shadow observer while retaining V1 dispatch plan |
| `backend/tests/unit/test_agent_task_spec_v2.py` | Contract and invariant tests |
| `backend/tests/unit/test_agent_query_lexical.py` | Canonicalization, spans, clauses and date tests |
| `backend/tests/unit/test_agent_schema_binding.py` | Scope, visibility, alias, enum and ambiguity tests |
| `backend/tests/unit/test_agent_task_planner_v2.py` | Objective/ActionSlot/conflict/provider/cost regressions |
| `backend/tests/unit/test_agent_task_planner_shadow.py` | Default-off, allowlist, sanitization and V1 authority preservation |

### Task 1: Freeze TaskSpec V2, schema snapshot and artifact contracts

**Files:**

- Create: `backend/app/schemas/agent_task_spec_v2.py`
- Create: `backend/tests/unit/test_agent_task_spec_v2.py`

**Interfaces:**

- Produces `AuthorizedFieldSpec`, `AuthorizedTableSpec`, `AuthorizedEntitySpec`, `AuthorizedSchemaSnapshot`, `SourceSpan`, `BoundPredicate`, `QueryIntentSpec`, `TaskObjectiveV2`, `DependencyEdgeV2`, `ActionTargetSelector`, `ActionSlotV1`, `ConflictAssignment`, `ConflictGroupV1`, `TaskOutputSpec`, `PlannerRequestV2`, `TaskSpecV2`, `PlannerCostEstimate`, `TaskSpecArtifact`.
- Produces canonical literals `ObjectiveKindV2`, `ActionKindV1`, `PlanningOutcome`, `FieldTypeV2`, `PredicateOperatorV2`.
- Produces `canonical_task_spec_payload(spec: TaskSpecV2) -> bytes` and `task_spec_sha256(spec: TaskSpecV2) -> str`.
- `ActionTargetSelector` carries static codes or a `query_spec_ref`; `expansion_policy != none` requires that reference and never authorizes a scan.

- [x] **Step 1: Write strict contract tests**

  Use literal constructors independent of planner helpers. Cover extra-field rejection, frozen models, strict scalar types, duplicate table/field/entity IDs, schema hash mismatch, invalid objective/edge/slot references, duplicate IDs, cycles, invalid operator/field-type pairs, unresolved assignments, conflicting duplicate assignments, missing confirmation policy, count bounds, timezone-aware boundaries, static/deferred target invariants and canonical hash stability.

  ```python
  def test_task_spec_rejects_edge_cycles_and_unknown_slot_objective() -> None:
      with pytest.raises(ValidationError):
          TaskSpecV2.model_validate(invalid_payload)

  def test_high_text_value_does_not_define_a_risk_objective_contract() -> None:
      objective = TaskObjectiveV2(
          objective_id="obj-01",
          kind="fact_query",
          required=True,
          entity_codes=(),
          query_spec_ref="query-intent:query-01",
          output_contract="structured_facts",
          planning_outcome="planned",
          denial_reason=None,
      )
      assert objective.kind == "fact_query"
  ```

- [x] **Step 2: Run contract tests and observe RED**

  Run: `python -m pytest tests/unit/test_agent_task_spec_v2.py -q`

  Expected: collection fails because `app.schemas.agent_task_spec_v2` does not exist.

- [x] **Step 3: Implement the minimal strict contracts**

  Every model uses:

  ```python
  model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
  ```

  Stable literals:

  ```python
  ObjectiveKindV2 = Literal[
      "fact_query", "risk_analysis", "daily_summary", "record_change",
      "task_creation", "reminder_request", "restricted_request",
      "conflict_resolution",
  ]
  ActionKindV1 = Literal[
      "record.create", "record.update", "task.create", "reminder.request"
  ]
  PlanningOutcome = Literal["planned", "denied", "clarification_required"]
  ```

  `TaskSpecV2` must carry `schema_version="task-spec.v2"`, `authorized_schema_hash`, `objectives`, `dependency_edges`, `query_intents`, `action_slots`, `conflict_groups`, `output`, `cost` and `provider_call_count`. It must validate a DAG and enforce 8/8/4 limits.

- [x] **Step 4: Run tests and refactor GREEN**

  Run the Task 1 test file twice. The canonical serialized bytes and SHA-256 must be identical on both calls.

### Task 2: Implement source-preserving Chinese lexical extraction and deterministic dates

**Files:**

- Create: `backend/app/services/agent_query_lexical.py`
- Create: `backend/tests/unit/test_agent_query_lexical.py`

**Interfaces:**

- Consumes: raw `query: str`, `clock: datetime`, `timezone_name: str`.
- Produces `LexicalToken`, `LexicalClause`, `LexicalQuery` strict dataclasses/Pydantic models local to the service.
- Produces `canonicalize_query(query: str) -> CanonicalQuery` and `extract_lexical_query(query: str, *, clock: datetime, timezone_name: str) -> LexicalQuery`.

- [x] **Step 1: Write lexical RED tests**

  Cover NFKC, full-width punctuation, whitespace, stable original offsets, case-insensitive but source-preserving `PRJ-*`/`MT-*`/`RISK-*`, Arabic/Chinese Top-N numbers, `并且/同时/然后/但/若/只/不要` boundaries, action verbs, negation, confirmation constraints, and dates `今天/明天/明天之前/本周`.

  ```python
  def test_tomorrow_before_uses_closed_open_utc_boundary() -> None:
      result = extract_lexical_query(
          "创建明天之前的评审任务",
          clock=datetime.fromisoformat("2026-07-29T00:00:00+08:00"),
          timezone_name="Asia/Shanghai",
      )
      assert result.date_ranges[0].end_utc.isoformat() == "2026-07-29T16:00:00+00:00"
  ```

  Add regressions proving `回滚方案`, `blocked_reason`, `high 优先级` and `评审任务` are lexical values/names, not risk semantics.

- [x] **Step 2: Run lexical tests and observe RED**

  Run: `python -m pytest tests/unit/test_agent_query_lexical.py -q`

- [x] **Step 3: Implement bounded lexical extraction**

  Use `unicodedata.normalize("NFKC", query)`, compiled regexes and `zoneinfo.ZoneInfo`; do not call a Provider. Reject empty/trimmed-invalid/NUL input, unsupported timezone, impossible date and >600-character input with stable codes.

- [x] **Step 4: Run lexical tests GREEN**

  Confirm every extracted token has a valid half-open source span and reconstructs its source substring.

### Task 3: Build an authorized schema snapshot and deterministic binder

**Files:**

- Create: `backend/app/services/agent_schema_binding.py`
- Create: `backend/tests/unit/test_agent_schema_binding.py`

**Interfaces:**

- Consumes existing `Stage06PlatformUnitOfWork`, authorized `Actor`, `workspace_id`, `employee_id`; never raw database access.
- Produces `build_authorized_schema_snapshot(uow, *, workspace_id: UUID, employee_id: UUID, actor: Actor) -> AuthorizedSchemaSnapshot`.
- Produces `bind_lexical_query(lexical: LexicalQuery, snapshot: AuthorizedSchemaSnapshot, *, authorized_entities: tuple[AuthorizedEntitySpec, ...] = ()) -> SchemaBindingResult`.
- Binding result separates `bound_tables`, `bound_fields`, `bound_entities`, `bound_enum_values`, `ambiguous_candidates`, `unresolved_mentions`.

- [x] **Step 1: Write scope and binding RED tests**

  Materialize two workspaces and an employee restricted to one table. Assert the snapshot includes only `employee.accessible_tables`, only active fields returned by `get_table_schema(..., actor=actor)`, no hidden field, no record values, and a hash that changes on authorized schema version changes.

  Cover exact key, exact display name, explicit alias, enum option, exact record code supplied as an authorized entity candidate, duplicate display-name ambiguity and unknown field. Exact code must outrank alias; no semantic guess is allowed.

- [x] **Step 2: Run binder tests and observe RED**

  Run: `python -m pytest tests/unit/test_agent_schema_binding.py -q`

- [x] **Step 3: Implement snapshot and binder using public service boundaries**

  Use employee `accessible_tables`, base/workspace equality checks and `get_table_schema`. Aliases come only from explicit field/table option metadata or a versioned built-in Chinese alias map. Entity candidates are supplied separately through the `authorized_entities` argument; an identifier without such a candidate remains `unresolved_authorized_lookup_required` for Stage12-C and is never treated as authorized merely because its syntax looks valid. The binder must not scan records in Stage12-B.

  ```python
  if str(table.id) not in set(employee.accessible_tables):
      continue
  safe_schema = get_table_schema(uow, table.id, actor=actor)
  ```

- [x] **Step 4: Run binder tests GREEN and permission mutation checks**

  Hide a previously visible field and remove a table from `accessible_tables`; both must disappear and never remain as ambiguous candidates.

### Task 4: Construct, normalize and validate multiple objectives and ActionSlots

**Files:**

- Create: `backend/app/services/agent_task_planner_v2.py`
- Create: `backend/tests/unit/test_agent_task_planner_v2.py`

**Interfaces:**

- Consumes `PlannerRequestV2(query, authorized_schema, authorized_entities, clock, timezone_name, allowed_action_kinds)`.
- Optional `ambiguity_resolver: PlannerAmbiguityResolver | None`; resolver receives only enumerated candidate IDs and returns selected IDs.
- Produces `plan_task_v2(request, *, ambiguity_resolver=None) -> TaskSpecArtifact`.
- Produces internal pure functions `construct_candidates`, `normalize_task_spec`, `validate_task_spec_semantics`, `estimate_planner_cost` for focused tests.

- [x] **Step 1: Write planner RED regressions from Stage12 Gold**

  Required literal cases:

  ```text
  high 优先级未完成事项 -> fact_query only
  显示 blocked_reason -> fact_query only
  创建回滚方案评审任务 -> fact_query + one task_creation slot, no risk_analysis
  评审任务 -> one task_creation slot
  比较 Atlas/Beacon 风险 -> fact_query -> risk_analysis
  为 Atlas 和 Beacon 分别创建任务 -> two task.create slots
  MT-017 同时改 done 和 blocked，并创建明天前评审任务
      -> conflicted update denied + independent task planned
  合法部分继续，读取密钥 -> visible fact planned + restricted objective denied
  ```

  Reuse the checked-in Stage12-A truth only as expected scorer input; production planner code must not import `backend/scripts` or test fixtures.

- [x] **Step 2: Run planner tests and observe RED**

  Run: `python -m pytest tests/unit/test_agent_task_planner_v2.py -q`

- [x] **Step 3: Implement clause candidates and semantic risk rules**

  Risk signals require an explicit risk intent verb/noun relationship such as `风险`, `比较风险`, `风险解释`, `风险评估`; values alone do not qualify. Each action clause creates an ActionSlot before normalization. Target expansion for `分别` uses only explicitly bound authorized entities.

- [x] **Step 4: Implement local conflict/denial and dependency normalization**

  Merge only identical `(kind, entity_codes, output_contract)` objectives. Generate deterministic IDs after sorting by source span. Attach conflict groups to `(target, field)` assignments; do not deny unrelated slots. Action objectives depend on the fact objective for their own target, and risk comparison depends on its fact input.

- [x] **Step 5: Implement semantic validation, cost and artifact hash**

  Validate field/operator type, target table, assignment fields, allowed action kinds, required fields and date ranges. Cost fields are integer estimates only: lexical token count, bound field count, objective count, action count, ambiguity count, planned provider calls. No query scan/edge/result estimate is invented before Stage12-C.

- [x] **Step 6: Run planner tests GREEN and score the public 48-case subset**

  Use Evaluation V2 `score_planner` against a conversion adapter. Record Objective/Predicate/ActionSlot results, but do not run a Provider or claim final product quality.

### Task 5: Add a constrained ambiguity resolver boundary

**Files:**

- Modify: `backend/app/services/agent_task_planner_v2.py`
- Modify: `backend/tests/unit/test_agent_task_planner_v2.py`

**Interfaces:**

- Produces `PlannerAmbiguityRequest`, `PlannerAmbiguityDecision` and `PlannerAmbiguityResolver` protocol.
- Resolver input contains `mention_id`, `candidate_ids`, `candidate_labels`, `allowed_selection_count`; it contains no hidden schema, raw record body, credentials or action permission expansion.

- [x] **Step 1: Write resolver boundary RED tests**

  Assert clear exact bindings make zero resolver calls; multiple same-name authorized candidates make exactly one call; a decision outside candidate IDs fails; an unavailable resolver returns `clarification_required`; more than four calls returns typed budget denial.

- [x] **Step 2: Run focused test and observe RED**

  Run the resolver-specific node with `-q`.

- [x] **Step 3: Implement the protocol and output validator**

  Do not implement an OpenRouter adapter in B. The protocol is the only seam; real Provider/model selection belongs to Stage12-E.

- [x] **Step 4: Run planner suite GREEN**

### Task 6: Implement default-off, allowlisted, sanitized V1/V2 shadow comparison

**Files:**

- Create: `backend/app/services/agent_task_planner_shadow.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/routes/agent_runs.py`
- Create: `backend/tests/unit/test_agent_task_planner_shadow.py`
- Modify: `backend/tests/unit/test_stage05_config.py`
- Modify only if route behavior needs coverage: existing `backend/tests/api/test_agent_runs.py`

**Interfaces:**

- Adds settings `agent_task_planner_v2_mode: str = "disabled"` and `agent_task_planner_v2_shadow_workspace_ids: tuple[str, ...] = ()`; allowed mode is `disabled|shadow`.
- Produces `PlannerShadowObservation` containing only V1/V2 hashes, objective/action counts, normalized kind deltas, denial codes, schema hash and `v1_dispatch_unchanged=True`.
- Produces `run_task_planner_shadow(v1_plan, request, snapshot, *, observer) -> PlannerShadowObservation`.

- [x] **Step 1: Write config and shadow RED tests**

  Assert default disabled; invalid mode rejected; production-like shadow requires a non-empty UUID allowlist; non-allowlisted workspaces never build a snapshot; raw query, field labels, entity values and assignments are absent from observation serialization.

- [x] **Step 2: Write route authority-preservation RED test**

  Enable shadow for one in-memory workspace and capture dispatched capability nodes. Assert nodes equal the legacy `build_task_plan` result even when V2 differs. Force V2 planning failure and assert V1 behavior continues while the sanitized observer records `shadow_failed`.

- [x] **Step 3: Implement settings and pure shadow comparison**

  Keep the V1 `task_plan` local variable as the sole source of `read_nodes`. V2 must not mutate the request, V1 plan, employee scope, allowed capabilities or dispatch list.

- [x] **Step 4: Wire shadow after existing authorization only**

  Build the snapshot only after `authorize_workspace_action(..., "digital_employee.invoke")`/current employee scope succeeds. The route records `stage12.planner_shadow_observed` through existing `record_audit_event(platform_uow, ...)`, using a SHA-256 trace suffix and only `PlannerShadowObservation.model_dump(mode="json")` as `after_state`; it must not add a migration, response field or SSE event.

- [x] **Step 5: Run shadow/config/API tests GREEN**

  Also rerun `test_agent_task_gateway.py` to prove Stage11 output compatibility.

### Task 7: Stage12-B evaluation, regression, acceptance and handoff

**Files:**

- Create: `project-docs/08-implementation/STAGE_12_B_TASKSPEC_PLANNER_ACCEPTANCE.md`
- Create: `project-docs/08-implementation/evidence/stage12-b-planner-v2-2026-07-29.json`
- Create: `project-docs/08-implementation/evidence/stage12-b-planner-v2-2026-07-29.md`
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`
- Modify: `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/README.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/README.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/03_PLANNER_AND_QUERY_ENGINE.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md`

**Interfaces:**

- Evidence records code/test identity, schema hash, 48-case Planner-only metrics, known regressions, resolver call counts, shadow deltas, safety/authority deltas and unavailable/deferred items.

- [x] **Step 1: Run Stage12-B focused tests**

  Run all five new unit files plus `test_agent_task_gateway.py`, Stage12-A scorer tests and relevant route/config tests. Record exact pass count and duration.

- [x] **Step 2: Run full backend regression under the Stage12-A documented database boundary**

  Run the same non-PostgreSQL command recorded in Stage12-A. Separately attempt PostgreSQL only if an authorized role with pgvector extension support is available; otherwise preserve the existing BLOCKED status.

- [x] **Step 3: Run static and repository checks**

  Run `python -m compileall -q app scripts`, `alembic heads`, `git diff --check`, a secret/path scan and `ruff` only if installed.

- [x] **Step 4: Audit architecture requirements**

  Explicitly verify: no value-marker risk objective; multi-slot actions; objective-local denial; conflict-local denial; authorized snapshot only; resolver candidate confinement; record-scan-free deferred ActionSlot templates; 8/8/4 budgets; deterministic dates; stable artifact hash; V1-only dispatch; no migration/API/SSE/permission expansion; no external sends.

- [x] **Step 5: Document metrics without overstating product quality**

  Planner-only score is not an Answer/Retrieval/Action product score. B uses only planning-time-applicable Objective/Predicate/Action template fields in its denominator; data-dependent concrete targets are explicitly deferred to C/F and still remain in the final Stage12 gate. PostgreSQL, Provider and multi-round real-LLM tests remain separate gates.

- [x] **Step 6: Update current truth and handoff**

  Mark Stage12-B accepted only if every Stage12-B row has direct evidence. Then identify Stage12-C Authorized Query Engine as next; do not start C inside the B acceptance diff.

- [x] **Step 7: Final scope review; no intermediate commit**

  Confirm only B files plus required docs changed. Preserve all Stage12-A artifacts and unrelated user work. The root handoff's one-final-commit rule remains in force.

## Self-review record

- Spec coverage: covers two-stage parser seam, canonicalization, schema binding, clause segmentation, multiple actions, semantic risk, local conflict/permission outcomes, strict validation, bounded cost, artifact hashing and V1/V2 shadow.
- Explicitly deferred: QueryPlan execution, record scanning, Join/Aggregate, real Planner Provider, new persistence schema, API/SSE extension, deployment and large real-LLM evaluation.
- Placeholder scan: no `TBD`, `TODO`, generic “handle errors” or undefined later-stage execution operator remains.
- Type consistency: `TaskSpecV2`/`ActionSlotV1`/`AuthorizedSchemaSnapshot` are defined in Task 1 and consumed by Tasks 2–7; shadow never becomes dispatch input.
