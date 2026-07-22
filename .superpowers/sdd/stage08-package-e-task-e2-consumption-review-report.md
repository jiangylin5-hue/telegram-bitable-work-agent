# Stage08 Package E / E2 消费期修复后的独立复审报告

## 结论

- 审查结论：**建议关闭 E2**。
- 严重度：**0 Critical / 0 Important / 0 Minor**。
- 本次结论仅覆盖 E2 的 C3/D4 受控读取、群压缩与降级边界；不宣称 E3、E4、assistant API、真实 LLM/Provider、Telegram、部署或整个 Package E 已完成。

## 审查范围与限制

本次是对消费期修复后的 fresh independent review。未修改生产代码、测试、既有文档、数据库、Docker 或外部系统；唯一新增文件为本报告。审查对象为：

- `backend/app/services/stage08_collaboration.py`
- `backend/app/services/stage08_context_composition.py`
- `backend/app/services/stage08_retrieval_provider.py`
- 对应的 E2 focused unit / disposable pgvector integration corpus。

共享 worktree 本身已有大量无关未提交改动，本报告没有把它们视为 E2 变更，也没有执行 git 写操作。

## 独立复现实测

在 `backend` 目录执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

结果：`137 passed in 3.64s`。

```powershell
python -m compileall -q app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py
```

结果：通过。

确认既有 loopback disposable pgvector 17 容器为 `healthy` 后，仅在本进程临时设置既有测试连接变量并执行：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
```

结果：`17 passed in 10.72s`。该测试使用独立连接内的 transaction rollback；未输出或保留连接串，未访问真实 Provider、HTTP、Telegram、Redis、Milvus 或生产环境。

## 消费期 current-state 审查

### 1. group proof 在 D4 消费前重新验证

`stage08_collaboration.py:70-76` 的 invocation-private `_GroupScopeProof` 固定保存 `binding_id`、`mapping_id`、`mapping_version` 与 customer/project pair。`_derive_business_scope_ids()`（`419-472`）只在唯一 active member、唯一 active `chat_user` binding 和唯一 active mapping 成立时生成该 proof；有 target 时，target 也必须是当前 mapping 的 customer 或 project。

在 D4 factory/search 之前，`execute_collaboration_reads()` 的 `263-269` 调用 `_group_scope_proof_is_current()`；该函数会重新走同一派生链，并要求五项 proof 精确相等。因而 binding/mapping 的替换、停用、歧义、mapping version 漂移、customer/project pair 漂移，或 target 不再匹配，都会在 D4 消费点前失败，进入固定 `retrieval_unavailable` 分支，不调用 D4。

压缩阶段修改 mapping version 的回归用例也实际验证 `search` 调用数为零。C3 一侧的 `stage08_group_context.py` 还会在建窗口、materialize 和 purge 前重验 member/binding/mapping、version 和业务关系；pending renderer 会重建窗口并比较 projection lineage。两层检查没有发现 stale group scope 被交给 D4 的路径。

### 2. 无群 proof、无 target 的正常 C1 路径

没有 target 且当前不存在可用 group proof 时，派生函数返回全空 proof，而不是抛出 target-denied。随后 C1 可以正常组成受限上下文；pgvector 集成用例覆盖了没有 group mapping 的正常 command，结果为 `internal_evidence`、`read_child_count == 2`。只有 target 被声明却不能由唯一 current mapping 证明时才 fail closed，因此正常 C1 路径没有被误报为权限拒绝。

### 3. compressor 输入、调用、DTO shape 与 digest 漂移

`stage08_collaboration.py:158-182` 将 private provider input 的构造、`compress()` 调用、`CompressionOutcome` 的 exact-type 检查、严格 Pydantic 重建和 digest 的 C3 current-state 验证放在同一个 `try` 内。异常、超时式异常、任意非 `CompressionOutcome` 对象、属性读取异常、`model_construct` 构造的无效 digest，以及 C3 lineage 漂移都会被统一转换为：

- 不记录 digest；
- `group_status="compression_unavailable"`；
- 固定 `compression_unavailable` degradation；
- 仅保留仍然合法的非群 C1 材料。

focused corpus 对 `object()`、属性访问异常对象和 forged invalid digest 都验证了无异常泄露、无 group material 泄露及 C1 保留。`CompressionOutcome` / digest 私有 carrier 也拒绝 JSON、pickle 和 repr 读取。

### 4. general advice 与 D4 例外回归

`general_advice` 在 `260-261` 明确绕过 D4；对应 recording provider 用例确认 `search` 从不调用，并得到限定的 `general_advice_only`。`business_fact` / `mixed` 的 D4 branch 把 authority build、search、private evidence render 和 safe-view projection 放在同一异常边界（`262-293`）；任一异常都会清空 evidence 与 citation count，只给出固定降级码，同时保留已经合法获得的 C3 非敏感状态。

现有 D4 provider 自身仍在 authority build、search、result render 与 safe citation 前重验 current authority、source/chunk/Memory 生命周期；137 个 focused tests 和 17 个 pgvector tests 均未显示修复回归。

### 5. private data 与副作用

静态扫描这三个 E2 生产模块，未发现 HTTP/OpenRouter、Telegram、Redis、Milvus、Tool Gateway、API route、AgentRun、audit、outbox、draft 或写入型 UoW 调用。唯一 Telegram 关联为受控 UoW 的 binding 读取。`Stage08CollaborationReadResult` 与 safe view 只公开状态、计数和固定 degradation code；query、authority、UUID、群正文、digest、D4 private evidence、provider exception 均在 opaque carrier 内，无法通过 repr/JSON/pickle 进入 safe view。

unit 与 integration 断言确认读取流程不新增 audit、outbox、idempotency、AgentRun、draft 或 notification 记录。pgvector 仅作为已启动的本地 disposable 容器中的 rollback 集成证据，不构成部署或持久化写入。

## 分级问题

- Critical：无。
- Important：无。
- Minor：无。

## E2 关闭后的边界

E2 现在可作为 E3 的私有读聚合输入，但没有由此获得分析、Policy Gate、draft/ticket、持久化审计或 HTTP API 能力。真实 LLM/embedding provider 仍由后续 Package F 的独立实测与质量评估负责。

## 临时清理

未创建测试源文件或持久化数据。集成测试结束时关闭 session/connection/engine 并 rollback；既有 disposable 容器保持原状。本报告是唯一新增审查产物。
