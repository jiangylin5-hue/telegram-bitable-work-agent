# Stage12-C Authorized Query Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, permission-preserving Query Engine that compiles Stage12-B `QueryIntentSpec` into a bounded `AuthorizedQueryPlanV1` and returns hash-stable `StructuredQueryResultV1` facts, joins, groups, aggregates, versions and provenance without Provider calculation or action execution.

**Architecture:** Stage12-C adds three explicit layers: an authorized relation catalog built from the already permission-filtered schema scope, a pure compiler/validator that emits a restricted AST, and an executor that can access records only through an authorization-preserving record source. Single-table operators, relation traversal and aggregation stay in focused modules; the executor coordinates them and emits a typed artifact. Stage11 V1 remains the only dispatch path, Stage12-B remains record-scan-free, and any C runtime observation is default-off and allowlisted.

**Tech Stack:** Python 3.12+, Pydantic v2 strict models, FastAPI project service conventions, SQLAlchemy 2.x UOW, PostgreSQL JSONB/record-links through existing repositories, pytest.

## Current Execution Status

- Task 1: implemented by RED/GREEN on 2026-07-29; focused contract compatibility evidence is `29 passed`.
- Task 2: implemented by RED/GREEN on 2026-07-29. Direct Task 2 evidence is `106 passed`; the Stage12-A/B/C compatibility set is `215 passed`.
- Task 3: implemented by RED/GREEN on 2026-07-29. Direct Task 3 evidence is `29 passed`; the Task 1–3 joint suite is `135 passed`.
- Task 4: implemented by RED/GREEN on 2026-07-29. Direct relation/record evidence is `20 passed`; the Task 1–4 joint suite is `146 passed`.
- Task 5: implemented by RED/GREEN on 2026-07-29. Direct aggregate evidence is `18 passed`; the Task 1–5 joint suite is `164 passed`.
- Task 6: implemented by RED/GREEN on 2026-07-29 after explicit approval of the internal `JoinedFactRowV1` amendment. The executor now returns hash-stable typed artifacts and supports joined rows without persistence or public exposure.
- Task 7: implemented on 2026-07-29. Query shadow remains default-off, workspace allowlisted, sanitized and unable to alter V1 dispatch or HTTP/SSE bytes.
- Task 8: accepted locally on 2026-07-29. Final evidence is `46/46` applicable Query exact, `11/11` aggregate exact, `2/2` sort exact, `48/48` safety, focused `288 passed`, real PostgreSQL `1 passed`, and full backend `1928 passed, 133 skipped` under the documented four-file historical boundary.
- Confirmation gate: the user explicitly confirmed the complete additive `QueryExecutionIntentV1` contract after reviewing the 48 Case evidence. The earlier projection-only shape is superseded and must not be implemented.

### Confirmed QueryExecutionIntentV1 contract

The additive `QueryIntentSpec.execution_spec` proposal is:

```text
QueryExecutionIntentV1
├─ projection_field_ids[]
├─ predicate_expression
│  ├─ leaf(BoundPredicate)
│  └─ group(and|or, children[])
├─ aggregations[]
│  ├─ aggregate_id / output_key
│  ├─ function / table_id / field_id|null
│  ├─ filter_expression
│  ├─ group_by_field_ids[]
│  └─ having(operator, value)|null
├─ sorts[]
│  ├─ field_id xor aggregate_id
│  ├─ mode(natural|field_order)
│  ├─ direction(asc|desc)
│  └─ nulls(first|last)
└─ limit
```

Case evidence that blocks the smaller shape:

- `daily_01` requires three aggregate-local filters for completed, in-progress and blocked metrics.
- `risk_04` requires post-aggregate `count >= 2` HAVING semantics.
- `join_08` requires stable aggregate `output_key` identity separate from function/value.
- `daily_04` requires enum field-order sorting, while aggregate ranking requires an aggregate target rather than a field target.

Compatibility rule: `QueryIntentSpec.execution_spec` is additive. Existing summary fields remain readable and must equal the summary derived from `execution_spec`; C refuses a legacy aggregate/sort intent without complete execution detail instead of guessing or reparsing raw text. A legacy simple predicate-only intent may still compile as an implicit `and` expression for backward compatibility.

## Global Constraints

- Stage12-C only: do not implement Embedding/Chunk V2, Specialist V2, answer Provider changes, durable Action expansion, Mini App changes, public API/SSE changes, migration, deployment, Telegram send or business writes.
- Planner remains record-scan-free. C consumes `TaskSpecV2`, `AuthorizedSchemaSnapshot`, an authorized relation catalog and an execution context; it never imports Evaluation Gold or test fixtures.
- No raw SQL, arbitrary function, dynamic Python expression, Provider-defined operator or unrestricted `uow.list_records` call may be exposed as a QueryPlan input.
- Every table, view, field, relation endpoint and record must remain inside `employee_scope -> caller_actor_scope -> telegram_chat/view_scope`.
- Hidden fields and hidden relation targets must not appear in plan errors, result values, group keys, hashes or provenance.
- Default maximums are exactly 5,000 authorized scanned records, 1,000 traversed edges, traversal depth 2 and 8 objectives. Budget refusal is explicit; truncation cannot be presented as a complete aggregate.
- Predicate AST maximums are depth 4 and 64 total nodes; each group remains limited to 16 children.
- Count semantics remain distinct: `count`, `count_non_null`, and `count_distinct` are separate functions.
- Results use stable UUID/string ordering before hashing. Dates are canonical ISO values; Planner-provided UTC boundaries are not reparsed from natural language.
- No C shadow execution is enabled by default. `off` remains the repository default and no allowlist is configured implicitly.
- The repository's one-final-commit handoff rule overrides the generic per-task commit examples in the skill; do not create intermediate commits unless the user changes that rule.

---

## File Map

