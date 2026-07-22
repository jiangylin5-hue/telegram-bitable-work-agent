# Stage08 Package E / E2 实施报告

## Status

- Task：`E2 Controlled C3/D4 reads and process-local group compression`
- Current Progress：任务级实现与本地回归已完成，等待 fresh independent review；本报告不关闭 E2、Package E 或 Stage08。
- Scope：仅实现 C3/D4 受控读取、短命群压缩材料与安全降级；不包含 E3 的 analysis/policy/draft，也不包含 E4 API。

## 改动

- `app/services/stage08_context_composition.py`
  - 新增 `prepare_stage08_group_compression_material`：仅对 `group_compression_pending` composite 进行消费期重读、authority/window/fragment lineage 校验后，生成不可 JSON/pickle、`repr` 不含正文的 process-local material。
  - 新增 `validate_stage08_group_compression_digest`：digest 返回后再次重建并核对群窗口；mapping 版本、成员、绑定、投影或来源漂移时拒绝 digest。
  - C3 不持久化 digest，不改变既有公开 `CompositeContextView`。
- `app/services/stage08_collaboration.py`
  - 新增内部 `execute_collaboration_reads`，从 sealed command、当前 actor、digital employee 访问范围与当前 group binding 推导 C1/C3 和 D4 读取范围。
  - 固定最多两个业务 read branch（C3 composite 与 D4 retrieval）；仅当 command intent 是 `general_advice` 且没有业务材料时才增加第三个 general-advice branch。
  - pending 群材料只经 `ContextCompressor` 的 sealed provider input 传递；默认 `UnavailableContextCompressor` 导致 `compression_unavailable`，保留合法 C1 material、绝不保存群摘要。
  - D4 继续经 authority/search/render_private_evidence 的消费期 revalidation；安全 view 只有计数、固定状态与 degradation code。
  - 返回 opaque `Stage08CollaborationReadResult`；query、正文、UUID、scope、score、authority 与私有 evidence 不进入 repr/JSON/public safe view。
- 测试
  - C3 pending handoff/lineage drift 用例。
  - E2 unit：有界读取、actor mismatch fail-closed、无持久副作用、pending compressor unavailable、compressor 返回后 mapping revoke。
  - E2 PostgreSQL：当前 member scope 在执行前撤销后立即降级，audit/outbox/idempotency 计数不增加。

## RED / GREEN 证据

1. C3 handoff RED：新增 import 和用例后，`test_stage08_context_composition_service.py` 收集失败，原因是 `prepare_stage08_group_compression_material` 尚不存在；这是预期的契约缺失。
2. C3 首次 GREEN 发现既有静态测试仍把字符串 `digest` 完全禁止；E2 已批准的 C3-only short-lived digest handoff 与旧断言冲突，因此最小调整为保留 Provider/LLM/network/persistence 禁止项、移除对所有 `digest` 字样的禁止。调整后 C3：`39 passed`。
3. E2 service 首次 RED：`3 failed`，原因是测试 fixture 的 view version 仍为 0，使现有 C1 contract 正确拒绝 source version。将 fixture 修正为现有 C3 同样的 `version=1` 后，E2 service 初次 GREEN 为 `3 passed`；随后补 actor mismatch 负例，当前为 `4 passed`。
4. 聚焦 unit GREEN：

```text
127 passed in 3.05s
tests/unit/test_stage08_context_composition_service.py
tests/unit/test_stage08_retrieval_provider.py
tests/unit/test_stage08_collaboration_contracts.py
tests/unit/test_stage08_collaboration_graph.py
tests/unit/test_stage08_collaboration_service.py
```

5. 专用 disposable pgvector PostgreSQL GREEN：容器健康、loopback-only；`17 passed in 8.28s`，包含新增 E2 member revoke current-state case。测试事务回滚；未打印或保存 DSN。
6. `compileall` 通过。已对 tracked 修改执行限定 `git diff --check`，无 whitespace 报告；新增未跟踪模块由 `compileall` 与 pytest 覆盖。静态扫描未发现 HTTP、OpenRouter、Telegram、Redis、Milvus、Tool Gateway 或 API route 依赖；service 对既有 `Stage06PlatformUnitOfWork` 的引用仅是受控 service boundary，不是 raw SQL/ORM bypass。

## 不做的事情

- 未新增 model、migration、UoW interface、global role、API schema/route、Docker、Redis、Milvus 或配置。
- 未调用真实 compressor、LLM、embedding HTTP、OpenRouter、Telegram、webhook 或部署。
- 未写 `AgentRun`、audit、outbox、idempotency、draft 或业务 record。
- 未把群原文、群摘要、query 或 D4 private evidence 放入 checkpoint、数据库、日志或 DTO。

## 剩余风险与下一门槛

- E2 尚需 fresh independent review，尤其检查 process-local compression material、current-state revoke、scope derivation 和 E1 reducer state 的边界。
- E2 的 LangGraph topology 已在 E1 验证为固定 3-way fan-out；本任务的 service 使用相同稳定 branch 顺序完成真实 C3/D4 读取，但 E3 才把其接入完整 analysis/policy terminal run。
- E3/E4、严格 query API、AgentRun/audit 记录、ticket/draft、真实 Provider 和生产部署均未完成，不能由本任务证据替代。

## 清理

- PostgreSQL 用例采用单事务 rollback；没有留下 knowledge source/chunk/outbox/idempotency/audit 或外部 artifact。
