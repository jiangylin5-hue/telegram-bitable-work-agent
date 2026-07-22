# Stage08 Package E / E3-R2/R3 实施报告

## Status

- Status: `DONE`
- Completed scope: sealed field/value intent、safe E3 atomic boundary、current-state lock/revalidation、same-key replay、trace-wide redaction、合法 unavailable analysis → fixed degraded terminal、真实 PostgreSQL success/replay/rollback/revoke/shared-lock/cleanup。
- Contract resolution (2026-07-22): 用户已明确授权 E1 合同扩展。只有重新通过 `AnalysisProviderOutcome` 严格校验的 `status="unavailable"` 进入 `degraded`；伪造/shape drift、validation failure 和 runtime exception 继续进入 `failed`。未使用 `model_construct` 或其它 Pydantic 绕过。
- Scope boundary: 未新增 API、schema/migration、global role、Provider、Telegram、部署、record 直接写入或 draft confirmation。

## Changed files

1. `backend/app/services/stage06_platform.py`
2. `backend/app/services/stage08_collaboration.py`
3. `backend/app/runtime/stage08_collaboration_contracts.py`
4. `backend/app/agents/stage08_collaboration.py`
5. `backend/tests/unit/test_stage08_collaboration_contracts.py`
6. `backend/tests/unit/test_stage08_collaboration_service.py`
7. `backend/tests/unit/test_stage08_collaboration_graph.py`
8. `backend/tests/integration/test_stage08_collaboration_postgres.py`
9. `.superpowers/sdd/stage08-package-e-task-e3-r23-report.md`

`backend/app/services/stage08_runtime.py`、`backend/app/runtime/stage08_tool_gateway.py` 的既有 R1 实现只被复用和验证，本任务未改这些文件。共享 worktree 原有 dirty 内容未覆盖、未 stage/commit/reset/checkout/clean/push。

## What changed

### 1. Safe intent 与消费期重验

- `run_stage08_collaboration` 的 E3 draft path 现在使用 factory-issued `Stage08SafeExecutionContext`，并把 sealed `DraftIntent(field_key, value)` 精确映射为 Gateway invocation 的 `proposed_values`；不再创建 `{}` draft。
- draft 前按确定顺序锁定并重验：workspace → active member → employee → employee member grants → target record → target table → target field → Telegram binding → business mapping → consumed D4 knowledge source/chunk facts → ticket。
- 重建并比较本次 process-local `ContextPlan` 与 group scope proof；workspace/member/employee/grant/record/table/field/action、actor write permission、employee accessible view field、C1/C2/C3/D4 business/source facts任何 drift 均 fail closed。
- Gateway 仍是唯一 draft 创建入口；源 record 未直接写入，draft 仍为 `pending_confirmation`。

### 2. 原子执行边界

- `stage08_e3_safe_execution_boundary` 只服务 E3 safe path。
- InMemory 在异常时截断恢复本边界新增的 ticket、idempotency、draft、AgentRun、audit、outbox、notification side effects。
- SQLAlchemy 使用 `session.begin_nested()` savepoint；不 commit/rollback 调用方外层事务。
- Gateway exception、非 succeeded terminal 或 provenance/scope failure 会退出 savepoint并回滚内部 ticket/idempotency/draft/AgentRun/audit；边界外只写一条 whitelist terminal AgentRun 和 audit。

### 3. Same-key replay

- 每次 same-key 请求先重新执行当前读取和 scope lock/revalidation。
- 只有 `succeeded` safe ticket、hash-only trace 的唯一 `pending_confirmation` draft、相同 target/employee/proposed values、以及无 entity id 的 safe ticket-created audit 同时存在时，才返回原 draft safe view。
- replay 不再次调用 Gateway，不依赖 record-wide pending draft 数量；default-mode ticket 没有 safe draft trace/provenance，不能被此 replay 消费。

### 4. Graph terminal 与 trace redaction