| File | Responsibility |
| --- | --- |
| `backend/app/schemas/authorized_query_plan.py` | Strict QueryPlan, relation catalog, result/provenance and artifact contracts |
| `backend/app/services/authorized_query_validation.py` | Operator/type/scope/reference/budget semantic validation and hash helpers |
| `backend/app/services/authorized_query_compiler.py` | Compile one `QueryIntentSpec` plus authorized relation graph into a validated plan |
| `backend/app/services/authorized_query_records.py` | Build an authorized record set from employee/caller/chat-view intersection; safe projection and version reads |
| `backend/app/services/authorized_query_relations.py` | Forward/reverse link traversal, cycle protection, edge budget and relation proofs |
| `backend/app/services/authorized_query_aggregates.py` | Deterministic group, aggregate, sort and limit semantics |
| `backend/app/services/authorized_table_query.py` | Coordinate validated execution and emit `StructuredQueryResultV1` artifact |
| `backend/app/services/authorized_query_shadow.py` | Default-off/allowlisted sanitized C observation; never dispatch or answer |
| `backend/app/schemas/agent_task_spec_v2.py` | Add the backward-compatible typed `QueryExecutionIntentV1` contract |
| `backend/app/services/agent_task_planner_v2.py` | Populate typed projection, predicate, aggregate and sort intent without record access |
| `backend/app/core/config.py` | Add C off/shadow mode and UUID allowlist settings |
| `backend/app/api/routes/agent_runs.py` | Invoke sanitized C shadow only behind B+C allowlists; do not change response/SSE contract |
| `backend/tests/unit/test_authorized_query_plan.py` | Contract/hash/semantic validator tests |
| `backend/tests/unit/test_authorized_query_compiler.py` | Entity/predicate/projection/path compilation tests |
| `backend/tests/unit/test_authorized_query_records.py` | Table/view/field/record scope and version tests |
| `backend/tests/unit/test_authorized_query_relations.py` | Forward/reverse/cycle/hidden-target/budget traversal tests |
| `backend/tests/unit/test_authorized_query_aggregates.py` | Group/count/distinct/null/sort/limit tests |
| `backend/tests/unit/test_authorized_table_query.py` | End-to-end in-memory deterministic result tests |
| `backend/tests/unit/test_authorized_query_shadow.py` | Default-off, allowlist, sanitization and V1-authority tests |
| `backend/tests/integration/test_stage12_authorized_query_postgres.py` | Real PostgreSQL JSONB/link/view/permission exactness and replay tests |
| `backend/scripts/stage12_query_engine_evaluation.py` | Deterministic Stage12-C diagnostic using materialized fixture data, never Gold as runtime input |
| `backend/tests/unit/test_stage12_query_engine_evaluation.py` | Gold-leak guard and diagnostic contract tests |
| `project-docs/08-implementation/STAGE_12_C_AUTHORIZED_QUERY_ENGINE_ACCEPTANCE.md` | C gate-by-gate acceptance record |
| `project-docs/08-implementation/evidence/stage12-c-authorized-query-engine-2026-07-29.{md,json}` | Human/machine-readable evidence |

### Task 1: Freeze the QueryPlan and StructuredQueryResult contracts

**Files:**
- Create: `backend/app/schemas/authorized_query_plan.py`
- Create: `backend/app/services/authorized_query_validation.py`
- Create: `backend/tests/unit/test_authorized_query_plan.py`

**Interfaces:**
- Consumes: `AuthorizedSchemaSnapshot`, field UUIDs, table UUIDs, view UUIDs and `scope_hash`.
- Produces: `AuthorizedRelationSpec`, `QueryPredicateLeaf`, `QueryPredicateGroup`, `QueryTraversalSpec`, `QueryAggregateSpec`, `AuthorizedQueryPlanV1`, `StructuredQueryResultV1`, `StructuredQueryArtifactV1`, `validate_authorized_query_plan(plan, snapshot, catalog, allowed_view_ids)` and deterministic SHA-256 helpers.

- [x] **Step 1: Write failing strict-contract tests**

  Add tests that construct one valid single-table plan and reject: an unknown table/field/view, a field/table mismatch, an invalid operator for field type, `raw_sql`, depth 3, edge budget above 1,000, scan budget above 5,000, an unauthorized or type-incompatible aggregate input, duplicate operator IDs, and a result hash that does not match canonical content. View validation uses the caller-supplied `allowed_view_ids`; it must not infer View authority from a schema snapshot that contains no View data.

  ```python
  def test_text_field_rejects_numeric_operator() -> None:
      plan = _plan_with_leaf(field_id=TITLE_ID, operator="gt", value=3)
      with pytest.raises(ValueError, match="authorized_query_operator_type_invalid"):
          validate_authorized_query_plan(
              plan,
              snapshot=_snapshot(),
              catalog=_catalog(),
              allowed_view_ids=(),
          )


  def test_plan_rejects_raw_sql_payload() -> None:
      with pytest.raises(ValidationError):
          AuthorizedQueryPlanV1.model_validate({**_valid_payload(), "raw_sql": "select 1"})
  ```

