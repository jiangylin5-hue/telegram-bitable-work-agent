# Stage09 Response Quality Remediation

## Status

- Status: approved for implementation on 2026-07-26
- Scope: replace model-selected table retrieval with a permission-constrained deterministic retrieval stage, then repair the Stage06 live response contract and skill-policy route exposed by the completed Stage09 real-provider evaluation.
- Non-goals: change table schema, user permissions, Telegram delivery, provider-write capability, model selection, or the persisted 24-row fixture.

## Evidence and problem statement

The completed ten-case fixture run had no timeout and no source mutation, but failed the quality gate: exact-match accuracy `0.10`, retrieval recall `0.00`, citation safety `0.10`, forbidden-skill precision `0.90`, and restricted-marker leak rate `0.10`. The redacted evidence is `evidence/stage09-real-provider-fixture-eval-2026-07-26.md`.

The current live-response JSON schema accepts a citation object without requiring `record_id` or `field_keys`; post-response validation only checks that `citations` is a list. The skill matcher recognises generic hidden-field wording but does not recognise field-name forms such as `private_notes`. These are separate defects and must have separate regression tests.

## Target architecture

```text
user prompt
  -> policy-intent normalization
  -> denied sensitive-field request: deterministic refusal, no LLM/table route
  -> otherwise bounded query-intent parser
  -> permission-filtered deterministic table query / filter / aggregate
  -> ephemeral result-set IDs and allowed fields
  -> LLM explanation of the result set only
  -> citation shape, visibility and result-set coverage validation
  -> accepted response or fail-closed validation error
```

`private_notes`, `internal_notes`, `hidden_*`, and `restricted_*` request variants are policy intents, not data intents. They select `platform-shared-policy`, reject data-access skills, and return a fixed refusal with an empty citation list. The provider receives no table values for that branch.

For permitted read-only answers, each citation object must contain exactly a non-empty `record_id` and a non-empty `field_keys` list. The backend validates that every cited record is in the deterministic result set and every cited field key is visible for that snapshot. Exact/filter/aggregate result modes additionally receive an authoritative citation projection generated from the deterministic result IDs; the model explains facts but does not author reference identifiers. This avoids model formatting drift while keeping result-set coverage complete and auditable.

The first implementation supports exact identifier lookup, conjunctive equality filters on visible scalar fields, and `count` aggregates. The parser produces a typed allowlisted intent or `clarification_required`; it never generates SQL, field names outside the visible schema, arbitrary operators, or unbounded scans. A shared scalar is bound to an explicit phrase when present (`high risk` maps to `risk_level=high`, rather than silently adding `priority=high`); this prevents an otherwise invisible false-negative conjunction. Semantic search, free-form aggregation, joins and formula evaluation remain later-stage work.

### 20-case follow-up: lexical normalization and answer coverage

The user-authorized real 20-case report found two remaining quality defects. First, a human query phrase such as `in progress` did not match the stored scalar `in_progress`, so the deterministic parser returned an overly broad project result set and lowered precision. Second, a model could omit a code while explaining a correctly retrieved and cited multi-record result set. The follow-up changes are deliberately bounded:

1. Normalize only separator-equivalent scalar values (`space`, `_`, and `-`) during prompt-to-visible-value matching; execution still compares the canonical stored value exactly.
2. For record-mode result sets, require every canonical result `ticket_code` to occur in the answer text before accepting it. Counts remain checked by their exact aggregate value.
3. Keep backend-authored citations, permission filtering, policy refusal, and unsupported-query clarification unchanged.

### Chinese query support

The first 20-case quality report intentionally used English prompts and therefore is not evidence for Chinese retrieval. The next bounded parser extension accepts Chinese command aliases (`列出`, `显示`, `查询`, `查找`, `多少`, `几个`) and canonicalizes a small explicit vocabulary of table scalar values before execution: `进行中` -> `in_progress`, `已完成` -> `done`, `已阻塞`/`阻塞` -> `blocked`, `计划中` -> `planned`, `高风险` -> `risk_level=high`, and `高优先级` -> `priority=high`. It does not translate arbitrary user text, infer unavailable fields, or expand the query language beyond the existing equality/count forms.

### Authoritative answer projection

Real mixed-language evaluation proved that deterministic retrieval and citations can be correct while a model still states an incorrect aggregate. For supported exact/filter/count queries, the user-facing factual answer is therefore rendered from the deterministic result projection: record answers include the canonical `ticket_code`, `status`, `risk_level`, and `summary` when visible; count answers include the canonical aggregate and supporting codes; empty identifier queries return a fixed not-found response. The provider may still be invoked for controlled observability and future non-factual wording, but cannot alter those factual values. Unsupported wording continues to request clarification.