- E1 固定十节点和 `checkpointer=None` 保持不变；graph topology tests fresh 通过。
- `degraded` 已一致加入 private/public terminal type、terminal transition set、graph status order 和 terminal precedence。合法 unavailable outcome 先重新经 Pydantic model validation，再进入 `degraded`；未知/伪造 shape 和 provider exception 保持 `failed`。
- degraded safe view 形状固定为 `answer=None`、`citations=()`、`draft_id=None`、`degradation_codes=("analysis_unavailable",)`，Policy Gate/Gateway 均不运行。
- terminal latency 改为 `time.monotonic()` 实测 elapsed；单元测试以 125 ms controlled clock 证明不是硬编码 0。
- terminal audit 改为 `system/stage08_e3_safe`，`permission_snapshot=None`；不再保留 caller actor id/authority metadata。
- trace scanner 覆盖本次全部 audit actor/entity/before/after/permission、全部 AgentRun input/output/tool/ref、ticket tool summary 和 outbox，而非只看最后一条。

## TDD evidence

### Initial required RED

先新增 brief 指定五个用例，再运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k "safe_draft_uses_sealed_intent or safe_gateway_failure or safe_revoke_before_gateway or safe_same_key or unavailable_analysis"
```

Output:

```text
5 failed, 16 deselected in 2.32s
```

五项失败原因均为预期：draft 值仍为 `{}`；Gateway exception 遗留 ticket/idempotency/internal audit；workspace execution lock 后 mapping revoke 仍误建 draft；same-key replay 返回 failed；unavailable 返回 failed 而非 degraded。

R1 已将 intent 从旧 `summary=` 改为 `field_key/value`，但 graph tests 尚未同步。本轮只改测试调用形状后：

```text
14 passed in 0.60s
```

### Minimal GREEN for the four implementable paths

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_service.py -k "safe_draft_uses_sealed_intent or safe_gateway_failure or safe_revoke_before_gateway or safe_same_key"
```

Fresh output after full trace redaction remediation:

```text
4 passed, 17 deselected in 1.79s
```

### Terminal audit metadata RED/GREEN

Trace scan 扩展到 audit actor metadata 后，先得到预期 RED：

```text
1 failed, 20 deselected in 1.90s
```

失败精准命中 persisted caller actor id `e2-owner`。改为 system actor/无 permission snapshot 后，上述四项 fresh GREEN：`4 passed, 17 deselected`。

### Previously unresolved RED

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

Fresh output:

```text
1 failed, 108 passed in 3.26s
```

唯一失败：`test_unavailable_analysis_is_degraded_without_gateway_or_network`，实际合法合同结果为 `failed`，期望为 brief 的 `degraded`。Gateway call count 仍为 0；默认 unavailable provider 没有 network port/call。排除该已确认合同冲突后的 fresh evidence：

```text
108 passed, 1 deselected in 2.56s
```

### User-authorized degraded contract follow-up RED/GREEN

用户授权后，先补充 degraded terminal/safe-view invariant，以及 shape drift/exception 仍 failed 的回归，再运行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py -k "degraded or unavailable_analysis or invalid_or_raising_analysis"
```

RED:

```text
2 failed, 2 passed, 74 deselected in 2.42s
```

两项预期失败分别为：contracts 不接受 `degraded`；合法 unavailable 仍返回 `failed`。同时 shape drift 与 runtime exception 两项已保持 `failed`，证明测试没有放宽无效 provider 路径；GREEN 阶段再加入 exact-type `model_construct` forged outcome，验证它也保持 `failed`。

最小合同/映射实现后的 focused GREEN：

```text
5 passed, 74 deselected in 2.00s
```

最终 R23 selected unit fresh evidence：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py

113 passed in 2.76s
```

## Real PostgreSQL evidence

### Provenance

- Database: Package D retained disposable `pgvector/pgvector:pg17` container。
- Address class: loopback only；测试主动拒绝非 loopback host。
- `vector` extension 在主流程测试中真实查询并断言存在。
- Alembic source/current head（未输出 DSN/credential）：

```text
20260720_0032 (head)
20260720_0032 (head)
```