- [x] **Step 2: Run the contract tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_authorized_query_plan.py`

  Expected: FAIL because `app.schemas.authorized_query_plan` does not exist.

- [x] **Step 3: Implement strict discriminated contracts**

  Use frozen, strict Pydantic models. The predicate tree is limited to `and`/`or`; leaves contain only registered field/operator/value data.

  ```python
  class QueryPredicateLeaf(_StrictFrozenModel):
      kind: Literal["leaf"] = "leaf"
      predicate_id: NonEmptyStr
      table_id: UUID
      field_id: UUID
      operator: PredicateOperatorV2
      value: JsonValue


  class QueryPredicateGroup(_StrictFrozenModel):
      kind: Literal["group"] = "group"
      predicate_id: NonEmptyStr
      operator: Literal["and", "or"]
      children: tuple["QueryPredicateNode", ...] = Field(min_length=1, max_length=16)


  class AuthorizedQueryPlanV1(_StrictFrozenModel):
      version: Literal["authorized-query-plan.v1"]
      query_intent_id: NonEmptyStr
      root_table_id: UUID
      authorized_view_ids: tuple[UUID, ...]
      entity_codes: tuple[NonEmptyStr, ...]
      predicate: QueryPredicateNode | None
      traversals: tuple[QueryTraversalSpec, ...]
      projection_field_ids: tuple[UUID, ...]
      group_by_field_ids: tuple[UUID, ...]
      aggregates: tuple[QueryAggregateSpec, ...]
      sort_rules: tuple[QuerySortSpec, ...]
      limit: StrictInt | None
      max_scan_rows: StrictInt = 5000
      max_relation_expansions: StrictInt = 1000
      scope_hash: Sha256Hex
      schema_hash: Sha256Hex
  ```

  `StructuredQueryResultV1` must contain `records`, `groups`, `aggregates`, `relation_paths`, `source_versions`, `scope_hash`, `schema_hash`, `result_hash`, `scanned_record_count`, `traversed_edge_count`, and `truncated`. Each record stores an ordered immutable tuple of `StructuredFieldValue(field_id, value)` entries, never a mutable dictionary or hidden field name; duplicate field IDs are rejected.

- [x] **Step 4: Implement semantic validation and canonical hashing**

  Validate every table/field reference against the supplied snapshot, every relation against the catalog, and every requested View against the explicit `allowed_view_ids`. Recursively reject Predicate trees deeper than 4 or larger than 64 nodes, validate aggregate/type compatibility, and reject hidden/unregistered paths without naming hidden objects in the error detail. Hash `model_dump(mode="json", exclude={"plan_hash"})` using sorted-key compact JSON. Aggregate input fields join the internal read set but do not have to appear in presentation projection.

- [x] **Step 5: Run contract tests GREEN and compatibility tests**

  Run: `python -m pytest -q tests/unit/test_authorized_query_plan.py tests/unit/test_agent_task_spec_v2.py`

  Expected: PASS.

### Task 2: Add QueryExecutionIntentV1 and compile TaskSpec into a bounded QueryPlan

**Files:**
- Modify: `backend/app/schemas/agent_task_spec_v2.py`
- Modify: `backend/app/services/agent_task_planner_v2.py`
- Create: `backend/app/services/authorized_query_compiler.py`
- Create: `backend/tests/unit/test_authorized_query_compiler.py`
- Modify: `backend/tests/unit/test_agent_task_spec_v2.py`
- Modify: `backend/tests/unit/test_agent_task_planner_v2.py`

**Interfaces:**
- Consumes: `TaskSpecV2`, one `query_intent_id`, `AuthorizedSchemaSnapshot`, `tuple[AuthorizedRelationSpec, ...]`, and authorized view IDs.
- Produces: additive `QueryIntentSpec.execution_spec: QueryExecutionIntentV1 | None`, `compile_authorized_query_plan(...) -> AuthorizedQueryPlanV1`, or a stable `AuthorizedQueryCompileError(code)`.
- Contract: `QueryExecutionIntentV1` owns presentation projections, recursive global predicates, aggregate-local predicates, aggregate identity/output keys, group fields, HAVING, typed field-or-aggregate sorts and semantic limit. Existing `QueryIntentSpec` summary fields remain compatibility summaries and must equal values derived from `execution_spec` whenever it is present.

- [x] **Step 1: Write RED contract, Planner-semantic and path-compilation tests**

  Cover the complete confirmed contract:

  - explicit requested fields become projection IDs;
  - recursive `and`/`or` predicate expressions remain typed and bounded;
  - `daily_01` can express three independently filtered metrics;
  - `risk_04` can express grouped `count` with `having >= 2`;
  - `join_08` has stable `aggregate_id` and `output_key`;
  - `daily_04` can sort an enum using authorized schema field order;
  - field and aggregate sort targets are mutually exclusive;
  - summary fields must match the execution contract;
  - a legacy aggregate/sort summary without execution detail is refused by the compiler;
  - predicate, aggregate, group and sort fields join the internal read set without leaking into presentation projection;
  - root-table-only queries have no traversal;
  - a related referenced table yields the unique shortest authorized path;
  - two equally short paths return `authorized_query_join_path_ambiguous`;
  - a missing path returns `authorized_query_join_path_unavailable`;
  - entity codes remain selectors and are not resolved by scanning during compilation.

  ```python
  def test_compiler_uses_unique_two_table_path() -> None:
      plan = compile_authorized_query_plan(
          task_spec=_task_spec(root=PROJECTS_ID, predicate_table=WORK_ITEMS_ID),
          query_intent_id="query-01",
          snapshot=_snapshot(),
          relations=(_project_work_items_reverse_relation(),),
          authorized_view_ids=(),
      )
      assert [(item.source_table_id, item.target_table_id, item.direction) for item in plan.traversals] == [
          (PROJECTS_ID, WORK_ITEMS_ID, "reverse")
      ]
  ```

- [x] **Step 2: Run TaskSpec, Planner and compiler tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_authorized_query_compiler.py tests/unit/test_agent_task_spec_v2.py tests/unit/test_agent_task_planner_v2.py`

  Expected: FAIL because the complete execution intent, extended QueryPlan aggregate/sort contracts and compiler are absent.

- [x] **Step 3: Add the backward-compatible typed execution contract**

  Add strict frozen `QueryPredicateExpressionV1`, `QueryAggregationIntentV1`, `QueryHavingIntentV1`, `QuerySortIntentV1` and `QueryExecutionIntentV1` models, then add `execution_spec: QueryExecutionIntentV1 | None = None` to `QueryIntentSpec`. Keep existing summaries readable, but validate their consistency with the execution contract. Extend `QueryAggregateSpec` for `output_key`, aggregate-local predicate, grouping and HAVING; extend `QuerySortSpec` with a mutually exclusive field/aggregate target and `natural|field_order` mode. In the Planner, populate only from authorized schema binding and deterministic query semantics; do not inspect records, evaluation Gold or fixtures.

