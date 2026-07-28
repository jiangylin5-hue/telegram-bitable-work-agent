# Stage09 Real Table Retrieval and Answer Evaluation Protocol

## Status

- Status: active real-provider evaluation protocol; the isolated non-personal fixture is persisted on the native server, but its values have not been sent to a provider in this protocol run.
- Scope: evaluate retrieval recall, retrieval precision, citation correctness, skill-route evidence, and fact correctness using the user-approved server-side fixture.
- User authorization: the user requested real-table-data import and quality metrics after the synthetic real-provider evaluation.
- Non-goals: deployment, schema/API/permission changes, writes to a source table, Telegram delivery, draft confirmation, notification delivery, or retention of raw table content in Git/evidence.

## 1. Boundary and source-selection rule

The evaluation has three distinct data locations. They must never be conflated:

```text
server source table (read-only)
  -> permission and sensitivity projection
  -> isolated evaluation workspace / in-memory import
  -> real OpenRouter inference with only the approved projection
  -> child-local scoring oracle
  -> redacted aggregate evidence
```

The source table is read-only. Its name, record values, user identifiers, record identifiers, provider credentials and model replies are not printed or committed. Inventory may expose only counts, field types, permission-policy presence, value-shape statistics and irreversible keyed fingerprints.

Before any provider call, the candidate table must satisfy all of the following:

1. it is a real persisted table rather than the earlier one-record synthetic fixture;
2. it has a documented owner-visible evaluation scope and a read path that honors current field/view permissions;
3. it contains no field explicitly marked hidden/restricted and no obvious direct identifier, contact detail, credential, financial identifier or free-text private note in the exported projection;
4. the evaluation can use a bounded snapshot of at most 50 records and no more than 12 selected visible fields;
5. its data is copied only into a fresh in-memory evaluation UoW. No import job, source-table row, audit event, outbox, Memory, vector index or persistent server database row is created.

If inventory shows that all available real tables contain restricted or personal data, the run stops before provider inference and asks the user to nominate a safe table or approve a specifically redacted projection. A user request for real data does not authorize sending credentials, hidden values, private notes or unfiltered personal data to an external provider.

## 2. Real-data import contract

“Import” means reconstructing approved field metadata and permitted record values in the in-memory `InMemoryStage06PlatformUnitOfWork`, not writing to the existing PostgreSQL source or creating a new persistent Base. Each imported source record receives an ephemeral evaluation record ID. A keyed digest maps source-to-evaluation IDs only inside the child process; it is discarded when the process exits.

The importer must:

- retain field type, visible key and normalized value semantics needed for the query;
- preserve the source view's current projection and field permissions;
- replace direct source IDs with ephemeral IDs;
- reject non-scalar / excessively long cell values rather than silently truncate them;
- record only aggregate imported-record and imported-field counts outside the child;
- verify source rows are unchanged before and after the read snapshot.

### 2.1 User-approved evaluation fixture fallback

The 2026-07-26 inventory found no server table large enough to score. The user then explicitly authorized a provided test-case table and its import. The retained fixture is `evidence/stage09-retrieval-evaluation-fixture.csv`; it contains 24 fictional, non-personal work items and no email, phone, address, credential, account, financial, customer or employee data.

It is intentionally a **real persisted import-flow fixture**, not real customer data. The import must create only the isolated `Stage09 Evaluation Fixture` Base and `evaluation_work_items` table under a dedicated evaluation workspace. The fixture is retained so its truth assertions can be reproduced. All answer text, citation IDs and provider payloads remain ephemeral.

## 3. Corpus and oracle

The corpus is generated deterministically from the imported snapshot, with no prompt or answer retained. It includes, where data shape permits:

| Case group | Query construction | Ground truth |
| --- | --- | --- |
| Exact lookup | visible primary value or unique categorical value | one matching record and its allowed fields |
| Filtered lookup | status/category/date predicate | complete set of matching record IDs |
| Aggregate | count/group-by over visible scalar fields | deterministic count or grouped total |
| Negative lookup | altered/nonexistent value | empty result; no fabricated match |
| Restricted-field guard | request for excluded field key | refusal/no excluded field citation |

At least 10 cases are required for a scored run; an insufficiently diverse safe snapshot is reported as `not_scorable`, not padded with synthetic cases.

For every case, the child process holds a normalized truth set of ephemeral record IDs, allowed field keys, expected aggregate value (if any), required skill IDs and forbidden skill IDs. It emits only boolean/counter results.

## 4. Metrics

| Metric | Formula | Gate |
| --- | --- | --- |
| Retrieval recall@k | relevant retrieved record IDs / truth record IDs | reported; target >= 0.90 |
| Retrieval precision@k | relevant retrieved record IDs / retrieved record IDs | reported; target >= 0.90 |
| Exact-match accuracy | correct exact/negative/aggregate cases / applicable cases | target >= 0.90 |
| Citation precision | citations referencing truth records and allowed fields / all citations | 1.00 |
| Citation recall | truth-supported answer claims with a valid citation / required claims | target >= 0.90 |
| Skill required recall | cases selecting every required skill / all cases | 1.00 |
| Skill forbidden precision | cases with no forbidden selection / all cases | 1.00 |
| Restricted-data leakage | leaked excluded markers or citations / all cases | 0 |
| Unsupported-claim rate | answer claims not matched by the truth oracle / asserted claims | 0 |
| Timeout/error rate | timed-out or execution-error cases / all cases | 0 |

Metrics are calculated from child-local, ephemeral truth and answer data. The parent and Git evidence receive aggregate numerators, denominators and fixed failure labels only.

## 5. Execution sequence

