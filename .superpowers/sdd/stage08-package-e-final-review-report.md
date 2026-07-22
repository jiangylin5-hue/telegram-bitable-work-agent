# Stage08 Package E 最终独立审查报告

## 结论

- 审查日期：2026-07-22
- 审查范围：Package E / E1–E4 主链路，包含私有 LangGraph 合同、C3/D4 受控读取、E3 safe-execution 草稿路径、E4 strict API 与 safe replay。
- 分级：**0 Critical / 1 Important / 0 Minor**。
- 关闭建议：**HOLD，Package E 暂不能关闭，不应进入 Package F。**
- 本轮仅新增本报告；未修改生产代码或测试，未调用真实 Provider、Telegram、部署或任何外部系统。

## Important

### I-01：生产 Coordinator 的“并行读取 / 可取消 / 超时预算”只存在于拓扑和 fake-node 测试，没有进入真实执行链

**证据**

1. 已批准的 Package E 计划要求“可并行读取、可取消”，E2 要求 C3/D4 并行读取；BDD `E-B02` 要求最多三个子图 fan-out，`E-02` 明确要求 bounded fan-out、cancel 和 timeout；E 合同的验收门槛也要求 fan-out/fan-in、budget、cancel 和 terminal mapper 正确。
2. `backend/app/agents/stage08_collaboration.py:165-205` 确实编译了三个 read node 的 fan-out/fan-in 形状；但生产 `run_stage08_collaboration` 在 `backend/app/services/stage08_collaboration.py:455-466` 把三个 read node 全部注入为同一个 `unchanged` no-op，然后在单一 `fan_in` 节点里才调用一次 `execute_collaboration_reads` 执行所有读取。
3. `execute_collaboration_reads` 在 `backend/app/services/stage08_collaboration.py:189-340` 依次执行 C3 compose/render、群压缩和 D4 search/render/safe-view；因此真实 C3/D4 I/O 是单节点串行执行，graph 的三路 fan-out 不承载任何业务读取。
4. `CollaborationBudget` 虽定义 wall `30_000ms` 和 provider `20_000ms`，实现只把 budget DTO 传入 compressor/provider；`run_stage08_collaboration` 没有 deadline、cancel token、超时执行器或执行中的 budget check。生产 service 也从不转入 `cancelled/timed_out`；这两个状态只在 finalizer 中被动映射。
5. 现有 cancel 测试 `backend/tests/unit/test_stage08_collaboration_graph.py:195-205` 通过测试专用 `cancel_at_plan=True` fake node 直接构造 terminal state，不运行生产 coordinator。`test_stage08_collaboration_postgres.py` 没有 cancel/timeout/budget 用例。所以 fresh green 不能证明这项生产合同。

**影响**

- Package E 现在能证明固定 graph 形状，但不能证明真实 C3/D4 并行、运行中取消或 wall/provider timeout。
- 任何缓慢或不遵守 budget 的 compressor/AnalysisProvider 都可以让 API 请求超过合同上限；Package F 一旦接入真实 LLM，该缺口将直接变为运行时资源和可用性问题。
- 这不会否定已验证的 E3 事务/草稿安全和 E4 replay 脱敏，但它未达到 Package E 自身的 E-02 关闭门槛。

**必需修正**

- 让生产 read nodes 真正执行受控的分支读取并由 reducer 汇总，或者经正式决策修改已批准的“并行”合同；不能保留 no-op fan-out 同时声称已实现并行读取。
- 在 Coordinator 边界实际执行 wall/provider deadline 和服务端取消，并在 provider/read/policy/draft 之前后 fail closed 检查；仅把数字放进 DTO 不算预算执行。
- 新增生产 service 级用例，证明真实分支执行、slow/blocked provider timeout、取消不进入 Policy/Gateway，并且 ticket/idempotency/draft/internal audit 无残留；不能只使用自定义 graph fake node。

## 已通过的主链路审查

1. **E1 私有合同：PASS（除 I-01 的真实执行闭环）**
   - command/state/private material 使用 process-local sealed carrier，strict safe view 会重建验证；graph 显式 `checkpointer=None`，provider shape drift fail closed。
2. **E2 scope/privacy：PASS（不含并行/超时声明）**
   - C3 group lineage 与 D4 authority/source 在消费点重验；private group/retrieval material 未进入 safe DTO 或持久化。
3. **E3 safe execution：PASS**
   - Policy Gate 在 ticket/Gateway 之前；savepoint/InMemory boundary 覆盖 current-state locks、ticket/idempotency、Gateway 和 pending draft；失败回滚、same-key safe replay、trace-wide UUID/private redaction 在源码与 PostgreSQL 主路径中一致。
4. **E4 strict API / safe replay：PASS**
   - 对外仅有 `POST /api/stage08/assistant/query`；command/authority 服务端派生；非法 body 使用 redacted 422；replay 前重验当前 member/employee/target，并从 versioned 六字段白名单投影严格重建首次 safe view。
5. **边界：PASS**
   - 未发现 Package E 新增 migration/model/global role、真实 Provider、Telegram/webhook 或部署行为；Stage06 默认 audit/Gateway 路径仍与 E3 factory-issued safe mode 分离。

## Fresh verification

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/api/test_stage08_collaboration_api.py
```

结果：`212 passed in 16.16s`。

从已有 compose 配置临时组装未输出的 loopback DSN，对 healthy `pgvector/pgvector:pg17` 执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_collaboration_postgres.py
```

结果：`2 passed in 4.94s`。测试是真实 `SqlAlchemyStage06PlatformUnitOfWork` PostgreSQL 主路径，包含 pending draft/replay、savepoint rollback、scope revoke、outer rollback cleanup 和双会话行锁证据，不是 `SELECT 1` 连通性烟测。

```powershell
python -m compileall -q app/runtime/stage08_collaboration_contracts.py app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py app/schemas/stage08_collaboration.py app/api/routes/stage08_collaboration.py
```

结果：退出码 `0`。指定 E 文件 `git diff --check` 退出码 `0`。

## 跳过项、清理和剩余风险

- 按 final-review brief 未执行 full backend suite、Stage07/UI、Package F 真实 LLM 评测、Telegram 或部署验收。
- 本地 PostgreSQL 证据只是 disposable loopback 开发证据，不代表 staging/production readiness。
- AgentRun 目前将 `provider_calls` 固定记为 `0`，而 `_analyse_state` 会调用一次 provider port；当 Package F 接入真实 Provider 时应同步修正运行计数，否则可观测性会失真。该项本轮作为 I-01 相关剩余风险记录，不另立第二个 finding。
- 测试使用 outer transaction rollback，lock 用例显式清理合成 workspace；本轮没有新建临时容器、临时脚本、外部资源或持久测试数据。

## Final verdict

Package E 的安全合同、E3 原子草稿和 E4 API/replay 主链路已有实质证据，但生产 Coordinator 尚未实现已批准的 bounded parallel/cancel/timeout。由于 final brief 规定只有 `0 Critical / 0 Important` 才能关闭，本轮结论是 **HOLD**；修复 I-01 并完成 fresh independent re-review 后再关闭 Package E。