- [x] **Step 4: Implement deterministic authorized BFS path selection**

  Build an adjacency list only from `AuthorizedRelationSpec`. Relation ownership is unambiguous: `link_source_table_id` is always the table that owns `link_field_id`, `link_target_table_id` is always the configured target table, and `direction` only controls whether traversal runs source→target or target→source. Search up to depth 2, order neighbors by `(link_source_table_id, link_field_id, direction, link_target_table_id)`, accept exactly one shortest path, and return ambiguity rather than selecting the first of equal paths.

  ```python
  def _unique_shortest_path(
      root_table_id: UUID,
      target_table_id: UUID,
      relations: tuple[AuthorizedRelationSpec, ...],
      *,
      max_depth: int = 2,
  ) -> tuple[QueryTraversalSpec, ...]:
      queue = deque([(root_table_id, ())])
      shortest: list[tuple[QueryTraversalSpec, ...]] = []
      shortest_depth: int | None = None
      while queue:
          table_id, path = queue.popleft()
          if shortest_depth is not None and len(path) >= shortest_depth:
              continue
          for edge in _ordered_edges_from(table_id, relations):
              candidate = (*path, _to_traversal(edge))
              next_table_id = _edge_destination(table_id, edge)
              if next_table_id == target_table_id:
                  shortest_depth = len(candidate)
                  shortest.append(candidate)
              elif len(candidate) < max_depth and next_table_id not in {
                  root_table_id,
                  *(_traversal_origin(item) for item in candidate),
              }:
                  queue.append((next_table_id, candidate))
      unique = tuple(dict.fromkeys(shortest))
      if len(unique) != 1:
          raise AuthorizedQueryCompileError(
              "authorized_query_join_path_unavailable"
              if not unique
              else "authorized_query_join_path_ambiguous"
          )
      return unique[0]
  ```

- [x] **Step 5: Compile the complete execution contract without executing**

  Preserve Planner typed values and UTC ranges. Recursively map the explicit predicate tree, aggregate-local filters, groups, HAVING, stable output keys, field/aggregate sort targets and semantic limit into the restricted QueryPlan AST. A predicate-only legacy intent may map its flat predicates to an `and` root; a legacy aggregate/sort summary without `execution_spec` must return `authorized_query_execution_detail_required`. Never reparse raw query text in the compiler or infer an unregistered function/expression.

- [x] **Step 6: Run compiler and Planner tests GREEN**

  Run: `python -m pytest -q tests/unit/test_authorized_query_compiler.py tests/unit/test_agent_task_spec_v2.py tests/unit/test_agent_task_planner_v2.py`

  Actual: PASS. Direct Task 2 suite: `106 passed in 1.71s`. Stage12-A/B/C compatibility set: `215 passed in 6.58s`. Existing deterministic hash tests derive expected values from actual typed output; no hard-coded Gold or fixture-derived runtime input was added.

### Task 3: Build the authorized record source and single-table operators

**Files:**
- Create: `backend/app/services/authorized_query_records.py`
- Create: `backend/tests/unit/test_authorized_query_records.py`
- Modify: `backend/app/services/agent_schema_binding.py`
- Modify: `backend/tests/unit/test_agent_schema_binding.py`

**Interfaces:**
- Consumes: `Stage06PlatformUnitOfWork`, `Actor`, workspace/base/employee IDs, authorized snapshot, optional chat-authorized view IDs and a validated table/field request.
- Produces: `AuthorizedQueryContext`, `AuthorizedRecord`, `AuthorizedRecordSet`, `build_authorized_relation_catalog(...)`, `scan_authorized_records(...)`, `resolve_authorized_entities(...)`, `filter_records(...)`, and `project_records(...)`.

- [x] **Step 1: Write RED authorization tests**

  Test the exact intersection: an employee-inaccessible table is denied; a caller-hidden field is never projected; a view-scoped record outside the view is absent; a chat scope cannot add an employee-inaccessible view; inactive/soft-deleted records are excluded; duplicate display labels return ambiguous; exact authorized code wins over aliases; each returned record includes its real version.

  ```python
  def test_chat_view_scope_cannot_expand_employee_scope() -> None:
      with pytest.raises(AuthorizedQueryDenied, match="authorized_query_view_scope_denied"):
          scan_authorized_records(
              context=_context(employee_views=(SAFE_VIEW_ID,), chat_views=(OTHER_VIEW_ID,)),
              table_id=WORK_ITEMS_ID,
              required_field_ids=(TITLE_ID,),
          )
  ```