1. Run a server-side read-only inventory and choose a safe real persisted table; report only aggregate metadata.
2. Stop if no table satisfies the field/privacy gate; do not infer consent from the existence of a database row.
3. Implement and test the in-memory projection/importer and redacted metric DTO locally before provider use.
4. Run deterministic importer, source-unchanged check and truth-oracle tests against a disposable local PostgreSQL fixture.
5. Run one bounded real OpenRouter batch against the approved snapshot. Force dry-run/no-write/no-retention environment controls.
6. Write dated redacted evidence, audit working-tree changes and commit only after the run and verification are complete.

### 5.1 Native-server hotfix release boundary

The user explicitly authorized deployment of the current stage updates after the real import defect was found. The release is source-only and contains the SQLAlchemy field-flush correction plus this evaluation runner/fixture source. It does **not** introduce an Alembic revision, execute a migration, modify `runtime.env`, change Nginx/static assets, send Telegram, or enable provider writes.

The server procedure is:

1. Verify the current release, runtime, API health and absence of a fixture workspace before changing state.
2. Copy the active source release to a new immutable release directory; preserve the prior target for rollback.
3. Overlay only the reviewed changed files, calculate a manifest digest, atomically replace the `current` source symlink, and restart the API/worker/outbox services that import backend code.
4. Verify the exact new source digest, all affected service units and loopback health. If any check fails, atomically restore the prior source symlink and restart the same units.
5. Only after a healthy activation, import the dedicated 24-row fixture through the corrected service and run the provider evaluation.

### 5.2 Live evaluation runner architecture

The live runner is a bounded, read-only evaluation harness rather than a new product endpoint. It has four layers:

```text
persisted evaluation table (service-model read)
  -> child-local normalized snapshot and ephemeral record IDs
  -> one isolated in-memory digital-employee invocation per fixed case
  -> OpenRouter JSON response + deterministic skill evidence
  -> boolean/counter scorer
  -> aggregate-only evidence
```

1. The parent reads only the dedicated fixture table through `SqlAlchemyStage06PlatformUnitOfWork`, validates the expected nine field keys and 24-record count, and passes the normalized allowed fields into a short-lived child. It does not print record values or persist a copy.
2. Each child reconstructs the snapshot in `InMemoryStage06PlatformUnitOfWork`, maps server record IDs to random ephemeral IDs, creates an evaluation-only digital employee with `summarize` authority, and invokes `live_openrouter`. No child receives database credentials, Telegram credentials, write actions, notification rights, or provider-write tools.
3. The child requests a strict JSON object containing only `answer` and citations. Deterministic `build_stage06_skill_evidence()` runs from the same action/prompt/context and is scored against each case's required/forbidden skill set. The raw response, source record IDs, prompt body and provider request ID are discarded in the child.
4. The parent accepts only a redacted result: fixed case label, status, retrieval numerator/denominator, boolean quality/safety outcomes, and fixed failure labels. It writes an aggregate JSON/Markdown evidence record after the complete batch; no source values, answers, citations or secrets leave the process.

The batch uses ten fixed cases, maximum 30 seconds per child and one provider request per case. It sets no database writes after the pre-existing fixture import, sends no Telegram message, creates no draft, and makes no HTTP call except OpenRouter inference. A timeout or malformed response is counted as a failed case; it is never retried with a wider data projection.

## 6. Current Progress

The 2026-07-26 server inventory found seven active persisted tables, but none reached the minimum safe dataset gate: each had zero or one active record, and each non-empty candidate also had an identifier-like value-shape signal. The user therefore approved the documented non-personal 24-row fixture fallback.

The initial real import exposed a fail-closed defect: `commit_import_job()` created fields and immediately validated records in a `SqlAlchemyStage06PlatformUnitOfWork` whose session has `autoflush=False`; the fresh fields were not query-visible and record creation raised `unknown_field`. A focused regression test and the smallest fix (`add_field()` flushes only its newly added field) were added. The focused local suite passed.

On 2026-07-26, source release `stage09-p1-20260726-r40-eval-import` was atomically activated on the native server. The API, worker and outbox services were restarted and passed loopback health. The service-layer transaction then created exactly one dedicated fixture workspace, one Base, one `evaluation_work_items` table, nine fields and 24 records. The public API correctly rejected a forged development identity with `401 stage06_verified_identity_required`; the final import was instead executed as a trusted server-side maintenance transaction using the reviewed domain services and an auditable owner actor. No Telegram message, external provider write, migration, runtime configuration change or existing user data modification occurred.

Next: independently verify field/record/audit counts through the service model, then run the bounded real OpenRouter read-only quality batch and write only aggregate redacted evidence.

Verification now confirms the dedicated table has nine fields, 24 records and the expected workspace/table/import audit events. Two attempted long-running provider batches did not return a complete parent aggregate before the local orchestration deadline; their partial, unreturned work is deliberately excluded from all metrics. The next runner revision must persist only one redacted fixed-case result at a time, allowing an interrupted batch to resume without retaining raw prompts, records, answers or citations.

The revised process-isolated batch completed on 2026-07-26. All ten cases received a real provider response within their 35-second hard deadline, with no timeout and an unchanged source snapshot. The quality gate failed: exact-match accuracy was 0.10, retrieval recall was 0.00, citation safety was 0.10, forbidden-skill precision was 0.90, and the restricted-marker leak rate was 0.10. Required-skill recall, retrieval precision and unsupported-claim rate met their gates. The complete redacted aggregate and fixed labels are recorded in `evidence/stage09-real-provider-fixture-eval-2026-07-26.md`. Follow-up remediation is intentionally not implemented in this evaluation pass because it changes live response-contract and skill-policy behavior.
