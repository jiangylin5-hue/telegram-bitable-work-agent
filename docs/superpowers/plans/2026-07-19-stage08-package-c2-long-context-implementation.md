# Stage08 Package C2 Long Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为一个已授权 Telegram group/supergroup 建立可删除、30 天保留、最多 120 片段的受控上下文投影；超过固定 24,000-code-point Agent 窗口时，为 C3/E 提供短命压缩请求，而不是创建长期 Memory。

**Architecture:** C2 在既有已验证的 Telegram 入站事务中，只为新消息和已知 edit 创建 500-code-point 受控投影；历史 `Message` 原文永远不回填、不作为读取源。C2 按 opaque authority、active binding/mapping、业务 scope、lifecycle 和 retention 重读最多 120 个片段，输出内部 `GroupContextWindow` 与 `compression_required`。C3 负责与 C1 合并和全局预算，Package E 才可通过受控 Provider 生成调用内 digest；digest 不得持久化。

**Tech Stack:** Python 3.12+、FastAPI 既有服务边界、Pydantic v2、SQLAlchemy 2.x、Alembic、PostgreSQL、pytest。当前任务不新增 HTTP client、Telegram 请求、Provider 调用、Redis、pgvector、LangGraph、route、role/action、Mini App 或外部写入。

## Global Constraints

- D1：只处理新 group/supergroup 入站与已知 edit；旧 `Message.raw_text`、`raw_caption`、`normalized_text` 不回填、不读取；本任务不删除历史 Message。
- D2 固定值：30 天 source retention、120 个片段、每片段 500 Unicode code points、最多 60,000 code points 原始工作窗口、最终群 context 24,000 code points、最新 24 片段最多 12,000 code points、调用内 digest 最多 12,000 code points、history half-life 7 天。
- D3：采用 `best_effort_group_deletion`。known edit、server-authorized purge 和 retention 到期必须失效；普通群远端 delete/revoke 没有可依赖 Bot API 事件，严禁声明即时观测。
- D4：一个 active Stage06 chat-user binding 必须有且仅有一个同 workspace customer record 与 project record mapping；空、重复、漂移或 relation 无效一律 unavailable。
- D5：`Stage08GroupContextAuthorityFactory` 只从 verified actor/employee/current workspace 自行解析 state，返回不可 Pydantic/JSON 序列化的 private object；不得接收 chat/binding/message/text 参数。
- D6：`label=group_context`、`source_type=group_message_fragment`、呈现 ID `group_context:NN`；C2 pack 在 C3 前不可消费。
- `content_fragment` 是唯一允许为此功能持久化的受控群正文；它不得进入任何公开 DTO、renderer、audit、error、trace、cache、Memory、RAG/vector、AgentRun 或 LangGraph checkpoint。
- 不得扩大既有 Telegram webhook/HTTP 能力：只可在既有已验证入站持久化路径新增本地 projection 写入；不触发 Telegram 网络调用。
- 每一生产行为先写一个会正确失败的测试，执行 RED，再作 minimal GREEN；每个任务必须通过独立 review。当前 worktree 有用户未提交修改，未经明确授权不得 stage、commit、reset、checkout 或 clean。

---

## File Structure