- [x] **Step 2: Run record-source tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_authorized_query_records.py tests/unit/test_agent_schema_binding.py`

  Expected: FAIL because the authorized record source/catalog does not exist.

- [x] **Step 3: Extend the authorized catalog with visible link metadata**

  `build_authorized_relation_catalog` may read `PlatformField.options["target_table_id"]` only after the source link field is visible and both source/target tables are inside the authorized snapshot. It emits IDs and direction metadata, not hidden names. A hidden link field or inaccessible target produces no catalog edge.

- [x] **Step 4: Implement scope intersection before enumeration**

  Resolve workspace/base/employee status and equality first. Validate every requested view against both employee `accessible_views` and chat-authorized views. Use `list_view_records` for view membership and `read_record_for_actor` for safe values/version; for explicitly authorized whole-table scope, enumerate table records only inside this private adapter and immediately pass every record through `read_record_for_actor`. No other C module calls `uow.list_records` directly.

- [x] **Step 5: Implement typed single-table filtering and projection**

  Normalize stored JSONB values through field-type-specific comparators. Implement only the operator matrix already approved in `agent_task_spec_v2.py`. Same-field `in` uses set membership; distinct leaves in the default group use `AND`; `OR` is executed only when present in the typed AST.

- [x] **Step 6: Enforce scan budgets before completeness claims**

  Count authorized candidate records, stop with `authorized_query_scan_budget_exceeded` when above 5,000, and do not return a partial aggregate. A user `Limit` is applied after filters/sort; it does not reduce the input set for aggregates.

- [x] **Step 7: Run record-source tests GREEN**

  Run: `python -m pytest -q tests/unit/test_authorized_query_records.py tests/unit/test_agent_schema_binding.py tests/unit/test_stage06_platform_core.py`

  Actual: PASS. Direct Task 3 suite: `29 passed in 1.85s`. Task 1–3 joint suite: `135 passed in 2.19s`. No record outside the authorized table/view/field intersection is returned, and over-budget scans refuse without a partial result.

### Task 4: Implement permission-preserving forward and reverse traversal

**Files:**
- Create: `backend/app/services/authorized_query_relations.py`
- Create: `backend/tests/unit/test_authorized_query_relations.py`

**Interfaces:**
- Consumes: `AuthorizedQueryContext`, `AuthorizedRecordSet`, validated `QueryTraversalSpec` sequence and `AuthorizedRelationSpec` catalog.
- Produces: traversed `AuthorizedRecordSet`, ordered `RelationPathProof` values, updated edge count, or stable budget/scope/ambiguity errors.

- [x] **Step 1: Write RED traversal tests**

  Cover one-hop forward, one-hop reverse, approved two-hop traversal, depth-3 refusal, repeated edge cycle, duplicate links, an inaccessible target table, hidden target record, hidden link field, target outside allowed view, malformed record-link endpoint and expansion 1,001. Assert hidden target IDs/names are absent from errors and result hashes.

  ```python
  def test_reverse_traversal_filters_hidden_source_records() -> None:
      result = traverse_authorized_links(
          context=_viewer_context(),
          source_records=_authorized_projects(),
          traversals=(_work_items_reverse(),),
          catalog=(_relation(),),
      )
      assert {item.record_id for item in result.records} == {VISIBLE_WORK_ITEM_ID}
      assert HIDDEN_WORK_ITEM_ID.hex not in result.provenance_json
  ```

- [x] **Step 2: Run relation tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_authorized_query_relations.py`

  Expected: FAIL because traversal is absent.

- [x] **Step 3: Implement forward traversal from safe linked values**

  Read only the already-authorized linked field. Canonicalize link IDs, deduplicate them, validate the target table against the relation catalog, and resolve every target through `scan_authorized_records` membership before it can enter the result.

- [x] **Step 4: Implement reverse traversal from registered record links**

  Use `list_record_links_to(target_record_id)`, retain only links whose `source_field_id/source_table_id/target_table_id` exactly match `link_field_id/link_source_table_id/link_target_table_id` in the catalog entry, and authorize the source record through the same record source. Do not trust link rows alone as permission proof.

- [x] **Step 5: Add cycle and expansion protection**

  Maintain visited `(source_table_id, source_record_id, source_field_id, target_record_id, direction)` keys. Count unique accepted edges, reject at 1,001, and record a `RelationPathProof` only after both endpoints pass authorization.

- [x] **Step 6: Run relation tests GREEN**

  Run: `python -m pytest -q tests/unit/test_authorized_query_relations.py tests/unit/test_authorized_query_records.py`

  Actual: PASS. Direct relation/record suite: `20 passed in 2.15s`. Task 1–4 joint suite: `146 passed in 2.76s`. Intermediate records retain version-only provenance so a link target removed by an authorized View cannot leak through result representation.

### Task 5: Implement deterministic grouping, aggregation, sorting and limit

**Files:**
- Create: `backend/app/services/authorized_query_aggregates.py`
- Create: `backend/tests/unit/test_authorized_query_aggregates.py`

**Interfaces:**
- Consumes: fully authorized and filtered `AuthorizedRecordSet`, group field IDs, `QueryAggregateSpec`, sort rules and optional user limit.
- Produces: `tuple[StructuredGroup, ...]`, `tuple[StructuredAggregate, ...]`, sorted record IDs and completeness metadata.

- [x] **Step 1: Write RED exact-semantics tests**

  Test `count` records, `count_non_null`, `count_distinct`, sum/average/min/max on numeric values, null exclusion, empty input, multi-group stable order, duplicate values, Unicode text sort, ascending/descending null placement, Top N after aggregation, and group-key-hidden fail closed.

  ```python
  @pytest.mark.parametrize(
      ("function", "expected"),
      (("count", 4), ("count_non_null", 3), ("count_distinct", 2)),
  )
  def test_count_functions_are_not_conflated(function: str, expected: int) -> None:
      assert aggregate(_records(["a", "a", None, "b"]), _spec(function)).value == expected
  ```

