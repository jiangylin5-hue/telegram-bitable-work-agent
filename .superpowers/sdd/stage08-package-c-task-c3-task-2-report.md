# Stage08 Package C3 — Task 2 Private Composer and Direct Renderer Report

## Status

- Task status: `review findings remediated; pending fresh independent re-review`
- Scope: 仅 C3 Task 2 的 C1/C2 私有合成、direct renderer、消费前重组与 fail-closed 边界。
- Not claimed: Task 3、C3 完成、Package C 完成、PostgreSQL 组合验证、Provider/LLM、Telegram 外部活动、部署或生产可用。

## Changed files

- `backend/app/services/stage08_context_composition.py`
  - 新增普通 `__slots__` 私有 `_Stage08CompositeContext` 与私有 block；均非 Pydantic、不可 JSON 序列化，`repr` 只暴露固定 safe status/count。
  - 新增且仅新增两个 public service functions：`compose_stage08_context`、`render_stage08_composite_context`。
  - 每次 compose 重新验证 C1 plan/actor 并调用既有 C1 composer；仅由 plan workspace/employee 和 server actor 构建 C2 authority。
  - direct C2 window 仅经既有 C2 fresh materializer 读取当前可用 fragment；C1 blocks 固定在前，C2 D6 blocks 固定在后。
  - 内容预算只计算 C1 canonical content chars 与 group fragment code points，严格执行 C1 12,000、group direct 24,000、C3 36,000 hard cap；不做文本截断。
  - renderer 每次从私有 plan/actor 重新合成；并用原 opaque C2 authority/window 复验本次 consumer lineage。projection/source/mapping/member/binding/relation 漂移会丢弃全部旧 group blocks，同时只渲染重新读取的当前 C1 结果。
  - plan actor 与当前 server actor 不一致时整体 fail closed，避免 C1 拒绝后 C2 误用另一成员 binding。
  - renderer 对“真实 composite 类型但其私有 C2 window safe view 已被篡改”的状态返回 `None`；合法当前态漂移与非法私有对象状态分开处理。
  - independent review Important 修复：private composite 保存原始 group-rendered count；消费前将其与 revalidated composite view、window selected count、opaque handle tuple 数量、authority/window nonce 及 handle mapping 关系严格绑定。合法 zero view 与残留 handles 不一致时返回 `None`。
  - `compression_required=True` 在 Task 2 只返回不可消费的 safe `no_evidence` private object；不 materialize、不渲染、不调用 Provider。pending 传播仍属于 Task 3。
- `backend/tests/unit/test_stage08_context_composition_service.py`
  - 新增 direct C1+C2 合并顺序、D6 header、预算、安全 view/repr、general marker 去除、partial status、无 group 的 C1 三态保持测试。
  - 新增 forged plan/composite、nested safe-view carrier、invalid UTC、36,000 inconsistent source fail-closed 测试。
  - 新增 projection/source type/mapping/member/binding/relation 漂移，C1 record/view/Memory 漂移与消费前重组测试。
  - 新增跨 actor binding 隔离、无记录/Memory/audit/outbox/AgentRun/notification mutation、禁止依赖静态测试。
  - independent review Minor 修复：预算测试使用精确 C2 private materialization/fragment types，并通过 spy 证明 `_compose_direct_result` 实际收到 24,500 group chars，避免类型守卫提前失败冒充预算验证。

## TDD evidence

### RED 1 — service absent

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py
```

Actual: collection error，唯一根因是 `app.services.stage08_context_composition` 尚不存在；`1 error in 2.61s`。

### RED 2 — interface skeleton only

加入仅抛出 `NotImplementedError` 的两个目标接口后复跑同一命令。

Actual: `16 failed in 2.90s`，均为未实现行为；测试中一个非法的 scoped `general_advice` request fixture 随即按既有 C1 contract 修正为 view drift 后的合法 general fallback，不改变生产合同。

### First GREEN and drift correction

最小 direct composer/renderer 首轮结果：`15 passed, 1 failed in 2.44s`。唯一失败证明同一 mapping 的 `mapping_version` 在 composition 后变化时，完全新建的 authority 会重新接受 group body。renderer 随后加入原 opaque lineage 的 fresh materialization 复验；修正后原 16-case suite 为 `16 passed`。

### Security regression RED — cross-actor binding

```powershell
python -m pytest -q tests/unit/test_stage08_context_composition_service.py::test_actor_mismatch_never_uses_a_different_members_group_binding
```

Actual RED: `1 failed in 1.51s`；C1 因 actor mismatch 拒绝，但 C2 可使用另一个当前成员的有效 binding，composite 错误成为 `internal_evidence`。

最小修复：compose 前要求 `actor_type=user` 且 `actor.actor_id == plan.actor_user_id`。

Actual GREEN: `1 passed in 1.06s`。

### Final focused GREEN

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py -W error
```

