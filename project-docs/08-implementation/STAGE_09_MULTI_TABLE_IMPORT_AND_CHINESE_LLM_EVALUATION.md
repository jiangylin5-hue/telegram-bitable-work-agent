# Stage09 多表导入、关联与中文真实 LLM 评测

## Status

- Status: approved execution scope — user explicitly requested a multi-table import, cross-table linked-record verification, and a real LLM Chinese multi-case report.
- Scope: create one dedicated non-personal evaluation workspace/Base, import three CSV-backed tables through the existing import-job service, add same-Base `linked_record` fields with service-validated target IDs, and run a bounded read-only real OpenRouter evaluation.
- Non-goals: modifying an existing user Base, database migration, Telegram send, provider-side write, draft confirmation, notification delivery, permission-policy expansion, or use of raw SQL for table/record creation.

## Test Dataset and Persistent Shape

All rows are fictional operational test data. The values contain no person name, email, phone, address, credential, payment identifier, customer note, or production record reference.

```text
Workspace: Stage09 Multi-table LLM Evaluation
Base: 多表关联中文评测样例

projects (6 imported rows)
  project_code, project_name, phase, delivery_state

work_items (18 imported rows)
  ticket_code, title, project_code, status, priority, risk_level, summary
  + project_link -> projects

risks (8 imported rows)
  risk_code, title, level, status, ticket_codes
  + affected_work_items -> work_items (one-to-many)
```

The CSV import intentionally retains stable external test keys (`project_code`, `ticket_code`, `risk_code`) as ordinary visible text. The second linking phase resolves only those test keys to freshly created same-Base UUID records, creates the two `linked_record` fields with `target_table_id`, then calls `update_record` with optimistic versions. `RecordLink` edges are therefore created only by the platform service's normal validation and synchronisation path.

## Execution Architecture

```text
three CSV fixtures
  -> create_import_job_from_csv / commit_import_job (three times; same Base)
  -> stable-key maps, visible relation fields, update_record
  -> service-model relation and edge-count verification
  -> child-local projection of the dedicated fixture only
  -> Chinese deterministic retrieval + real OpenRouter explanation
  -> canonical citations / skill evidence / truth oracle
  -> retained report: query, answer, skills, citations, per-case score
```

The persistent import is required to verify actual multi-table and edge creation. The provider batch does not receive database credentials or hidden fields. It receives only the evaluation fixture's visible projection in child-local memory. Unlike the earlier redacted run, the user explicitly requests query/answer retention; the dated report may therefore retain only these fictional rows' questions and answers. It must never retain provider credentials, request IDs, raw production identifiers, system prompts, or any non-fixture content.

## Chinese Case Matrix and Metrics

Twenty cases are required: exact ticket lookup, project-scoped filtered lists, aggregate counts, negative lookups, relation-label verification, and two restricted-field guards. At least twelve cases must use Chinese query text; English is not used as a fallback for a Chinese parser failure.

Each case records:

| Field | Meaning |
| --- | --- |
| `query` | fictional Chinese test question |
| `answer` | returned model/service answer |
| `skills` | deterministic selected skill IDs |
| `expected_codes` / `cited_codes` | fixture-only truth and canonical citation codes |
| `retrieval_recall` / `retrieval_precision` | set overlap against the fixture oracle |
| `citation_safe` | all citations are visible, canonical and truth-supported |
| `fact_correct` | expected code/count/status fragments present |
| `score` | all applicable gates pass |

Aggregate report gates: completion 20/20, zero timeout/error, recall >= 0.90, precision >= 0.90, exact-match >= 0.90, citation safety 1.00, required-skill recall 1.00, forbidden-skill precision 1.00, restricted-data leakage 0, unsupported-claim rate 0. A failed gate is reported as a result; it is never repaired by answer rewriting or retries with a wider projection.

## Implementation Steps

1. Add a deterministic fixture/import helper and RED unit test proving three import jobs reuse one Base, create 32 records, create two typed relation fields, and produce the expected edge count. Assert cross-Base and unknown-target linking remain rejected by the service.
2. Add twenty Chinese cases and a report DTO. Test the oracle against an in-memory imported fixture: queries, expected codes, exact score and safety guard must be deterministic without a provider.
3. Package and deploy a matching native source/venv/static candidate only after focused tests, full relevant suites and production build pass. Do not add a migration.
4. Run one bounded server-side maintenance import under the service account. Verify only aggregate base/table/field/record/edge/audit counts and that the current user workspace is untouched.
5. Run the real OpenRouter cases in bounded child processes. Persist a Markdown/JSON report locally with fictional query/answer/skill/citation-score data; record all aggregate metrics and failures.
6. Re-read server health and audit the working tree. Retain the dedicated evaluation Base for reproducibility; do not clean it or modify user data without later explicit instruction.

## Acceptance Criteria

- Exactly one dedicated Base contains the three imported tables, 32 fixture records and service-created relation edges.
- Every `linked_record` target is same-Base and resolves to the expected imported record; no raw SQL relationship write is used.
- The real batch contains 20 completed Chinese-centric cases or transparently lists bounded timeout/error cases.
- The final report includes query, answer, skills, recall, precision, citation safety and score for each case.
- No Telegram send, draft, notification, migration, external provider write or non-fixture data disclosure occurs.

## Current Progress

- 2026-07-27: local RED/GREEN coverage proved the three import jobs share one Base and create 32 records, two relation fields and 26 normalized edges. The first implementation exposed CSV header slugging (`ticket_code` becomes `ticket-code`) and default `field_n` mapping; the fixture now uses explicit source-to-stable-key mappings.
- 2026-07-27: r60 activated with sealed source/venv/static candidate gates and bounded readiness. The service-account import completed with 3 tables, 32 records, 2 relation fields and 26 edges.
- 2026-07-27: real OpenRouter 20-case batch completed with no timeout. Retrieval recall/precision, citation safety, required/forbidden skill gates and restricted-data leakage passed; exact-match was 0.95 because an unknown project-code query returned clarification rather than an explicit empty result. Full fixture-only report: `evidence/stage09-multitable-chinese-real-llm-report-2026-07-27.md`.
- 2026-07-27: r61 sealed the SQLAlchemy flush correction discovered during first server-side fixture creation. Source, venv and static artifacts were atomically activated only after layout, asset, static-parity, service-account module and readiness gates passed; r60 remains rollback.