| Operation | File | Responsibility |
| --- | --- | --- |
| Create | `project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md` | D1-D6 最终值、Bot API 删除限制、projection/mapping schema、retention/purge 语义和 C3/E 分界 |
| Modify | `project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md` | 将 C2 BDD 从短窗口改为已确认长窗口/压缩合同 |
| Modify | `project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md`、`STAGE_08_IMPLEMENTATION_PLAN.md`、`STAGE_08_DATA_API_SECURITY_CONTRACT.md` | 记录已确认 D2/D3、受控 ingestion exception 和不持久化 digest 规则 |
| Create | `backend/app/models/stage08_group_context.py` | `Stage08GroupBusinessContextBinding`、`Stage08GroupMessageProjection` ORM 边界 |
| Create | `backend/alembic/versions/20260719_0030_stage08_group_context.py` | 两表、FK、active mapping uniqueness、lifecycle/version/retention 和 source ordering index |
| Modify | `backend/app/models/__init__.py`、`backend/app/services/stage06_platform.py` | model export 与 protocol/in-memory/PostgreSQL UoW parity |
| Modify | `backend/app/schemas/telegram_webhook.py`、`backend/app/services/telegram_update_parser.py`、`backend/app/services/telegram_ingestion.py` | 既有 new/edited update 的受控本地 projection writer；不新增网络/route |
| Create | `backend/app/runtime/stage08_group_context_contracts.py` | strict internal budget/plan/window/pack/omission contracts；public serialisation rejects content and identifiers |
| Create | `backend/app/services/stage08_group_context.py` | opaque authority factory、mapping/lifecycle resolver、selector、purge、window composition和 C3 compression signal |
| Create | `backend/tests/unit/test_stage08_group_context_contracts.py` | DTO and carrier rejection、fixed thresholds/status tests |
| Create | `backend/tests/unit/test_stage08_group_context_ingestion.py` | new/edit projection/redaction/legacy-refusal tests |
| Create | `backend/tests/unit/test_stage08_group_context_service.py` | authority/scope/order/budget/purge/rebuild tests |
| Create | `backend/tests/integration/test_stage08_group_context_postgres.py` | real PostgreSQL schema/constraint/lifecycle/concurrency evidence |
| Create | `project-docs/08-implementation/evidence/stage08-package-c2-group-history.md` | only actual command results, exclusions and retained risks |
| Create | `.superpowers/sdd/stage08-package-c-task-c2-report.md` | task reports and RED/GREEN evidence |

## Interfaces

```python
class Stage08GroupContextAuthorityFactory:
    def build(
        self,
        uow: Stage06PlatformUnitOfWork,
        *,
        workspace_id: UUID,
        employee_id: UUID,
        actor: Actor,
    ) -> _GroupContextAuthority: ...

def build_group_context_window(
    uow: Stage06PlatformUnitOfWork,
    authority: _GroupContextAuthority,
    *,
    business_scope: ResolvedBusinessScope,
    now: datetime,
) -> GroupContextWindow: ...

def purge_expired_group_context_projections(
    uow: Stage06PlatformUnitOfWork,
    *,
    now: datetime,
) -> GroupContextPurgeResult: ...

def purge_group_context_projection(
    uow: Stage06PlatformUnitOfWork,
    authority: _GroupContextAuthority,
    *,
    projection_handle: _GroupProjectionHandle,
    now: datetime,
) -> GroupContextPurgeResult: ...
```

`_GroupContextAuthority` and `_GroupProjectionHandle` are private Python objects, not BaseModels and never API parameters. `GroupContextWindow` is internal-only: its public validation/rendering view contains status, counts, budget usage and `compression_required`, never fragment text, raw identifiers, IDs, token, permission or source references.

### Task 1: D3 Decision Record and Contract Reconciliation

**Files:**
- Create: `project-docs/08-implementation/decisions/STAGE_08_C2_D3_GROUP_CONTEXT_DATA_CONTRACT.md`
- Modify: C2 BDD, Stage08 source/implementation/data-security documents and `docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md`
- Test: none; this is documentation-only and creates no production behavior

**Produces:** one precise, Chinese decision record that is the only implementation authority for D2/D3; it reconciles the old 20/12/6,000 profile and old no-ingestion wording with the approved 120/60,000/24,000 design.

- [x] **Step 1: Write the decision record before schema work**

Record the exact D1-D6 values from the approved design. State that `content_fragment` is a 500-code-point controlled projection for new/edited inbound messages; an old Message row is always unavailable. State `event_at=Telegram message.date UTC`, late delivery does not alter ordering, and `best_effort_group_deletion` means only known edit, authorized purge and retention expiry are trustworthy invalidation facts.

