# Stage08 Package E / E2 修复后独立复审报告

## 结论

- 审查结论：**不建议关闭 E2**。
- 严重度：**0 Critical / 2 Important / 0 Minor**。
- 本轮已确认前次两项修复有效：带 `target_record_id` 的撤销、歧义、inactive 或无 mapping 情形会在读取前 fail closed；`search`、`render_private_evidence`、`safe_view` 任一 D4 异常都会清空 retrieval branch，映射为固定 `retrieval_unavailable`，并保留已获准的 C3 材料。
- 但仍有两个未满足的 E2 已批准边界：group binding/mapping 在 plan 后漂移时 D4 没有在消费点重新验证；以及压缩器返回 shape drift 时异常会穿透 E2，而非降级为无群材料。两项均涉及运行期权限/私有上下文安全边界，必须修复并再次独立复审。

## 独立复现实测

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

结果：`133 passed in 3.58s`。

```powershell
python -m compileall -q app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py
```

结果：通过。

既有 loopback disposable pgvector 17 容器为 healthy 后，仅在本次进程环境设置既有测试连接变量并执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
```

结果：`17 passed in 9.27s`。该套件使用事务 rollback；没有打印或保存连接串。

另进行两项不落库的独立反例：

1. 以 49 条受控群投影触发 pending compression；测试 compressor 在 C3 已完成当前状态校验后将 mapping 改为 `inactive`。随后 E2 仍调用 D4，得到 `mapping_inactive_before_d4=True`、safe result `internal_evidence`、`read_child_count=2`。该反例使用内存 UoW，无数据库或外部系统写入。
2. 同样触发 pending compression，但 compressor 返回普通 `object()` 作为 shape drift。`execute_collaboration_reads` 抛出 `AttributeError`，而不是返回固定 `compression_unavailable` 安全结果。该反例也仅使用内存 UoW。

静态复查 E2 三个生产模块未发现 HTTP/OpenRouter/Redis/Milvus/Tool Gateway/API route/AgentRun/audit/outbox 写入依赖；唯一 Telegram 相关调用是受控 UoW 的 `list_telegram_bindings()` 读取。`git diff --check` 对受审文件通过。

## 已确认符合的部分

- `backend/app/services/stage08_collaboration.py:369-405` 现在只在唯一 current active member、chat-user binding、active mapping 存在且 target 为空或匹配该 mapping 时返回完整 customer/project pair；无 mapping 或 target 不匹配会进入固定 fail-closed result，不再将 target 单独升级为 scope。
- `backend/app/services/stage08_collaboration.py:242-299` 将 D4 authority build、`search`、`render_private_evidence` 和 `safe_view` 置于同一局部异常边界。异常时 evidence/citation count 均清零，safe result 不携带 provider exception；已存在的 C3 evidence 仍可返回。
- focused tests 覆盖 revoked/ambiguous/inactive binding 的 target、以及 `search`、render、safe-view 三个 D4 注入式异常路径；safe JSON/repr 没有测试 secret，且无 audit/outbox/idempotency 等持久副作用。
- C3 的 opaque compression material/digest 仍拒绝构造、JSON、pickle 和 repr 泄露；有效 digest 仍会在消费前重建 window、mapping 和 projection lineage。没有新增 API、schema/migration、Tool Gateway/draft、真实 Provider、Telegram、Redis 或 Milvus 调用。

## Important

### I-01：group binding/mapping 在 plan 后撤权，D4 仍使用已过期 business scope

`backend/app/services/stage08_collaboration.py:141-167` 在 C3/压缩期间取得并重验 group mapping；随后 `:245-259` 直接将最初 `plan.business_scope` 传给 `Stage08RetrievalAuthorityFactory.build`/D4，没有再验证该 scope 所依赖的 current active chat-user binding 与 group-business mapping。

独立反例证明：compressor 将 mapping 改为 `inactive` 后，C3 正确转为 `compression_unavailable`，但 D4 仍被调用。当前 local fixture 未返回检索命中，不能把这一点误报为实际 evidence 泄露；不过 D4 调用仍携带先前由 group mapping 派生的 customer/project scope，已经违反已批准计划的“所有 read 路径都在消费期重验 group binding”和设计中“最终权限取 caller、employee、群绑定、业务关系与 source lifecycle 交集”的约束。匹配源存在时，该路径可能读取刚撤销群绑定所确定的 scoped RAG material。

建议修复：在每次 D4 authority build/consume 前，以内部服务重新验证唯一 active member、chat-user binding 和 group-business mapping，并确认其 customer/project pair 与 plan 完全相同；任一漂移仅将 retrieval branch 标记为固定 unavailable/degraded，不调用或不消费 D4 evidence。补一个有可命中 D4 source 的 PostgreSQL rollback 用例：mapping/binding 在 C3 后撤权时 `retrieval_citation_count=0`、无 private evidence、无 audit/outbox/idempotency 写入。

### I-02：压缩器 shape drift 会抛出异常，未映射为固定安全降级

`backend/app/services/stage08_collaboration.py:153-159` 仅捕获 `compress()` 的调用异常；`compression.status`、`compression.digest` 与随后 digest 验证发生在 `try` 外。符合 `ContextCompressor` protocol 但返回未知对象的 adapter 会在 `:161-166` 抛出 `AttributeError`。

这违背 E2 简报的“compressor exception、timeout、shape drift 或 unavailable 都映射为 no-group degradation”和 E-B02 的“任一 read failure 只产生标签化 omission/degradation”。异常没有包含私有文本，但会绕开 E2 safe-result/terminal 语义，也会令 E3/E4 接到未脱敏的失败路径。

建议修复：将 compressor 调用、严格 `CompressionOutcome` 型别/shape 校验及 digest 当前状态校验纳入同一局部 fail-closed boundary。任何异常、伪造对象、invalid outcome 或 validation failure 都应清空 compression material、记录 `compression_unavailable`，并继续让合法 C1/C3 非群材料与 D4 分支按原规则完成。新增 malformed object、异常属性访问和 invalid digest 三个负例，断言无异常、无 digest 持久化/泄露、其他合法材料仍可返回。

## 复审门槛

修复后至少重跑本报告的 133 focused tests、compileall 和 disposable pgvector 17 integration tests，并由新的 fresh independent reviewer 额外验证：

1. active mapping/binding 在 C3 后撤权时，D4 不会读取或消费以该 mapping 派生的 scope；
2. compressor 的异常、timeout、invalid DTO、shape drift 和 digest drift 全部映射为固定安全 degradation；
3. target fail-closed 与 D4 exception branch 既有修复不回归；
4. C3/D4 私有材料、query、UUID、authority、provider error 仍不进入 safe view、持久化 sink、日志或外部系统。

本报告不宣称 E2、E3/E4、Package E、真实 LLM、API、生产部署或 Telegram 已完成。
