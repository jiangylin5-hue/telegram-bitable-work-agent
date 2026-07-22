# Stage08 Package C Task C1 上下文工程证据

## Status

- Document status：`task-level evidenced / independently-reviewed PASS (Fix Round 3)`
- Scope：仅 C1 类型化 `ContextPlan` / `ContextPack`、关系解析、授权表格投影、非群业务 Memory、`general_advice` marker、确定性预算/截断/重读与 ID-free renderer。
- Evidence boundary：本地单元测试与 disposable local PostgreSQL；不代表 Package C、Stage08、staging 或 production 验收完成。Package B B5 已在后续独立复审中关闭，但不由本 C1 证据替代。

## 1. RED → GREEN 证据

| Cycle | RED | GREEN |
| --- | --- | --- |
| contracts baseline | 合同测试首次因 `app.runtime.stage08_context_contracts` 不存在而失败；随后 source/budget 绕过测试先出现 `DID NOT RAISE`。 | 完成 strict/frozen 合同与 service-boundary revalidation，并补齐 plan budget validator。 |
| service baseline | 服务测试首次因 `app.services.stage08_context` 不存在而失败。 | resolver、planner、composer、renderer 聚焦单测通过。 |
| intent/source matrix | 首轮审查证明 plan 可接受错误 source 组合、超过三个 table view、错误 priority/reason 和按 source 重复放大预算。 | 合同强制精确矩阵、唯一 view 上限、固定 priority/reason，并校验 table/Memory source 的预算总和；planner 稳定拆分全局预算。 |
| pack binding | 首轮审查证明 evidence/usage 未与 plan、真实 selected/truncated/omission/content 绑定。 | pack validator 校验 source kind、workspace、两位顺序 ordinal、selected/truncated/omission/content exactness，以及单项字符上限。 |
| evidence safety | 首轮审查证明 UUID 只检查完整 scalar，嵌入字符串、key 或大小写/分隔符变体的敏感 metadata 可进入 renderer。 | canonicalizer 替换 value/key 内嵌 UUID，删除内部 identifier key，对 token/permission/identity/source reference fail closed；构造对象在边界重校验。 |
| Memory scope | 新增 customer/project scope 用例后，旧合同拒绝合法 `memory_lookup`；旧 matcher 还允许请求维度缺失或 Memory 多出维度。 | request 接受 customer/project scope；读取前要求 customer/project 两个维度逐项精确相等。 |
| read-only lifecycle | 真实 PostgreSQL TTL/source drift 场景显示旧 C1 读取路径会把 item 标记 stale/expired 并写 audit。 | `read_memory_projection` 新增内部 `read_only`；C1 使用该模式，验证失败返回空结果但 item 仍为 active、audit 数不变；默认 lifecycle 行为回归继续通过。 |
| normalization/budget | 新增长字符串、列表、深度、非有限浮点、路径、单项/总预算和多 view 测试，暴露边界覆盖不足。 | canonicalization 与 composer 在固定规则下稳定截断/拒绝，预算不随 view 数成倍扩大，零额度 source 不调用 `limit=0`。 |
| Fix Round 2 pack/source binding | 第二轮独立复审证明 platform evidence 可带未计划 view、超出每个 source 上限；constructed pack 还可携带内部 `id` carrier。 | pack 逐条绑定计划 `view_id`/source version/业务 scope/每 source 上限；contract fail-closed 拒绝 `id`、`record_id`、`memory_id` 及其变体，并为普通与 `model_construct` 构造增加回归。 |
| Fix Round 3 review | 审查重新执行 source binding、默认/只读 lifecycle、UUID/内部 ID、scope 与 budget 攻击路径。 | `PASS / 0 Critical / 0 Important / 1 documentation Minor`；本文件与实施报告现同步最终计数。 |

## 2. Fresh verification

### 2.1 C1 unit

```powershell
cd backend
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py
```

结果：`74 passed in 1.20s`。

### 2.2 Context + Memory focused unit

```powershell
cd backend
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py
```

结果：`158 passed`（C1 `74` 与 Memory `84` 分别复跑）。

该集合同时证明 C1 的 `read_only` 读取与 B2 默认 `lifecycle_aware` 行为均有回归覆盖。

### 2.3 Disposable local PostgreSQL

使用已授权的 `STAGE06_LOCAL_DATABASE_URL`，目标仅为本机 disposable PostgreSQL；文档不记录凭据。

```powershell
cd backend
python -m pytest -q tests/integration/test_stage08_context_postgres.py
```

