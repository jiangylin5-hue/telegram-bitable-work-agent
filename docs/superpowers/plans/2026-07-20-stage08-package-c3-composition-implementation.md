# Stage08 Package C3 Context Composition Implementation Plan

> 必须按 task-level TDD 执行。每个任务先写 RED、再 minimal GREEN、再独立复审；不以 C3 通过替代 Package E/F、真实 Provider 或部署验证。

## Goal

在不改变 C1/C2 公共合同且不创建任何外部或持久化副作用的前提下，实现 C1/C2 私有合成、36,000 内容级总预算、压缩 pending 传播和消费前重新验证。

## Preconditions

- C1 已关闭；C2 Tasks 1–6 已最终独立复审通过。
- 权威设计：`docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md`。
- C3 不可开始 Package E 的 `ContextCompressor`，也不可新增 API/schema/permission。

## File Map

| Operation | File | Responsibility |
| --- | --- | --- |
| Create | `backend/app/runtime/stage08_context_composition_contracts.py` | strict safe view/budget usage and deep validation; no body carrier |
| Create | `backend/app/services/stage08_context_composition.py` | C1+C2 current-state composition and private renderer |
| Create | `backend/tests/unit/test_stage08_context_composition_contracts.py` | safe view/model-construct/privacy/budget tests |
| Create | `backend/tests/unit/test_stage08_context_composition_service.py` | C1+C2 ordering, drift, pending, renderer and no-side-effect corpus |
| Create | `backend/tests/integration/test_stage08_context_composition_postgres.py` | disposable PostgreSQL combined re-read/drift evidence |
| Create | `project-docs/08-implementation/evidence/stage08-package-c3-composition.md` | actual RED/GREEN/local PG/static evidence |
| Create | `.superpowers/sdd/stage08-package-c-task-c3-report.md` | changed files, verification, risks and cleanup |

## Task 1 — Strict private-composition contracts

**Status:** complete — task-level RED→GREEN and independent review `PASS / 0 Critical / 0 Important / 0 Minor`; focused contract suite `27 passed`. This does not close C3.

1. Write failing contract tests for invalid `group_compression_pending` shape, text/UUID/identity carrier fields, a false 36,000 budget view, and nested `model_construct` bypasses.
2. Run RED for only the new contract module.
3. Implement frozen Pydantic safe-view/value contracts. They expose counts/status/boolean only; no `content`, `scope` values, handles, plan, actor, identifier, digest or renderer fields.
4. Run GREEN and static serialization-negative tests.

## Task 2 — C1/C2 private composer and direct renderer

**Status:** complete — two real security defects found during task/review (mapping-version stale consumption, cross-actor binding) and the final review found a forged zero-fragment lineage bypass plus budget coverage gap. All were repaired with RED→GREEN; fresh independent re-review `PASS / 0 Critical / 0 Important / 0 Minor`, focused service `20 passed`, C1/C2/C3 unit regression `178 passed`. This does not close C3.

1. Write failing service corpus for same-scope C1+C2 merge, C1-first/C2-window deterministic order, 36,000 content bound, unavailable group preservation of C1, removal of general marker when group evidence exists, source/lifecycle/mapping/member/relation drift, and `repr`/view privacy.
2. Run RED.
3. Implement only an internal `compose_stage08_context` and `render_stage08_composite_context`. Build C2 authority from plan/actor/current state; call the existing C2 private materializer only after C2 window revalidation. Recompose before rendering; never accept caller group identifiers.
4. Run GREEN, including no new database/audit/outbox/Memory mutation assertions.

## Task 3 — Compression pending and failure semantics

**Status:** complete — real `49 × 500 = 24,500` pending-window RED→GREEN, the later direct-to-pending transition repair, and independent reviews passed. C3 did not invoke a Provider, materialize a pending group body, or add a public handoff.

1. Write failing tests that force a C2 window over 24,000 and assert C3 neither materializes body nor invokes/imports Provider, but returns safe pending state and an opaque private E handoff only.
2. Run RED.
3. Implement pending propagation. C3 must not synthesize digest, truncate to a fake group answer, or render raw group text in this branch.
4. Run GREEN and static forbidden-dependency scan.

## Task 4 — Real PostgreSQL package composition evidence

**Status:** complete — disposable local PostgreSQL evidence covered C1 relation/field/Memory and C2 mapping/relation/provenance/expiry/purge drift. The initial ten-case RED and later twelve-case expansion are separately documented; Task 4 remediation review passed.

1. Write failing disposable PostgreSQL cases combining C1 scoped relation/field/Memory changes with C2 mapping/provenance/purge/expiry drift after private composition and before renderer consumption.
2. Run RED.
3. Apply only a minimal C3 correction if real current-state revalidation is missing; do not reopen C1/C2 unless a narrowly proven defect requires its own follow-up review.
4. Run C3/C2/C1 focused suite, compileall, static privacy scan and `git diff --check`; record actual outputs and cleanup.

## Task 5 — Independent review and Package C handoff

**Status:** complete — first review correctly failed on the direct-to-pending renderer defect; the minimal C3 repair passed its own independent review, then fresh package review passed `0 Critical / 0 Important / 1 non-blocking Minor`. Package C is eligible for source-document closure and Package D handoff only.

Review D1–D6 preservation, C1/C2 compatibility, privacy, no persistence/external effects, 36,000 content bound, compression pending and local PostgreSQL evidence. If clean, update Package C BDD/source-of-truth/implementation plan/acceptance ledger to show C3 completion only. Package C may become `evidenced-pending`; Package E/F/provider/deployment remain pending.

## Required Final Commands

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = $env:STAGE06_LOCAL_DATABASE_URL
Push-Location backend
python -m alembic upgrade head
python -m alembic heads
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/integration/test_stage08_context_postgres.py tests/integration/test_stage08_group_context_postgres.py tests/integration/test_stage08_context_composition_postgres.py
$exitCode = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL = $originalDatabaseUrl
exit $exitCode
```

```powershell
Push-Location backend
python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
rg -n "Message|raw_text|raw_caption|normalized_text|TelegramBot|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route|Redis|pgvector|LangGraph|MemoryItem|AgentRun|audit|outbox" backend/app/runtime/stage08_context_composition_contracts.py backend/app/services/stage08_context_composition.py
git diff --check -- backend project-docs/08-implementation docs/superpowers
```

The scan has to be interpreted line-by-line: type names in a documentation string are not a pass; C3 production imports, calls or persistence to prohibited boundaries fail review.