- [x] **Step 2: Run aggregate tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_authorized_query_aggregates.py`

  Expected: FAIL because the aggregate module does not exist.

- [x] **Step 3: Implement typed aggregate functions**

  Reject sum/average on non-number fields during validation. Use `Decimal(str(value))` internally, emit JSON-safe int/float/string according to the result contract, and never ask an LLM to recount or regroup.

- [x] **Step 4: Implement stable group/sort/limit order**

  Canonical order is `(is_null, canonical_value, record_id)` for ascending and the exact inverse value order for descending while retaining record ID as the deterministic tie-breaker. Apply aggregate calculation to the complete filtered set before presentation Limit.

- [x] **Step 5: Run aggregate tests GREEN**

  Run: `python -m pytest -q tests/unit/test_authorized_query_aggregates.py`

  Actual: PASS. Direct aggregate suite: `18 passed`. Task 1–5 joint suite: `164 passed in 2.81s`. Numeric comparison uses `Decimal`, linked-record groups use canonical JSON keys, HAVING removes rejected groups from facts, and aggregate values are computed before presentation Limit.

### Task 6: Coordinate end-to-end execution and hash-stable artifacts

#### Confirmed internal JoinedFactRowV1 amendment

Task 1–5 correctly authorize and compute individual record sets, relations and aggregates, but `AuthorizedTraversalResult.record_set` is intentionally a deduplicated destination union. Consuming only that union in Task 6 would lose which target record belongs to which root record. Two already-confirmed `QueryExecutionIntentV1` capabilities would then be semantically incorrect:

- a cross-table Boolean expression such as `project.phase = delivery or work_item.status = blocked` cannot be evaluated against one joined fact row;
- a projection containing both a root-table field and a target-table field cannot preserve their relationship.

Recommended additive internal contract:

```text
JoinedFactRowV1
+-- root_record_id
+-- records_by_table[]
|   +-- table_id
|   `-- AuthorizedRecord
+-- relation_path_proofs[]
`-- source_versions[]
```

Revised fixed pipeline if approved:

```text
authorize root records
-> push down only predicates whose truth is table-local and logically safe
-> expand each relation into immutable JoinedFactRowV1 rows
-> evaluate the complete typed predicate expression on each joined row
-> emit unique projected records from matched rows
-> aggregate/sort/limit on the explicitly referenced target/group fields
-> collect row-scoped proofs and versions
-> canonical artifact hash
```

This amendment is internal to Stage12-C. It adds no database migration, public API/SSE field, permission expansion, Provider input, action behavior or external write. The user explicitly confirmed it on 2026-07-29; the narrower cross-table-refusal alternative is superseded.

**Files:**
- Create: `backend/app/services/authorized_table_query.py`
- Create: `backend/tests/unit/test_authorized_table_query.py`

**Interfaces:**
- Consumes: `execute_authorized_query(uow, actor, workspace_id, employee_id, chat_view_ids, snapshot, plan, allow_whole_table=False) -> StructuredQueryArtifactV1`.
- Produces: one validated plan artifact plus one hash-stable `StructuredQueryResultV1`; it performs no persistence, Provider call, action proposal or external send.
- `chat_view_ids=None` does not imply whole-table authority. Whole-table enumeration requires the caller to pass `allow_whole_table=True` explicitly; otherwise the coordinator remains view-scoped and fail-closed.

- [x] **Step 1: Write RED end-to-end fixture tests**

  Materialize projects, work items, risks, tasks, owners, daily metrics and interactions through existing Stage06 services. Cover: identifier lookup; compound filters; negative/empty/date predicates; project→work-item reverse join; work-item→risk reverse join; grouped unfinished counts; max-risk selection; stable sort/limit; view restriction; source versions; relation proofs; repeated-run identical hashes.

  The confirmed joined-row semantics must also cover: cross-table `or` truth evaluated per joined row; root-plus-target projection relationship; one-to-many row expansion lineage; duplicate path/record de-duplication without proof loss; row-scoped versions/proofs; and absence of rejected or hidden target identifiers from both the artifact and `result_hash` input.

  ```python
  def test_project_blocked_work_items_and_open_risks_are_exact_and_replayable() -> None:
      first = execute_authorized_query(**_join_request())
      second = execute_authorized_query(**_join_request())
      assert first.result.result_hash == second.result.result_hash
      assert _codes(first.result) == ["MT-001", "RISK-002"]
      assert all(item.record_version >= 1 for item in first.result.source_versions)
  ```

- [x] **Step 2: Run end-to-end tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_authorized_table_query.py`

  Actual: RED as expected. Collection failed with `ModuleNotFoundError: No module named 'app.services.authorized_table_query'`; no coordinator implementation existed when the tests were first executed.

- [x] **Step 3: Implement the fixed execution pipeline**

  Execute exactly: validate plan and current scope → scan/resolve root set → apply only logically safe table-local predicate pushdown → expand each registered relation into immutable `JoinedFactRowV1` rows → evaluate the complete typed predicate expression per joined row → emit unique projected records from matched rows → group/aggregate → sort/limit → collect only row-scoped versions/proofs → canonical hash. Revalidate schema/scope hashes before and after execution; return `authorized_query_scope_drift` or `authorized_query_schema_drift` rather than stale facts.

  `JoinedFactRowV1` remains an internal frozen service contract. It must keep one authorized record per table on the row, the root identity, only the accepted relation proofs that formed that row, and the corresponding source versions. It must not be added to the public API/SSE contract or persisted.

  Actual: implemented as an internal frozen dataclass in `authorized_table_query.py`. Cross-table predicates are evaluated only after immutable row expansion; projection de-duplicates records while relation proofs retain root-to-target lineage. Scope/schema hashes are revalidated both before and after execution.

- [x] **Step 4: Separate safety pagination from semantic Limit**

  Internally page authorized record enumeration until complete or budget refusal. Set `truncated=False` only after every required page/edge is processed. Never return `truncated=True` together with an aggregate presented as complete.

  Actual: root and destination scans share the plan-wide scan budget; traversal hops share the plan-wide edge budget. Budget exhaustion raises a fail-closed refusal and produces no partial artifact. Presentation `Limit` runs only after complete matching and aggregation; `truncated` therefore describes presentation truncation only.

- [x] **Step 5: Run end-to-end and full C unit tests GREEN**

  Run: `python -m pytest -q tests/unit/test_authorized_query_plan.py tests/unit/test_authorized_query_compiler.py tests/unit/test_authorized_query_records.py tests/unit/test_authorized_query_relations.py tests/unit/test_authorized_query_aggregates.py tests/unit/test_authorized_table_query.py`

  Actual: PASS. Direct coordinator suite: `8 passed in 1.65s`. The six-file command above: `80 passed in 3.34s`. Expanded Task 1–6 joint suite including TaskSpec, planner and schema binding: `162 passed in 3.05s`. `compileall` and `git diff --check` passed; Ruff was skipped because the environment does not have the `ruff` module installed.

### Task 7: Add default-off shadow observation without changing dispatch or API contracts

**Files:**
- Create: `backend/app/services/authorized_query_shadow.py`
- Create: `backend/tests/unit/test_authorized_query_shadow.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/routes/agent_runs.py`
- Modify: `backend/tests/unit/test_stage05_config.py`
- Modify: `backend/tests/api/test_agent_run_events_api.py`

**Interfaces:**
- Consumes: B shadow artifact, C compiler/executor dependencies and UUID workspace allowlist.
- Produces: `AuthorizedQueryShadowObservationV1` with plan/result hashes, counts, duration, error code and scope hash only. It is not stored in user-visible answer/SSE fields and cannot become a command.