- [x] **Step 2: Reconcile all current C2 contracts**

Replace obsolete values `recent 20/history 12/group 6000` with the long-window constants. Define: `group_context_unavailable` for invalid authority/scope/no eligible source; `group_context_partial` for at least one safe fragment plus any count/char/age/budget omission; `group_context_available` only with no such omission. Define `compression_required = raw_selected_chars > 24000` and prohibit C2 Provider calls.

- [x] **Step 3: Document the permitted ingress exception**

Write that the existing trusted ingress path may write a projection in the same local transaction but C2 does not add a webhook, polling loop, outgoing Telegram request or historical raw read. State C3 owns merge and E owns provider compression, so no digest can persist here.

- [x] **Step 4: Verify documentation consistency**

Run:

```powershell
rg -n "recent 20|history 12|6000|即时删除|D3.*未确认|TODO|TBD" project-docs/08-implementation/STAGE_08_PACKAGE_C2_GROUP_HISTORY_BDD_AND_ACCEPTANCE.md project-docs/08-implementation/STAGE_08_SOURCE_OF_TRUTH.md project-docs/08-implementation/STAGE_08_IMPLEMENTATION_PLAN.md project-docs/08-implementation/STAGE_08_DATA_API_SECURITY_CONTRACT.md docs/superpowers/plans/2026-07-19-stage08-package-c2-group-history.md
git diff --check -- project-docs/08-implementation docs/superpowers/plans
```

Expected: no stale active C2 value or whitespace error; historical design evidence may retain its dated wording only if labelled historical.

### Task 2: Data Model, Migration and UoW Parity

**Files:**
- Create: `backend/app/models/stage08_group_context.py`
- Create: `backend/alembic/versions/20260719_0030_stage08_group_context.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/services/stage06_platform.py`
- Test: `backend/tests/integration/test_stage08_group_context_postgres.py`

**Consumes:** Task 1 data contract.

**Produces:** versioned business mapping and smallest possible new-message projection with UoW methods for add/get/list/lock/purge; no API or Provider.

- [x] **Step 1: Write failing PostgreSQL tests**

Create fixtures for one workspace/base/table/customer/project, one active Stage06 `chat_user` binding and one mapping. Assert a second active mapping for the same binding fails; a projection requires active mapping, `content_version >= 1`, valid UTC timestamps, `retention_expires_at > event_at`, lifecycle in `active/superseded/purged`, unique `(source_message_id, content_version)`, and an expired/purged fragment is not listable as active.

- [x] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: fail because C2 models/UoW/migration are absent.

- [x] **Step 3: Add the minimal schema and UoW parity**

Implement `Stage08GroupBusinessContextBinding` with workspace/binding/customer-record/project-record/mapping-version/status fields and partial unique active binding index. Implement `Stage08GroupMessageProjection` with source Message FK, mapping FK, bounded fragment, version/event/edit/retention/lifecycle/tiebreak fields and indexes for active mapping/time reads. Add matching UoW protocol, in-memory and SQLAlchemy implementations; lock only mapping/projection lifecycle transitions, not raw Message.

- [x] **Step 4: Apply migration and run GREEN**

