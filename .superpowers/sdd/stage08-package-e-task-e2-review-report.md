# Stage08 Package E / E2 独立复审报告

## 结论

- 审查结论：**不建议关闭 E2**。
- 严重度：**0 Critical / 2 Important / 0 Minor**。
- 依据：C3 的短命 opaque handoff、D4 既有受控检索以及本地 disposable pgvector 回归均有正向证据；但 E2 当前仍会把未由 active group binding/mapping 证明的 `target_record_id` 升格为有效 business scope，且 D4 单分支异常会直接逃逸，未履行“只降级该分支并保留其余合法材料”的既定合同。两项都必须先修复并复审。

## 独立复现实测

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

结果：`127 passed in 2.93s`。

```powershell
python -m compileall -q app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py
```

结果：通过。

在既有 loopback disposable pgvector 环境中，仅为该测试进程提供既有测试连接配置后执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
```

结果：`17 passed in 10.09s`。这包含 E2 的 PostgreSQL active-member 撤权回读用例；用例在事务内回滚。审查没有打印或保存 DSN。

另以不落库的 in-memory fixture 做了两项独立反例复现：

1. 将唯一 `Stage08GroupBusinessContextBinding` 改为 `revoked` 后，构造带该项目 `target_record_id` 的 sealed command，`execute_collaboration_reads(...)` 仍返回 `{"status":"internal_evidence","read_child_count":2,"retrieval_citation_count":0,"group_status":"unavailable","degradation_codes":["no_evidence"]}`。
2. 注入一个继承 `PostgresRetrievalProvider`、其 `search` 抛出 `RuntimeError("simulated_retrieval_outage")` 的 test double；调用没有生成安全降级结果，而是直接抛出该 `RuntimeError`。

上述两次复现均只使用进程内 `InMemoryStage06PlatformUnitOfWork`，没有产生数据库、Docker 或外部系统写入。

## 已确认符合的部分

- `prepare_stage08_group_compression_material` 仅接受 `group_compression_pending` composite，在 materialize 前后重建 C1 pack、group authority/window，并校验 mapping、projection lineage；carrier 的 `repr` 为 opaque，JSON/pickle 路径拒绝。
- `validate_stage08_group_compression_digest` 会在 compressor 返回后重新 materialize 同一 pending window，mapping version/projection 发生漂移时拒绝 digest。现有单测覆盖 mapping version 漂移与 compressor unavailable。
- E2 返回的 `Stage08CollaborationReadResult` 只提供 count/status/degradation 的 safe view；复核中 query、群正文、digest、D4 evidence、UUID、field、score、authority 都未出现在其 `repr` 或 safe JSON。
- D4 的 `PostgresRetrievalProvider` 仍在 search、private-evidence render 和 safe-view 消费点重验 authority/source/chunk；pgvector 集成回归通过，且现有 member revoke 用例检查 audit/outbox/idempotency 计数未增加。
- 静态检查 E2 三个生产模块及 E1 contracts 未发现 HTTP/OpenRouter/Redis/Milvus/Tool Gateway/API route/AgentRun/audit/outbox/logging 依赖。唯一 `telegram` 命中是受控 UoW 的 `list_telegram_bindings()` 读取，用来派生当前 binding，并非 Telegram 客户端调用。
- E1 十节点拓扑仍使用 `checkpointer=None`；E2 没有引入 schema、migration、route、真实 Provider、Telegram、Redis、Docker 或外部写入。

## Important

### I-01：撤销或缺失 group mapping 后，`target_record_id` 被错误升格为有效 project scope

`backend/app/services/stage08_collaboration.py:357-388` 的 `_derive_business_scope_ids` 在没有唯一 active member/binding/mapping，或 target 不匹配 mapping 时，回退为：

```python
return None, snapshot.target_record_id
```

这使 sealed command 中的 target 直接成为 `ContextPlanningRequest.project_record_id`，再经 C1/D4 的 normal record resolver 读取对应项目。实测表明 mapping 已撤销时仍可得到 `internal_evidence`。这违背已批准 E 合同的两条边界：空值、歧义、撤权和 relation drift 必须 fail closed；`target_record_id` 只是待验证资源选择，不能构成 effective customer/project/group/retrieval scope。

影响：在 E4 把该 service 暴露为 query API 前，调用路径将能以 target 把一个并未由 active group context 证明的业务对象注入 C1/D4 scope。即使当前 record resolver 仍会做一般的 employee/actor 可见性检查，这仍是绑定上下文与业务 scope 的合同绕过。

建议修复：E2 只能在恰好一个 current active member、`chat_user` binding 与 group-business mapping 存在且 target 为 `None` 或匹配该 mapping 时，返回 mapping 的完整 customer/project pair。否则不得把 target 放入任何 effective business scope（返回 `(None, None)` 或进入明确的无 group-context 降级）；target 的对象类型、可见性及 action 语义留给 E3/E4 的专门 revalidation，不能在此替代 binding 证明。补充 unit 和 PostgreSQL revoke/ambiguous/no-binding target cases，断言 target 不会产生 scoped C1/D4 material。

### I-02：D4 读取异常会穿透 E2，未降级为单分支 failure

`backend/app/services/stage08_collaboration.py:242-287` 对 C3 compressor 的异常有局部降级，但 `retrieval_provider.search`、`render_private_evidence` 和 `safe_view` 没有受控异常边界。独立注入一个失败的 `PostgresRetrievalProvider` 后，`RuntimeError` 直接从 `execute_collaboration_reads` 抛出，C3 已获得的合法材料也不会形成 E2 的 safe result。

这不满足 E2 简报和 BDD 的“任一 read failure 只产生标签化 omission/degradation、保留其他合法材料”。未来 API 还会得到未经过 E2 safe mapping 的异常路径。

建议修复：将整个 D4 consume sequence 包在只映射固定 `retrieval_unavailable` 的异常边界内；异常时不要保留半成品 private evidence、provider error 或 exception text，只记录 retrieval branch 的 `unavailable` outcome，并让 C3/general-advice 分支继续按既有规则决定结果。为 `search`、render、safe-view 各自异常补 unit tests，并断言 safe result/repr/persistent sinks 均无原始异常或 private material。

## 复审门槛

修复后至少重跑：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py
```

并由新的审查轮独立验证：revoke/no-binding/ambiguous target 不扩大 scope；D4 异常只降级 retrieval 分支；C3、D4、safe view、audit/outbox/idempotency 均没有 private material 或异常细节泄露。当前 E3、E4、真实 LLM、API、draft、生产部署和 Telegram 均不在本报告完成范围内。