结果：`6 passed in 9.00s`。

覆盖：

- 当前可见单跳客户/项目关系与有界 table + Memory pack；
- plan 后字段权限撤销，旧字段值不再进入 evidence；
- plan 后 record version / relation scope 漂移，降级为 `general_advice`；
- Memory TTL / source version 漂移在只读消费中 fail closed，同时 item 状态和 audit 数不变；
- group Memory 与历史 `Message` sentinel 同时存在，但 C1 不读取、不渲染；
- 每项测试事务 rollback，C1 未新增持久化对象。

### 2.4 C1 + Package A/B focused regression

```powershell
cd backend
python -m pytest -q tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/integration/test_stage08_context_postgres.py tests/unit/test_stage08_memory_contracts.py tests/unit/test_stage08_memory_service.py tests/unit/test_stage08_tool_gateway.py tests/unit/test_stage08_runtime_service.py
```

结果：`196 passed in 9.37s`。

### 2.5 Compile 与边界扫描

```powershell
cd backend
python -m compileall -q app/runtime/stage08_context_contracts.py app/services/stage08_context.py app/services/stage08_memory.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_memory_service.py tests/integration/test_stage08_context_postgres.py
```

结果：exit `0`。

- 对 C1 新增 production 文件扫描 `Message|raw_text|telegram|OpenRouter|APIRouter|router.|alembic|migration|webhook`：`NO_FORBIDDEN_C1_PRODUCTION_MATCHES`；API/router/migration registration scan：`NO_C1_ROUTE_OR_MIGRATION_REGISTRATION`。
- 限定文件 `git diff --check`：exit `0`。

## 3. 安全与数据行为

- `ContextPlan` 只冻结 source kind、view/version、scope/version 与预算，不冻结 record/Memory 内容，也不是 capability、ticket 或权限快照。
- planning 与 composition 两次重算 active workspace、employee、member eligibility、employee table/view scope 和 view access。
- customer/project 关系只从 `read_record_for_actor` 可见的 `linked_record` cell 解析，不读取 raw `record.values`。
- table evidence 仅由 `list_view_records` 与 `read_record_for_actor` 的一致交集生成；service 不直接调用 `uow.list_records`。
- Memory 只通过 `read_memory_projection(..., lifecycle_mode="read_only")` 重读；成员、TTL、source 与 scope 仍校验，任何漂移均 fail closed，但不改变 Memory 生命周期、不写 audit。
- `memory_lookup` 可携带 customer/project scope；Memory payload 必须与两个请求维度逐项精确匹配，缺失、错误和额外维度都拒绝。
- budget 是全局上限：最多 20 table records、2 Memory items、4 evidence、单项 2000 chars、合计 12000 chars；多个 view 不能放大 table budget。
- canonicalizer 固定 key order、list/string/depth 上限、changed paths；NaN/Infinity 拒绝。UUID fragment 会被固定 marker 替换，敏感 metadata key fail closed。
- `ContextPack` 将 evidence 类型/workspace/ordinal 和 usage 精确绑定到 plan 与实际内容；`model_construct` 等构造绕过在 service boundary 被拒绝。
- renderer 仅显示 evidence ordinal、label/type/version、scope dimension name 与 canonical content；不显示 scope UUID、record/Memory ID、source refs、permission snapshot 或 identity token。

## 4. 未执行与保留风险

- 未运行 full backend suite、前端 suite、Stage08 package acceptance；本轮只运行 C1 及直接 A/B 回归。
- 未调用 Provider/LLM/OpenRouter、Telegram/Bot API、HTTP/network、Redis、RAG/pgvector 或 LangGraph。
- 未新增 API/router、migration、schema、permission action/role、ticket、draft、notification、AgentRun 或 C1 持久化。
- Package B B5 package-level PostgreSQL/生命周期 closure 已在后续独立复审中完成；C1 的 Package C 边界不因此扩大。
- C2 group recent window、Message/history、时间衰减、retention、edit/delete/version/order 仍是独立合同门禁；C1 未预埋读取旁路。
- C1 已完成三轮独立审查；Fix Round 3 为 `PASS / 0 Critical / 0 Important / 1 Minor`，该 Minor（过期文档计数）已在本次同步关闭。
- 未进行 staging/production 验证或部署。

## 5. Temporary cleanup

- 未创建临时脚本、fixture 文件、服务或外部资源。
- PostgreSQL fixture 仅重建授权的 disposable local schema，并在每项测试结束 rollback 业务事务。
- 无 stage、commit、reset、checkout 或 clean。
