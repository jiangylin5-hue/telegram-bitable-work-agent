# Stage08 Package C3 Context Composition — 本地 PostgreSQL 证据

## Status

- Evidence status: `Task 4 verified; Task 5 independent review pending`
- Scope: 已批准的 C3 私有 Context composition/renderer，在 disposable local PostgreSQL 上对 C1 与 C2 当前状态重读的真实证据。
- Date: 2026-07-20
- Database: 仅使用 `STAGE06_LOCAL_DATABASE_URL`；每次命令后恢复调用前的 `DATABASE_URL`。不接触默认 orphaned 数据库、生产数据库或外部系统。

## 已验证行为

测试文件为 `backend/tests/integration/test_stage08_context_composition_postgres.py`，使用既有 `stage06_postgres` disposable fixture。每个用例自行 `rollback()` 并 `close()` session。

1. 未漂移的 direct composite 使用当前 C1 evidence 在前、授权 D6 group fragment 在后，且 fragment 顺序确定。
2. C1 的 customer/project relation（同时带来 record version）或 field visibility 漂移后，不再输出旧 business evidence；relation 漂移时也不输出旧 group body。
3. C1 Memory 的 lifecycle、source version、scope 三种漂移分别会移除旧 `confirmed_memory` evidence；C2 仍当前时可继续输出其授权 group fragment。
4. C2 active mapping、business relation、source chat provenance、retention expiry、authorised purge 任一漂移后，旧 direct composite 绝不输出旧 group fragment。若 C1 仍当前，则仅保留 fresh C1 renderer 输出；这是 C3 design §4 step 4、step 83 和状态表所规定的 direct-path 行为。
5. 49 条 × 500 characters = 24,500 characters 的 C2 high window 进入 `group_compression_pending`；发生 group provenance 漂移后 renderer 返回 `None`，不会 materialize、summarize 或渲染 group body，也不会在 safe view/repr 中泄漏它。

## 审计补救：10 项 RED 与 12 项最终模块的时间线

独立复审指出，旧版本将首次 `7 passed, 3 failed` 与最终 `12 passed`
相邻记载，却没有解释测试数量变化。本节已纠正该歧义：首次 RED
不是最终 12 项的 complete corpus，不能以它声称覆盖后来补入的两个
Memory case。

首次 untracked 测试文件快照没有保留为独立 artifact；因此可审计依据
仅限当时 runner 的 `7 + 3 = 10` 输出、其 failure stack 中的旧 Memory
测试名、当前 collect-only 输出和下面明确记录的 coverage change。

| 阶段 | 收集数 | Actual | 说明 |
| --- | ---: | --- | --- |
| T0 | 10 | `7 passed, 3 failed in 17.69s` | 初始 RED。 |
| T1 | 10 | `10 passed in 15.26s` | 仅修复不合法 fixture。 |
| T2 | 12 | targeted `3 passed in 6.31s`; module `12 passed in 20.03s` | 将单一 Memory lifecycle case 扩展为 lifecycle/source/scope。 |
| T3 | 12 | C3 unit `63 passed in 1.50s`; module `12 passed in 17.29s`; focused `211 passed in 48.59s` | 本次补救后的新鲜复跑。 |

### T0 的精确 10 项

1. `test_composition_postgres_direct_render_is_current_and_c1_first`；
2. C1 `record_relation`；
3. C1 `field_visibility`；
4. 当时唯一的 `test_composition_postgres_rereads_memory_lifecycle_before_render`；
5. C2 `mapping`；6. C2 `relation`；7. C2 `provenance`；8. C2 `retention`；9. C2 `purge`；
10. `test_composition_postgres_pending_group_drift_fails_closed`。

T0 的三个 failure 是第 4 项和 C2 的 `retention`/`purge`。它们均在
C3 renderer assertion 之前失败：Memory payload 不等于当前 source field，
或 retention time 等于 event time 而违反 PostgreSQL
`retention_after_event` constraint。

T1 令 Memory payload 等于真实 `title`，并将 C2 projection 的 event
设置为到期前一分钟；原 10 项随即全绿。T2 将上述单一 lifecycle 测试
改成当前 `lifecycle`、`source`、`scope` 三参数，特意新增两个 case，
以满足 Task 4 对 Memory 三类 drift 的独立覆盖要求；这不表示有
production defect。

当前命令 `python -m pytest --collect-only -q
tests/integration/test_stage08_context_composition_postgres.py` 的实际输出为
`12 tests collected in 2.21s`，其 node IDs 为：

```text
direct_render_is_current_and_c1_first
rereads_c1_business_state_before_render[record_relation]
rereads_c1_business_state_before_render[field_visibility]
rereads_memory_state_before_render[lifecycle]
rereads_memory_state_before_render[source]
rereads_memory_state_before_render[scope]
never_renders_group_after_c2_drift[mapping]
never_renders_group_after_c2_drift[relation]
never_renders_group_after_c2_drift[provenance]
never_renders_group_after_c2_drift[retention]
never_renders_group_after_c2_drift[purge]
pending_group_drift_fails_closed
```

## RED → GREEN 记录（已限定口径）

首次把新集成用例接入真实 PostgreSQL 时，10 项 collection 的结果为
`7 passed, 3 failed in 17.69s`。三个失败都发生在新测试的 fixture
约束：Memory payload 与 source field 不一致，或 retention time 等于
event time 而被 PostgreSQL `retention_after_event` constraint 拒绝。它们
没有进入 C3 renderer，故不是 C3/C1/C2 production defect，也不是最终
12 项完整 RED corpus 的证据。

将 fixture 调整为合法 C1 source value 与 `event_at < retention_expires_at`
后，原 10 项结果为 `10 passed in 15.26s`。随后增加 source/scope 两个
Memory drift case，最终模块结果为 `12 passed in 20.03s`；没有改动 C3
production source。这同时证明 retention/purge 情况下 C3 会保留 fresh C1、
但不保留 stale group body。

## 最终命令与结果

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

Actual:

- Alembic: `20260720_0031 (head)`。
- Historical C1/C2/C3 focused regression: `211 passed in 51.97s`。
- 补救后新鲜复跑：C3 contracts/service `63 passed in 1.50s`；当前 12 项 PostgreSQL
  模块 `12 passed in 17.29s`；完整 C1/C2/C3 focused regression
  `211 passed in 48.59s`。
- C3 contracts/service `compileall`: exit `0`。
- raw Message、Telegram/network、provider/API、Redis/vector/LangGraph、Memory persistence、audit/outbox、`ContextCompressor`、digest 的 C3 production-source scan：zero matches。
- `git diff --check -- backend project-docs/08-implementation docs/superpowers`: exit `0`；只有已存在 dirty worktree 的 LF/CRLF warning，无 whitespace error。

## 边界与遗留风险

- 没有 Telegram、OpenRouter、HTTP、部署、生产数据库或真实外部写入。
- 没有 schema、migration、API、permission、C1/C2 持久化或 C3 production service 改动。
- 这是 local disposable PostgreSQL 证据，不等于 staging/production readiness。
- 必须完成 Task 5 independent review，才能将 C3 由 task-level verified 提升为包级结论；Package E/F、真实 LLM 评测与部署仍未开始。