```powershell
Push-Location backend; python -m alembic upgrade head; python -m alembic heads; python -m pytest -q tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: one head `20260719_0030`; real PostgreSQL fixtures prove constraints and listability.

### Task 3: Trusted Ingress Projection and Best-Effort Lifecycle

**Files:**
- Modify: `backend/app/schemas/telegram_webhook.py`, `backend/app/services/telegram_update_parser.py`, `backend/app/services/telegram_ingestion.py`
- Test: `backend/tests/unit/test_stage08_group_context_ingestion.py`, Task 2 PostgreSQL test

**Consumes:** Task 2 UoW/schema.

**Produces:** a local new/edited ingress writer that creates or supersedes 500-code-point projections only when a current eligible mapping exists; no route/client/network change.

- [x] **Step 1: Write failing ingress tests**

Test a normal group new message creates one normalized 500-code-point fragment with UTC `event_at` and `retention_expires_at=event_at+30d`; private/channel/unmapped/inactive binding creates no projection; an `edited_message` creates version 2 and supersedes version 1; old raw Message rows are not enumerated; all test-safe output excludes raw chat/message/update identifiers.

- [x] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: fail because parser accepts only the old message shape and no projection writer exists.

- [x] **Step 3: Implement the narrow writer**

Extend the existing webhook schema/parser to distinguish `message` and `edited_message` while using the existing verified webhook path. The ingestion service must resolve one current eligible Stage06 binding plus mapping before it sees a fragment, normalize/truncate to 500 code points, persist mapping-bound projection and version transition atomically, and do nothing if any gate is invalid. Do not query old `Message.raw_*` fields and do not create any outgoing Telegram call.

- [x] **Step 4: Run GREEN and static boundary check**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
rg -n "getUpdates|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route" backend/app/services/telegram_ingestion.py backend/app/services/telegram_update_parser.py
```

Expected: tests pass; no new network/Provider/API matches.

### Task 4: Opaque Authority, Long-Window Contract and Purge Service

**Files:**
- Create: `backend/app/runtime/stage08_group_context_contracts.py`
- Create: `backend/app/services/stage08_group_context.py`
- Test: `backend/tests/unit/test_stage08_group_context_contracts.py`, `backend/tests/unit/test_stage08_group_context_service.py`

**Consumes:** Task 2 schema/UoW and Task 3 lifecycle facts.

**Produces:** private authority, 120/60,000 selector, 24,000 compression signal, safe public counters/statuses, authorized purge and current-source re-read. It does not produce a digest or call a Provider.

- [x] **Step 1: Write failing contract tests**

Assert all exact constants; reject `model_construct`, client-shaped authority, fragment text/IDs/source refs in public pack, invalid statuses, a 501st-code-point fragment, a 121st fragment, and a public `compression_required` pack with text. Assert only private internal objects carry text/source handles.

- [x] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_contracts.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: fail because no C2 runtime contract exists.

- [x] **Step 3: Write failing service tests**

Test factory rejects actor/member/employee/binding/mapping/customer/project workspace drift and private/channel; valid source selects deterministic 24 newest plus decay-ranked history to 120; over 24,000 sets `compression_required`; over 60,000 cannot occur; purge/expiry/superseded version remove fragments; a re-read after mapping/version/purge drift returns unavailable or rebuild-required; no Memory/outbox/audit/AgentRun mutation occurs.

- [x] **Step 4: Run service RED**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: fail because authority/window/purge service is absent.

- [x] **Step 5: Implement minimal contracts and service**

Use frozen, `extra="forbid"` models for public count/status views and private dataclasses for authority/handles/text. Revalidate all public models from dumps. Build one source-only, same-workspace resolver and stable selector; tag `compression_required` rather than compressing. `purge_expired_group_context_projections` must erase fragment text idempotently, and `purge_group_context_projection` must require private authority/handle. Neither function can return text or IDs.

- [x] **Step 6: Run GREEN**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: all focused contract/service tests pass.

### Task 5: Real PostgreSQL Drift, Privacy and Package C2 Closure

**Files:**
- Modify: `backend/tests/integration/test_stage08_group_context_postgres.py`
- Create: `project-docs/08-implementation/evidence/stage08-package-c2-group-history.md`
- Create: `.superpowers/sdd/stage08-package-c-task-c2-report.md`

**Consumes:** Tasks 2–4.

**Produces:** real local PostgreSQL evidence that C2 reads current projection state, does not leak/persist digest content and is ready only for C3 handoff.

- [x] **Step 1: Write failing lifecycle/privacy tests**

