# Stage08 Package E / E2 受控 C3/D4 读取与 process-local compression 简报

## 目标

在已经关闭的 E1 private graph contract/topology 上，实现**仅内部可调用**的 `execute_collaboration_reads(uow, command, actor, deps, now)`：它从 server-side sealed command 派生当前 actor/employee/view/business scope，最多并行（或以确定性等效 fan-out）读取 C3 composite、D4 retrieval 和 general-advice marker；所有私有材料仅在当前调用中进入 E1 sealed carrier。若群窗口需要压缩，只允许 Package E 通过 C3 的内部 opaque handoff 把当前 material 交给注入的 `ContextCompressor`，并立即在同一调用重新验证 bounded digest；默认 unavailable 时仅返回安全降级，绝不持久化 digest 或原文。

## 严格范围

允许：

- 修改 `backend/app/agents/stage08_collaboration.py`
- 新增 `backend/app/services/stage08_collaboration.py`
- 修改 `backend/app/services/stage08_context_composition.py`
- 修改 `backend/tests/unit/test_stage08_collaboration_graph.py`
- 新增 `backend/tests/unit/test_stage08_collaboration_service.py`
- 修改 `backend/tests/integration/test_stage08_retrieval_pgvector.py`
- 新增 `.superpowers/sdd/stage08-package-e-task-e2-report.md`

禁止：models/migrations/UoW/interfaces/global role matrix/API schemas/routes/main/Telegram/Docker/configuration/Milvus/真实 Provider/HTTP/Redis/Tool Gateway/draft/AgentRun/audit/outbox 写入。不要修改 E1 contracts，除非发现无法符合已批准合同的硬性矛盾；若遇到该矛盾立即报告而非自行扩范围。

## 必须遵守的安全与行为约束

1. 客户端不可传入 effective role、employee/view/field scope、retrieval filter/budget、authority、群材料、compressor input 或 digest。E2 service 只从 sealed command、当前 authenticated actor 和现有 `DigitalEmployee`/member grant 及 C1 plan 推导；空值、歧义、暂停 employee、撤权或 relation drift 一律 fail closed。
2. C3 与 D4 都必须在各自**消费点**复用现有 current-state revalidation；任何 member/employee/view/field/record relation/group binding/source/chunk/Memory lifecycle 在计划后变化时，只丢弃受影响材料或安全降级，不能复用缓存私有文本。不得因为一个分支失败而泄漏其他分支材料。
3. read fan-out 总数固定不超过 3，顺序稳定为 composite_context、retrieval、general_advice；只在完全无合法材料时，且 command intent 允许时，才可以 `general_advice` 降级。safe result 只含 status、计数、固定 degradation code 和 E1 safe label/ordinal，不含 raw query、C3 group text/digest、D4 private evidence、UUID、field、score、authority、provider error 或业务原文。
4. C3 新增的 handoff 必须是内部 opaque carrier，正常构造/JSON/pickle/repr 都不能暴露或伪造 raw material；只接受 `group_compression_pending` 的当前 composite，消费时重建/重验证 group authority/window/fragment lineage。compressor 异常、timeout、shape drift 或 unavailable 都映射为 no-group degradation；C3 不保存 digest、不更改既有 public safe-view contract。
5. E2 只使用 `UnavailableContextCompressor` 或 deterministic fake。不能调用 OpenRouter/embedding network/Telegram/任何 HTTP。D4 可使用现有 disposable pgvector **本地集成测试**，但不得回退默认/native DB、不得泄露 DSN、测试后知识 source/chunk/outbox/idempotency/audit 残留必须为 0。
6. E1 graph topology 仍必须精确十节点、`checkpointer=None`。E2 可为节点提供内部 service adapter，但不能把 private material 放进 public state/DTO/log/checkpoint，也不能开始 analysis/policy/draft/API。

## TDD/验收步骤

1. 先写 RED：fan-out 至多三支且稳定 fan-in；member/source/Memory revoke after plan 只移除对应 material；pending group compressor unavailable 不保存 digest；客户端式/伪造 authority input 被拒绝；private text 不在 repr/safe result/persistent sink。
2. 运行 RED：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
```

3. 最小实现 C3 opaque compression handoff 与 service fan-out/degrade，复用 C1/C3/D4 正确入口，禁止 raw ORM/SQL。
4. 运行 GREEN 和回归：

```powershell
python -m pytest -q -W error -p no:cacheprovider tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_retrieval_provider.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py
$env:DATABASE_URL = $env:STAGE08_RAG_DATABASE_URL; python -m pytest -q -W error -p no:cacheprovider tests/integration/test_stage08_retrieval_pgvector.py
python -m compileall -q app/agents/stage08_collaboration.py app/services/stage08_collaboration.py app/services/stage08_context_composition.py
```

若 `STAGE08_RAG_DATABASE_URL` 未显式配置或 container 不健康，报告这个阻塞，不得将 skip 算作通过；允许 root 后续检查专用 disposable environment。

5. 中文报告必须记录 RED/GREEN 精确结果、C3/D4 current-state 证据、仅本地 pgvector 的情况、无外部调用/写入、cleanup、跳过项与风险；完成后等待 fresh independent review，不能关闭 E2/Package E。