Actual final after review remediation: `20 passed in 1.27s`，无 warning。

### Forged private-state RED

在最终私有对象审计中新增“真实 composite 的 private C2 window view 被替换为非法对象”回归。

Actual RED: `1 failed in 1.69s`，renderer 向调用方抛出了 nested Pydantic validation error。第一次收紧后虽然不再抛错，但错误地退化为 C1-only string；按“invalid private object returns None”合同继续保持 RED。最终 helper 区分合法 drift、fresh 与 invalid 三态。

Actual targeted GREEN: `1 passed in 0.95s`。

### Independent review remediation RED/GREEN

Important — forged zero-window lineage bypass：

```powershell
python -m pytest -q tests/unit/test_stage08_context_composition_service.py::test_structurally_valid_zero_window_cannot_bypass_original_group_lineage
```

Actual RED: `1 failed in 1.61s`。mapping version 漂移本来会移除 secret；把原 private window view 换成结构合法的 unavailable/zero view 后，renderer 再次输出 `forged-zero-lineage-secret`。

最小修复：新增原始 group-rendered count，并在 zero early return 前严格核对 composite safe view、window selected count、opaque handles、authority/window nonce 和 mapping 关系。任何结构不一致返回 invalid `None`；合法原始 no-group composite 保持可用。

Minor — budget branch coverage：

先给旧 `SimpleNamespace` fake 用例加入 `_compose_direct_result` 实际到达断言。Actual RED: `1 failed in 1.31s`，`observed_group_chars=[]`，证明旧用例在 materialization type guard 提前退出。

随后只把 fake 换为 49 个精确 `_SelectedGroupContextFragment`（每条 500 chars）与精确 `_GroupContextMaterialization`；原 window 是 49 个 489-char direct fragments。spy 实际观测 `24,500` chars 进入 `_compose_direct_result` 并触发 direct group cap fail-closed，未削弱任何生产 type guard。

两项 targeted GREEN：`2 passed in 1.21s`。

## Regression verification

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py
```

Actual final after review remediation: `178 passed in 1.64s`。

```powershell
Push-Location backend
python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py
```

Actual: exit `0`，无输出。

```powershell
rg -n "Message|raw_text|raw_caption|normalized_text|TelegramBot|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route|Redis|pgvector|LangGraph|MemoryItem|AgentRun|audit|outbox" backend/app/runtime/stage08_context_composition_contracts.py backend/app/services/stage08_context_composition.py
```

Actual: 无匹配；按预期 `rg` 原始 exit `1`，包装命令将“无匹配”解释为成功。

Public function scan：生产 service 仅匹配：

```text
compose_stage08_context
render_stage08_composite_context
```

## Scope exclusions and skipped checks

- 未访问 PostgreSQL；真实组合漂移属于 C3 Task 4。
- 未实现或测试 >24,000 group raw window 的 pending handoff；Task 2 仅验证 direct path，Task 3 负责 pending contract 和专门 corpus。
- 未调用 Provider/LLM、Telegram 网络、Redis、LangGraph、RAG/vector、审计、outbox、Mini App 或外部系统。
- 未修改 C1/C2、schema/migration、route/API、permission 或任何 Git state。
- `python -m ruff ...` 未执行成功，因为当前解释器没有安装 `ruff`（`No module named ruff`）；以 pytest `-W error`、compileall、static boundary scan 和 whitespace check 作为本 Task 实际静态证据，不把 ruff 声称为已通过。

## Remaining risks

- Task 2 的 compression branch 只是安全不可消费占位；Task 3 必须实现并单独复审 `group_compression_pending`，不得把当前 `no_evidence` 当作最终压缩语义。
- 当前全部行为证据来自 InMemory UoW；mapping/projection 与 C1/C2 组合的真实事务/并发语义仍需 Task 4 disposable PostgreSQL 验证。
- 本报告及 remediation 不替代 fresh independent re-review；Task 2 尚不能标记 final PASS。

## Cleanup

- 无临时数据库、外部记录、Provider/Telegram 调用、缓存或持久化 digest。
- 无残留 pytest/Python 进程；曾有一次工具侧异常长等待，命令被终止后检查进程列表为空，随后同一 suite 在约 4 秒内正常完成。
