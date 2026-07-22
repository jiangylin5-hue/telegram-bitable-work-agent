# Stage08 Package E / E3 最终独立审查报告

## Status

- Review result: `PASS`
- Findings: `0 Critical / 0 Important / 0 Minor`
- Closure verdict: **可以关闭 E3**
- Review scope: E3-R1 与合并后的 E3-R2/R3 安全执行适配层，包括用户已确认的 `degraded` 终态最小扩展
- Review date: 2026-07-22

## 审查结论

本轮直接审阅了 E3 决策、修复计划、E 合同、BDD、实现源码和测试，而不是把既有实现报告作为通过依据。当前实现满足最终 review brief 的六项问题，没有发现阻断 E3 关闭的缺陷。

### 1. `degraded` 来源与合同一致性：PASS

- `backend/app/runtime/stage08_collaboration_contracts.py` 已将 `degraded` 一致加入 `AssistantTerminalStatus`、`CollaborationStatus` 与 terminal set。
- `_analyse_state` 对 Provider 返回值执行 exact-type/exact-field 检查，再通过 `AnalysisProviderOutcome.model_validate(...)` 重建；只有验证后的 `status="unavailable"` 进入 `degraded`。
- shape drift、伪造的非法 Pydantic shape 和 Provider runtime exception 均进入 `failed`。
- graph 的 terminal routing、status order、terminal conflict reducer 均识别 `degraded`，并在 `analyse` 后直接路由到 `finalize`，不会进入 `policy_gate`。

### 2. `degraded` 安全投影与无动作约束：PASS

- `AssistantQuerySafeView` 对 `degraded` 固定要求：`answer=None`、`citations=()`、`degradation_codes=("analysis_unavailable",)`、`draft_id=None`。
- `_finalize_state` 只构造上述固定形状；没有 private reference、Provider payload、record/draft/ticket identifier。
- graph 在 `analyse` 产生 terminal 后直接进入 `finalize`；定向测试同时断言 Gateway call count 为 0，ticket/idempotency/draft 均未生成。

### 3. 无效 Provider 输出继续 fail closed：PASS

- 非 `AnalysisProviderOutcome` 对象、额外/缺失字段、非法 `model_construct` 内容及异常都会被 `_analyse_state` 捕获并映射为 `failed`。
- `failed` 投影为空 answer/citations/draft，不把 exception 或 Provider response 带入 safe view、AgentRun 或 audit。

### 4. E3 原子执行、current-state 重验与 replay：PASS

- draft 路径仅在 Policy Gate 通过后进入 `stage08_e3_safe_execution_boundary`。
- 消费期按固定顺序锁定并重验 workspace、member、employee/grants、record、table、field、Telegram binding、business mapping 与已消费 D4 source/chunk；任一 drift 均 fail closed。
- InMemory 边界在异常时回退本边界新增的 ticket、idempotency、draft、AgentRun、audit、outbox 与 notification；SQLAlchemy 使用 `session.begin_nested()` savepoint，且不接管调用方 outer transaction。
- Gateway failure 会退出边界并回滚 ticket/idempotency/draft/internal trace；边界外只留下最小 terminal failure AgentRun/audit。
- same-key 路径先重新执行 current-state scope 重验，再以 hash-only trace、safe ticket audit、唯一 pending draft、相同 target/employee/value 证明 replay；不会再次调用 Gateway，也不通过 record-wide pending 数量推断结果。
- default-mode ticket 缺少 E3 safe provenance 时拒绝 replay；different key 使用不同 trace 并走独立执行路径。

### 5. 全 trace 脱敏：PASS

- safe ticket、Gateway、Stage06 draft adapter 与 E3 terminal 记录均使用 whitelist summary。
- terminal audit 使用 `actor_type="system"`、`actor_id="stage08_e3_safe"`、`entity_id=None`、`permission_snapshot=None`。
- 单元和 PostgreSQL 测试扫描同 trace 的全部 audit actor/entity/before/after/permission、全部 AgentRun input/output/tool/ref 与 ticket tool summary；未发现 query、answer、field/value、caller actor、record/draft/ticket UUID 或 Provider payload。
- draft 业务表仍按已确认合同保留必要的主键、外键与 `proposed_values`；这些内容没有进入 audit/API/trace safe projection。

### 6. PostgreSQL 证据与范围边界：PASS

- 集成测试使用真实 `SqlAlchemyStage06PlatformUnitOfWork` 和 loopback `pgvector/pgvector:pg17` PostgreSQL，并断言 `vector` extension 存在，不是连接型 `SELECT 1` smoke。
- 主流程实际覆盖成功 pending draft、same-key replay、Gateway savepoint rollback、mapping revoke、outer transaction rollback cleanup。
- 双会话测试使用 `pg_blocking_pids` 证明第二会话确实被相同 workspace `FOR UPDATE` 锁阻塞，释放后才能继续。
- E3 修改保持为内部 adapter；未新增 public API、schema/migration、permission model、真实 Provider、Telegram、部署、record 直接写入或 draft confirmation。
- Stage06 默认 ticket/Gateway/draft 路径仍保留原有 UUID audit 行为；safe behavior 只由不可从 JSON 构造的 factory-issued `Stage08SafeExecutionContext` 开启。

## Fresh verification

### E3 selected unit suite

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

Result:

```text
113 passed in 2.75s
```

### Stage06 default behavior regression

```powershell
python -m pytest tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage08_runtime_service.py tests/unit/test_stage08_tool_gateway.py -q
```

Result:

```text
40 passed in 3.82s
```

### Real loopback PostgreSQL

在未打印 DSN/credential 的前提下设置 `STAGE08_RAG_DATABASE_URL`，执行：

```powershell
python -m pytest tests/integration/test_stage08_collaboration_postgres.py -q
```

Result:

```text
2 passed in 5.31s
```

### Compile verification

```powershell
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/services/stage06_platform.py app/services/stage08_collaboration.py app/services/stage08_runtime.py app/runtime/stage08_tool_gateway.py app/agents/stage08_collaboration.py
```

Result: exit code `0`，无输出。

## Skipped tests / external actions

- 未运行全 backend suite；本轮按 final review brief 执行 E3 定向回归、Stage06 默认行为回归与真实 PostgreSQL 主路径。
- 未调用 OpenRouter/真实 Provider、Telegram/Bot API、部署或生产系统；这些不属于 E3 final review。
- E4 assistant query API、Package F 真实 LLM 质量评测和生产部署仍是后续 package，不能因 E3 通过而宣称完成。

## Temporary cleanup

- PostgreSQL 主流程 fixture 位于 outer transaction 并在测试末 root rollback；独立 observer 验证 workspace/ticket/idempotency/draft/AgentRun/audit 均为 0。
- lock 测试显式删除 committed synthetic workspace，并验证计数为 0。
- 本审查未创建临时脚本、外部资源、migration、API 或部署资产；保留的本地 pgvector 容器属于既有 Package D/E 测试基础设施。

## Final verdict

`0 Critical / 0 Important / 0 Minor`。E3 safe-execution remediation 与已确认的 `degraded` 合同扩展可以关闭；Package E 下一步可进入 E4，但不得把本结论扩展解释为真实 Provider、Telegram 或生产上线验收。