### RED/GREEN

首轮 PostgreSQL run：

```text
1 failed, 1 passed
```

失败属于 test fixture：用了数据库 check constraint 不允许的 mapping status `revoked`；真实 schema 只允许 `active/inactive`。最小改为已支持的 `inactive` 后，没有生产代码事务修复，fresh output：

```powershell
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py

2 passed in 5.06s
```

连接串/credential 未打印。

degraded 合同补丁后的真实本地 PostgreSQL fresh regression：

```text
2 passed in 5.29s
```

### Success, replay, rollback, revoke

真实 `SqlAlchemyStage06PlatformUnitOfWork` + outer transaction + E3 nested savepoint 证明：

- success: 1 个 `pending_confirmation` draft，`proposed_values == {"title": "E3 controlled"}`，source record values 不变；
- same-key replay: 返回相同 safe view/draft id，数据库只有 1 ticket、1 idempotency、1 draft；
- Gateway exception: savepoint 后 ticket/idempotency/draft 数量均不增加，只增加 1 terminal AgentRun + 1 terminal audit；随后同一 outer transaction 继续执行 revoke 场景，证明没有调用 caller-level rollback；
- scope revoke: analysis 后把已读取 mapping 切为合法 terminal `inactive`，结果 `denied`，无新增 ticket/idempotency/draft；
- 四条 trace 在 root rollback 前的精确计数：

```text
tickets=1
idempotency=1
drafts=1
agent_runs=5
audits=9
```

全部 trace projection 扫描不含 query、answer、actor、field/value、record/draft/ticket UUID 或 provider payload。

### Shared lock evidence

- Session A 用真实 UoW `SELECT ... FOR UPDATE` 锁 workspace。
- Session B 对同一 workspace 发起相同 lock 并保持未完成。
- observer 使用 `pg_blocking_pids(blocked_pid)`，真实返回 Session A backend pid；断言 future 在 A release 前未完成。
- A rollback 后 B 获得锁并安全 rollback。

### Cleanup

- 主流程所有 synthetic fixture/side effect 位于 caller outer transaction；测试末尾 root rollback。
- 独立 observer 对本次 workspace/traces 验证：`tickets=0`、`idempotency=0`、`drafts=0`、`agent_runs=0`、`audits=0`，workspace row 也为 0。
- lock test 显式删除 1 个 committed synthetic workspace，随后 count 为 0。
- 未创建临时脚本、文件或外部资源。Package D retained disposable container 不是本任务创建，按 Package D/E package owner 的既有 cleanup gate 保留运行；本任务未 down/删除 volume。

## Compile verification

```powershell
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/services/stage06_platform.py app/services/stage08_collaboration.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/agents/stage08_collaboration.py
```

Fresh result: exit code 0, no compile output。

## External calls

- Real Provider/OpenRouter: none。
- HTTP/external network: none；只有已授权 loopback disposable PostgreSQL。
- Telegram/Bot API: none。
- Deployment: none。
- Record direct write/draft confirmation: none。

## Skipped / out of scope

1. 未运行真实 Provider、Telegram、API E4、deployment 或生产数据库测试；均不在本轮授权范围。

## Remaining E4 / Package F risks

1. E4 assistant query public API、strict request/response/error corpus 和 API-level permission/idempotency evidence 尚未实现。
2. Package F 真实 LLM/OpenRouter quality、provider timeout/retry/cost evidence 尚未实现；E3 的 provider 仍是 deterministic fake/unavailable port。
3. 生产 deployment、remote staging、Telegram entry smoke 均仍是后续独立 gate。
4. 本报告关闭 E3 R2/R3 implementation concern；Package E 完成仍取决于 E4 与后续独立验收，不能据此宣称整包完成。

## Git / temporary cleanup

- 未执行 stage、commit、reset、checkout、clean、push。
- 未删除或改写共享 worktree 的其它 dirty 内容。
- 本任务测试数据已按上述 PostgreSQL cleanup evidence 清零。