Stage07 Team Bot may supply `view_records_override` only after its own bounded, permission-filtered projection pipeline. That compatibility path does not enter the new generic parser and retains its existing citation filtering. Strict result-set coverage is enabled only for the normal platform-query path, where this Stage09 executor owns the complete result set. This boundary avoids treating a pre-bounded adapter payload as if it were a fresh user query.

## Implementation plan

### Task 1: policy intent normalization

Files: `backend/app/agents/stage06_skill_matching.py`, `backend/tests/unit/test_stage06_skill_matching.py`.

1. Write failing tests for `private_notes`, `internal-notes`, `restricted customer field`, and existing `hidden field` phrasing.
2. Assert selected skills contain `platform-shared-policy` and contain no member of `DATA_ACCESS_SKILLS`.
3. Extend the normalized policy-denial trigger set and preserve the existing generic triggers.
4. Run the focused skill matcher test file.

### Task 2: fail-closed live citation contract

Files: `backend/app/agents/stage06_live_digital_employee.py`, `backend/tests/unit/test_stage06_live_digital_employee_runtime.py`.

1. Write failing tests for a citation lacking either required key, an empty `field_keys`, an unknown record ID, and a hidden field key.
2. Add a shared validator that receives the generated response plus the visible record snapshot; it must raise stable validation errors without echoing values.
3. Tighten the JSON schema with required citation properties and `additionalProperties: false` at citation-object level.
4. Run the focused runtime tests and retain valid-citation behavior.

### Task 3: policy refusal before provider invocation

Files: `backend/app/services/stage06_digital_employees.py`, `backend/tests/unit/test_stage06_live_digital_employee_runtime.py`.

1. Write a failing service-level test using a capturing LLM client; a sensitive-field request must return the fixed refusal, empty citations, guardrail evidence, and zero client calls.
2. Add the narrow pre-provider policy branch in `_invoke_live_digital_employee` after skill evidence exists but before context construction.
3. Preserve normal `summarize` behavior for permitted prompts.
4. Run service/runtime tests.

### Task 4: deterministic retrieval before LLM explanation

Files: `backend/app/services/stage09_table_retrieval.py` (new), `backend/app/services/stage06_digital_employees.py`, `backend/tests/unit/test_stage09_table_retrieval.py` (new), `backend/tests/unit/test_stage06_live_digital_employee_runtime.py`.

1. Write failing tests for exact ticket lookup, conjunctive visible-field filter (including the shared-value `high risk` / `high priority` collision), count aggregate, hidden-field query rejection, unknown field rejection, and result-set citation coverage.
2. Define immutable `TableQueryIntent` and `TableQueryResult` values. The executor accepts only the already permission-filtered visible record projection and performs no ORM/session access, SQL generation, or write.
3. Add a bounded English fixture-intent parser for the supported forms; unsupported wording returns `clarification_required` rather than falling back to full-table model context.
4. In the live employee service, route supported `summarize` prompts through this executor, pass only matched records to the LLM, and require returned citations to cover every returned record for exact/filter/count modes.
5. Run retrieval and runtime tests.

### Task 5: evaluation regression and release gate

Files: `backend/tests/unit/test_stage09_real_table_quality_eval.py`, `backend/scripts/stage09_real_table_quality_eval.py`, `backend/scripts/stage09_live_retrieval_eval.py`, Stage09 evidence documents.

1. Add evaluator tests that score a sensitive refusal with no marker leak and reject malformed citations.
2. Run the focused unit suite, then `stage09_live_retrieval_eval.py` on the native server with a per-process 60-second bound and four-worker maximum. A process reports exactly one projected score through a blocking queue read; the parent must never use `Queue.empty()` as an acceptance signal. It rebuilds the committed fixture in an in-memory platform unit of work so the invocation follows the normal (non-override) retrieval path without writing another server fixture. Only per-case outcome labels, boolean score signals and aggregate counters leave child processes; raw prompts, records, answers and provider identifiers are not retained.
3. Require source snapshot equality, 10 completed cases, zero timeout, zero restricted-marker leak, citation safety `1.00`, and forbidden-skill precision `1.00` before release acceptance.
4. Publish a source-only r41 for the initial retrieval implementation, then r42 for the corrected field-qualified filter parser, only after local tests pass; commit only after server audit and the final real evaluation complete.

## Acceptance criteria

- Sensitive-field variants do not invoke OpenRouter, do not select table-data skills, and return no citations.
- Supported query intents are executed deterministically over only visible fields and records; unsupported intents ask for clarification rather than send a full table to the model.
- Permitted live responses cannot expose a citation that is malformed, points outside the query result set, omits required result records, or names a hidden field.
- Existing valid citation tests remain green.
- The real fixture evaluation completes with no source mutation; quality evidence states both passing and failing metrics without raw response retention.
