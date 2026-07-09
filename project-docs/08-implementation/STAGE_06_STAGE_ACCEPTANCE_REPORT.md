# Stage 06 Stage Acceptance Report

## Status

- Document status: final Stage06 backend-stage acceptance
- Scope: Generic Telegram-first multidimensional table backend, template/import, table-bound digital employees, Stage06 skill evidence and Package 6 security hardening
- Acceptance date: 2026-07-10
- Decision: `Passed` for the documented Stage06 backend-readiness scope
- Launch decision: `Not claimed`; Mini App, remote staging and production deployment remain separate gates

## 1. Lineage Correction

Stage06 work originally started while the repository was still on `codex/stage-05-development`. The Stage05 branch itself ends at `fa645d9`; the Stage06 platform pivot then remained partly in the shared uncommitted worktree while Package 6 was committed on `codex/stage-06-hardening`.

The pre-acceptance worktree contained:

- 14 modified tracked files: active project/platform truth documents, Stage06 router registration, unified model registration and the metadata acceptance test;
- 26 untracked files: migrations `20260709_0017` to `20260709_0019`, Stage06 runtime/template models, live digital employee and skills runtime, smoke/evaluation scripts, Stage06 tests and Stage06 design documents.

Content review classified all 40 files as Stage06. No Stage05 business hotfix, staging credential, customer send change, provider write or funds/account operation is included in the Stage06 completion commit.

## 2. Accepted Stage06 Scope

The accepted backend stage contains:

- platform-first project/source documents;
- workspace, member, base, table, field, JSONB record, link, lookup, view and form storage;
- CSV and Excel preview/commit with bounded payload, shape and cell limits;
- official generic templates plus an optional advertising sample;
- table-bound digital employee configuration and deterministic/live OpenRouter runtime;
- Telegram member-bound mention context;
- permission-filtered reads, draft-first writes, confirmation and audit;
- server-controlled notification fail-closed behavior;
- cursor pagination and idempotent protected mutations;
- additive PostgreSQL migration chain through `20260710_0020`;
- Stage06 skill manifest/matching evidence and the 118-case deterministic benchmark;
- sanitized machine-readable security evidence.

## 3. Acceptance Matrix

| Gate | Evidence | Result |
| --- | --- | --- |
| S6-01 to S6-08 platform/docs/import/templates | Source/SDD/contract plus platform and template/import tests | Passed |
| S6-09 to S6-16 digital employees, live runtime, draft and notification safety | Runtime/API tests plus retained real OpenRouter evidence | Passed |
| S6-17 PostgreSQL migration | Disposable local PostgreSQL migrated to `20260710_0020` | Passed |
| S6-18 Telegram backend entry | Retained real `@ops` smoke with reversible webhook restoration | Passed |
| S6-19 safety close | Provider disabled and notification fail-closed evidence | Passed |
| S6-20 to S6-21 skills evidence | 27 manifests, 11 active core skills, 118-case evaluator | Passed |
| S6-22 to S6-27 Package 6 security gates | Identity, membership, tenant, lookup/audit, limits, pagination, idempotency, concurrency and sanitized artifact tests | Passed |

The detailed requirement-level status remains in [Stage 06 BDD And Acceptance](STAGE_06_BDD_AND_ACCEPTANCE.md) and [Stage 06 Backend Exit Audit](STAGE_06_BACKEND_EXIT_AUDIT.md).

## 4. Fresh Verification

Commands were run from the complete Stage06 worktree before the final commit:

```powershell
pytest -q tests/unit -k stage06
```

Result: `129 passed, 173 deselected`.

```powershell
python scripts/stage06_skill_hit_rate_eval.py
```

Result: `ok=true`, 118 cases, top-1 `0.8923`, top-3 `1.0`, zero high-risk false commit routes and zero unauthorized-data false positives.

```powershell
$env:STAGE06_LOCAL_DATABASE_URL='<disposable-local-postgres>'; python scripts/stage06_security_hardening_smoke.py
```

Result: all 4 checks passed; migration head `20260710_0020`; PostgreSQL tenant/audit/concurrency tests `2 passed`.

```powershell
$env:STAGE06_LOCAL_DATABASE_URL='<disposable-local-postgres>'; pytest tests -q
```

Result: `402 passed, 17 skipped`.

Additional final gates:

- `python -m compileall -q app scripts`: passed;
- `python -m alembic heads`: one head, `20260710_0020`;
- metadata registration: all Stage06 tables, including `stage06_idempotency_records`, registered;
- `git diff --check`: passed; Windows line-ending warnings only;
- sanitized evidence: `evidence/STAGE_06_SECURITY_HARDENING_EVIDENCE.json` contains no URL, credential, raw record, Telegram text or LLM payload.

## 5. Retained External Evidence

The following prior Stage06 evidence was reviewed and retained rather than repeated during this acceptance:

- real OpenRouter summarize and draft-update calls;
- five-case post-skill OpenRouter smoke;
- real Telegram `@ops` backend entry with temporary polling and webhook restoration.

No new Telegram send, webhook mutation, provider write, funds movement or account operation was performed for this acceptance.

## 6. Skipped Tests

The 17 skipped tests are historical Stage02 online PostgreSQL tests requiring `STAGE02_ONLINE_DATABASE_URL`. They do not cover Stage06; the new Stage06 local PostgreSQL migration, isolation, redaction and concurrency tests ran and passed.

## 7. Remaining Risks

- Mini App and desktop-browser UI are not implemented by explicit scope decision.
- A production verified-identity provider adapter is not connected.
- Remote staging/production PostgreSQL and deployed webhook topology are not proven.
- Stale `in_progress` idempotency reservations need an expiry/recovery runbook before production traffic.
- Formula, attachment, workflow and dashboard breadth remains Stage07+ work.
- The 118-case skill evaluation is deterministic routing evidence; the five real LLM cases are smoke evidence, not a statistical live-model quality evaluation.

## 8. Temporary Cleanup

- No real secrets or local `.env` files are committed.
- PostgreSQL tests use and reset an explicitly disposable local database.
- No temporary webhook state or test polling process remains.
- The JSON security artifact and labeled skill fixture are retained intentionally as regression/acceptance evidence.

## 9. Final Decision

Stage06 is accepted and may be frozen as the backend baseline for the next separately confirmed phase.

This decision does not authorize production launch, Mini App implementation, broad Telegram sends, provider writes, funds operations or account production. Those require their own scope, documents and acceptance.