- [x] **Step 1: Write RED flag/authority/sanitization tests**

  Assert default mode `off`; invalid mode/UUID list fails configuration; non-allowlisted workspaces do not compile or scan; allowlisted shadow records only hashes/counts/error codes; record values, labels, field names and hidden identifiers are absent; Stage11 gateway nodes and HTTP/SSE response bodies are byte-for-byte unchanged.

- [x] **Step 2: Run shadow/config/API tests and verify RED**

  Run: `python -m pytest -q tests/unit/test_authorized_query_shadow.py tests/unit/test_stage05_config.py tests/api/test_agent_run_events_api.py tests/unit/test_agent_task_gateway.py`

  Actual: RED as expected. Collection failed with `ModuleNotFoundError: No module named 'app.services.authorized_query_shadow'`; C shadow settings and adapter were not present when the tests were first executed.

- [x] **Step 3: Implement off/shadow configuration**

  Add `AUTHORIZED_QUERY_ENGINE_V1_MODE: Literal["off", "shadow"] = "off"` and `AUTHORIZED_QUERY_ENGINE_V1_WORKSPACE_ALLOWLIST`. Do not add `active` in Stage12-C; active dispatch belongs to a later connected-stage decision.

  Actual: implemented with repository default `off`, an empty default UUID allowlist and fail-fast validation. `active` is rejected and no workspace is enabled implicitly.

- [x] **Step 4: Implement sanitized observation and route hook**

  Run only after B shadow succeeds and both B/C allowlists contain the workspace. Catch C errors into stable codes. Do not mutate V1 task plan, command, checkpoint, answer, action candidates or public response models.

  Actual: the B shadow now exposes its in-process `TaskSpecArtifact` only through an internal outcome wrapper. C runs only when B status is `observed`, the artifact exists and both independent workspace gates pass. The stored C observation contains only hashes, counts, integer duration, stable error code and scope hash; HTTP/SSE models and V1 nodes remain unchanged.

- [x] **Step 5: Run shadow/config/API compatibility GREEN**

  Run: `python -m pytest -q tests/unit/test_authorized_query_shadow.py tests/unit/test_stage05_config.py tests/api/test_agent_run_events_api.py tests/unit/test_agent_task_gateway.py`

  Actual: PASS. The exact four-file command passed `31 passed in 6.24s`; the expanded shadow compatibility command including B shadow tests passed `36 passed in 4.77s`. API evidence confirms the C plan/result hash sentinels are absent from both HTTP and SSE bytes, while V1 remains the only dispatch authority.

### Task 8: PostgreSQL exactness, Stage12-C diagnostic, acceptance and handoff

**Files:**
- Create: `backend/tests/integration/test_stage12_authorized_query_postgres.py`
- Create: `backend/scripts/stage12_query_engine_evaluation.py`
- Create: `backend/tests/unit/test_stage12_query_engine_evaluation.py`
- Create: `project-docs/08-implementation/STAGE_12_C_AUTHORIZED_QUERY_ENGINE_ACCEPTANCE.md`
- Create: `project-docs/08-implementation/evidence/stage12-c-authorized-query-engine-2026-07-29.json`
- Create: `project-docs/08-implementation/evidence/stage12-c-authorized-query-engine-2026-07-29.md`
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`
- Modify: `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/README.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/README.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/03_PLANNER_AND_QUERY_ENGINE.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md`

**Interfaces:**
- Consumes: Stage12-A materialized fixture, Stage12-B TaskSpec artifacts and the C compile/execute API. Evaluation truth is used only by the scorer after runtime artifacts exist.
- Produces: per-case Query/Join/Aggregate exact metrics, permission/safety gates, PostgreSQL evidence status and the Stage12-C acceptance decision.

#### Task 8 acceptance pause: relation-intent and optional-join gap

The first bounded diagnostic ran on 2026-07-29 and is evidence of a real architecture gap, not an acceptance result. Runtime safety was `48/48`, but only `9/48` complete cases were exact. The Join slice was exact for only `join_02` and `join_06`; `join_01`, `join_03`, `join_04`, `join_05`, `join_07` and `join_08` exposed three connected limitations:

- Planner can bind an entity code to the wrong root table when the query names both the entity and related tables.
- `QueryExecutionIntentV1` has no explicit relation intent, so a table mentioned only as desired related evidence (for example, “关联风险”) disappears unless one of its fields also appears in a predicate, projection or aggregate.
- `AuthorizedQueryPlanV1.traversals` is a single mandatory inner-join chain. It cannot preserve required work-item rows while optionally attaching zero-or-more risk rows, nor can it represent independent relation branches/existence checks without conflating their predicates.

Implementing Case-specific keyword patches would overfit the evaluation fixture and is forbidden. The recommended correction is an additive internal contract, with no public API/SSE, database schema, permission, Provider, action or write expansion:

```text
QueryExecutionIntentV1.join_intents[]
  -> target_table_id
  -> purpose: project | filter | exists | aggregate
  -> requirement: required | optional

AuthorizedQueryPlanV1.traversal_paths[]
  -> path_id
  -> steps[]
  -> join_mode: inner | left | semi