In a disposable PostgreSQL transaction, create a valid mapping/projection/window; independently edit, supersede, expire, purge, deactivate member/binding/mapping and change business record relation after plan construction. Assert old fragment never appears, the recomposed window is unavailable/rebuild-required, no text/identifier carrier serializes, and concurrent purge versus reader resolves by current locked state without stale safe output.

- [x] **Step 2: Run RED**

```powershell
Push-Location backend; python -m pytest -q tests/integration/test_stage08_group_context_postgres.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
```

Expected: fail until all lifecycle re-read and purge transitions are implemented.

- [x] **Step 3: Apply only minimal corrections**

If a test needs a C1 mutation, route, Provider, long-lived digest, Memory write, vector index, Redis, LangGraph checkpoint or Telegram network call, stop that change and record it for C3/E/production; do not expand C2.

- [x] **Step 4: Run final C2 verification**

```powershell
Push-Location backend; python -m pytest -q tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py tests/integration/test_stage08_group_context_postgres.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
Push-Location backend; python -m compileall -q app/models/stage08_group_context.py app/runtime/stage08_group_context_contracts.py app/services/stage08_group_context.py app/services/telegram_ingestion.py; $exitCode = $LASTEXITCODE; Pop-Location; exit $exitCode
rg -n "raw_text|raw_caption|normalized_text|TelegramBot|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route|Redis|pgvector|LangGraph|MemoryItem|AgentRun" backend/app/models/stage08_group_context.py backend/app/runtime/stage08_group_context_contracts.py backend/app/services/stage08_group_context.py
git diff --check -- backend project-docs/08-implementation docs/superpowers
```

Expected: focused C2/C1 suite and compile pass; static scan has no prohibited production dependency or historical raw read. `content_fragment` is allowed only in the new model/private service path and must not appear in public DTO/log/audit functions.

### Task 6: Independent Review and C3 Handoff

**Files:**
- Create: `.superpowers/sdd/stage08-package-c-task-c2-review-package.md`
- Create: `.superpowers/sdd/stage08-package-c-task-c2-review.md`
- Modify: Package C BDD/progress ledger/evidence only after clean review

- [x] **Step 1: Perform independent task review**

Verify the actual diff against all Global Constraints, especially that the ingress exception only writes new/edited local projections, long context did not become Memory, delete language remains best-effort, and text/source carriers cannot cross serialization/persistence boundaries.

- [x] **Step 2: Re-run final verification independently**

Use the Task 5 commands, check Alembic has exactly one head, and retain only actual outputs in evidence.

- [x] **Step 3: Hand off to C3 without merging**

Record that C2 returns an internal long window plus `compression_required`; C3 must own C1/C2 composition and total budget, and E alone may invoke `ContextCompressor`. C2 pass does not mean Package C, Stage08, Provider evaluation or deployment passes.

## Self-Review

- Coverage: Task 1 captures all user-approved D1–D6 and resolves old contract contradictions; Task 2 covers schema/mapping; Task 3 covers the narrow ingress exception; Task 4 covers safe C2 selection/purge; Task 5 supplies real PostgreSQL evidence; Task 6 supplies independent closure and exact C3/E handoff.
- Scope: no task writes long-lived digest, calls an LLM, expands public API, changes C1, creates RAG/vector/Redis/LangGraph state or performs Telegram networking.
- Type consistency: public `GroupContextWindow` views contain status/count/budget/compression signal only; text/handles remain private; C3/E consume only the private internal window after their own confirmed contracts.
- Workspace safety: all tasks preserve unrelated dirty changes and do not stage or commit.

## Execution Handoff

This plan replaces the earlier short-window C2 implementation sequence after Task 1 reconciliation. Tasks 1–6 are complete and Task 6 final independent re-review is clean after the two Important findings were remediated. C2 is closed; C3 may now start, while C3 merge/global budget/renderer and Package E `ContextCompressor` remain unimplemented and separately gated.
