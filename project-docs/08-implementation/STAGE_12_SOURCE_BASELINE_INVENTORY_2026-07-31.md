# Stage12 Source Baseline Inventory

## Status

- Status: `implemented-local-checkpoint; release-fail`
- Inventory date: 2026-07-31
- Branch: `codex/stage09-ai-conversation-sse`
- Baseline before checkpoint: commit `2ba69ed`
- Production authority: Stage11/r76
- Deployment: not performed
- Push: pending

## Purpose

This document closes the long-lived uncommitted Stage12 A–F source state before Grounded Answer Provider V2 implementation begins. The checkpoint preserves reproducible source and failure evidence; it does not claim Stage12 acceptance, real-model reliability or production readiness.

## Inventory Before This Document

The worktree contained exactly 225 uncommitted paths:

- 30 modified tracked files;
- 195 untracked files.

### Modified tracked files

| Category | Count | Scope |
| --- | ---: | --- |
| Backend API | 1 | Stage12 admission/action/trace integration in the existing run API |
| Backend models | 2 | event/runtime and Stage12 persistence integration |
| Backend schema | 1 | event/runtime Stage12 projection |
| Backend services | 4 | event runtime, orchestration, SSE and platform authorization integration |
| Backend worker | 1 | typed Specialist/Action runtime integration |
| Backend tests | 9 | API, PostgreSQL, Redis, migration, worker and SSE regression |
| Mini App | 8 | pending Action review/confirm/reject and Stage12 run projection |
| Governance | 1 | approved Stage12 technical decisions |
| Backend registration/config | 3 | capability registry, settings and FastAPI route registration |

### Untracked Stage12 files

| Category | Count | Scope |
| --- | ---: | --- |
| Alembic migrations | 5 | Retrieval V2, durable Action, same-table relations, relation identity and scope registration |
| Backend API/model/schema | 7 | Stage12 Action route, persistence and strict contracts |
| Backend services | 42 | Planner, authorized query, retrieval, typed Specialist, ClaimGraph, Provider and Action services |
| Backend workers | 3 | Retrieval outbox/runtime and durable Action worker |
| Evaluation scripts | 12 | Evaluation V2, Planner/Query/Retrieval/Provider/quality/campaign tooling |
| Backend tests and fixtures | 73 | unit, API, PostgreSQL and frozen complex-case fixtures |
| Architecture documents | 7 | Stage12 Quality Architecture V2 package |
| Implementation/acceptance documents | 9 | A–F, Human Gold and integrated audit sources |
| Implementation plans | 11 | approved Stage12 A–F/correction/campaign plans |
| Evidence | 30 | deterministic, PostgreSQL, Redis, Provider, Human Gold and campaign evidence |

## Migration Chain

The five new migrations form one linear chain:

```text
20260728_0034
-> 20260729_0035
-> 20260730_0036
-> 20260730_0037
-> 20260730_0038
-> 20260730_0039
```

No production migration has been executed for this checkpoint.

## Hygiene Audit

- No `.env`, private key, token file, SQLite/database file, cache, build output or temporary directory is part of the inventory.
- Literal scans found configuration key names and test strings, but no private-key header or OpenRouter token prefix.
- The only file above 1 MiB is the approximately 5.8 MiB immutable pre-correction real campaign JSON. It is retained because it records the failed baseline rather than hiding it.
- `git diff --check` passed; Windows emitted existing LF/CRLF conversion warnings, not whitespace errors.
- Existing `.tmp` permission-denied directories are ignored, pre-existing and excluded from Git.

## Verification Already Bound To This Source State

The same worktree content, before this inventory-only addition, produced the following retained evidence:

- backend: `2411 passed, 40 skipped`;
- disposable PostgreSQL/pgvector matrix: `7 passed`;
- Mini App: `413 passed`;
- production build: pass, `1853 modules`;
- Alembic current/head on the disposable database: `20260730_0039`;
- temporary Stage12 schema count: `0`;
- production write, confirmed Action and Telegram send counts: `0/0/0`.

The 40 skips remain classified as missing independent Redis/online PostgreSQL/Stage08 PostgreSQL/pgvector environments and are not counted as passes.

## Known Release Failure

The post-correction real `48 × 3` campaign returned 144 safe answers, but only 24 obtained a completed real Composer result. The remaining 120 cases exhausted two schema-invalid attempts, producing 240 schema-invalid observations. Provider-originated final-answer reliability and total latency therefore fail the unchanged Stage12 release gates.

This checkpoint must be described as `release-fail`. Deterministic fallback results do not prove the required real-model answer path.

## Next Authorized Correction

The user approved `Grounded Answer Provider V2` on 2026-07-31. Its design is:

`docs/superpowers/specs/2026-07-31-stage12-grounded-answer-provider-v2-design.md`

The correction requires:

1. a fixed-array Provider contract;
2. real model-authored final Chinese answer statements;
3. deterministic claim/evidence/action grounding validation;
4. explicit `answer_source` and split failure taxonomy;
5. a 12-call real compatibility gate before any full campaign;
6. zero fallback in Stage12 real-model acceptance;
7. native server deployment only, using Nginx/systemd/FastAPI/PostgreSQL/pgvector/Redis;
8. bounded real server-backend and Telegram tests after local gates pass.

## Checkpoint Boundary

This checkpoint intentionally includes the complete identified Stage12 A–F source/evidence package and the existing shared integration diffs. It excludes ignored local credentials, temporary files, runtime databases, build output and server artifacts. Subsequent Grounded V2 work must be committed separately so the previous failed state remains inspectable.