```

Entity-code ownership must be resolved from the authorized schema/entity catalog before final root-table selection. The compiler must still resolve one unique authorized path per intent and refuse ambiguity. Execution remains permission-preserving and bounded, but evaluates each path independently and merges only typed structured facts/provenance.

This changes an already confirmed internal Planner/QueryPlan contract. The user explicitly approved this additive internal amendment on 2026-07-29. Implementation may proceed by RED/GREEN, but Stage12-C must not be marked accepted before the amended contract is implemented and the same bounded diagnostic is rerun.

- [x] **Step 1: Write PostgreSQL RED tests before adapting SQLAlchemy behavior**

  Use a disposable database URL guarded by `STAGE06_LOCAL_DATABASE_URL`. Test JSONB typed filters, forward/reverse `record_links`, saved-view scope, hidden field/record exclusion, cross-workspace refusal, stable replay hashes and source version changes after a committed update. The test must skip with one explicit reason when the authorized PostgreSQL environment is absent; it must not create an extension or migration.

- [x] **Step 2: Run PostgreSQL tests and record the actual environment state**

  Run: `python -m pytest -q tests/integration/test_stage12_authorized_query_postgres.py`

  Expected with a configured authorized database: initial behavioral failures, then PASS after service fixes. Expected without it: explicit SKIP/BLOCKED evidence; never infer PostgreSQL success from in-memory tests.

  Actual: the user explicitly authorized the native local PostgreSQL instance. `pgvector 0.8.3` was installed by the `postgres` administrator, Alembic reached `20260728_0034`, the real Stage08 pgvector suite passed `17 tests`, and the Stage12-C PostgreSQL test passed `1 test` while retaining the migration head and extension version after rollback cleanup.

- [x] **Step 3: Write the diagnostic Gold-leak guard**

  Monkeypatch the scorer fixture loader and prove compile/execute completes before expected results are read. Runtime input may include query, authorized schema/entity catalog and materialized records only; expected record IDs, aggregates and action targets cannot enter compiler/executor arguments.

  Actual: PASS, `2 passed`. The test proves Gold is unavailable until after Planner/compile/execute artifacts exist.

- [x] **Step 4: Run the bounded Stage12-C diagnostic and close the relation-contract gap**

  Score only C-applicable structured facts: entity resolution, predicates, joins, groups, aggregates, relation paths, versions, scope and safety. Report raw and applicable denominators. Do not run the 48-case × 3 real-LLM campaign and do not score final Action expansion.

  First actual run: raw `48`, applicable `48`, executed `26`, refused `22`, preliminary exact `9/48`, safety `48/48`. This was a diagnostic failure and was not promoted. The scorer was corrected to exclude cases with no structured Query truth and to require exact record/evidence boundaries, relation paths, aggregate output keys/values, sort contracts, source versions and safety. After the approved Join amendment, independent paths, optional-path semantics, cross-table grouped aggregation and evidence bounding were implemented. Final result: raw `48`, applicable `46`, exact `46/46`, aggregate `11/11`, sort `2/2`, safety `48/48`, with zero Provider, Action expansion, business write or external send.

- [x] **Step 5: Run focused and full regressions**

  Run all Stage12-A/B/C unit, config, gateway and API compatibility tests. Then run the same full backend command and the same four historical PostgreSQL-only exclusions recorded in Stage12-B. Record exact counts/durations rather than copying prior evidence.

  Actual: focused A/B/C compatibility `288 passed in 12.08s`; Stage12-C local PostgreSQL `1 passed in 3.85s`; full backend `1928 passed, 133 skipped in 142.57s` after explicitly excluding the same four historical PostgreSQL-only files.

- [x] **Step 6: Run static/repository/scope checks**

  Run `python -m compileall -q app scripts`, `python -m alembic heads`, `git diff --check`, and changed-file secret/developer-path scans. Run `python -m ruff --version`; if unavailable, record unavailable rather than claiming lint success. Confirm no migration, public API/SSE, Provider, action, write, send, deployment or Mini App diff.

  Actual: compileall and diff check passed; Alembic has one head `20260728_0034`; added-line/untracked credential and developer-path scans have zero hits. Ruff is not installed, so no lint pass is claimed. Scope audit found no migration, Mini App, Provider, Action persistence, deployment or external-send implementation.

- [x] **Step 7: Write acceptance and update current truth**

  Mark C accepted only when every available deterministic Query/Join/Aggregate/permission row has direct evidence and all unavailable infrastructure rows are explicitly blocked/skipped. Preserve Stage12-B raw `37/48` Objective disclosure and pending human Gold review. Identify Stage12-D as next only after C acceptance.

  Actual: acceptance and machine/human evidence were written. The latest Planner disclosure is Objective `37/37` applicable with `11` truth-review-required rows, Predicate `44/48`, and Action template `24/24`; Gold remains pending human sign-off. Stage12-D is now the next stage.

- [x] **Step 8: Final scope audit; no intermediate commit**

  Compare changed files against this plan, preserve all A/B artifacts and unrelated user work, remove temporary databases/processes/artifacts or document retained ones, and keep the one-final-commit rule.

  Actual: A/B artifacts and unrelated work were preserved; the PostgreSQL test rolled back fixture data; no process, deployment or external effect was retained. No intermediate commit was created.

## Self-Review Record

- Spec coverage: QueryPlan AST, identifier resolution, table/view scan, typed filters, projections, unique-path Join planning, forward/reverse traversal, cycle/edge/depth budgets, group/aggregate/count semantics, stable sort/limit, scope/schema/version revalidation, provenance, hashes, default-off shadow and PostgreSQL evidence each map to a task.
- Boundary coverage: Planner still does not scan records; C computes authorized result sets but does not expand/persist Action candidates; no D/E/F, migration, public API/SSE, Provider, deployment, write or Telegram send enters the plan.
- Placeholder scan: every implementation step names concrete models/functions, stable errors, tests and commands; no deferred implementation marker or generic error-handling instruction remains.
- Type consistency: `AuthorizedRelationSpec` and QueryPlan/result contracts originate in Task 1, are extended and compiled in Task 2, executed by Tasks 3–6, observed in Task 7 and evaluated in Task 8. `QueryIntentSpec.execution_spec` is the only planned backward-compatible Stage12-B contract extension; all pre-existing summary fields remain readable and consistency-checked.
- Architecture risk checked: the existing B snapshot lacks linked-record target metadata and its QueryIntent summaries cannot represent conditional aggregates, HAVING, stable metric identity or typed sort targets. The confirmed additive contract resolves those gaps within the already approved C `Schema Linker + Project + TraverseLink + Aggregate` boundary; it does not add a public API or permission expansion.
