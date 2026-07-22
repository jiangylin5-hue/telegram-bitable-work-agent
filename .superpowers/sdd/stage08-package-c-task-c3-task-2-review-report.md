# Stage08 Package C3 — Task 2 独立复审报告

## Review status

- Result: `FINAL PASS after remediation`
- Critical: 无
- Important: 无（原 1 项已关闭）
- Minor: 无（原 1 项已关闭）
- Scope: 仅复审 C3 Task 2 private composer 与 direct renderer；本结论不代表 Task 3、C3 或 Package C 完成。

## Reviewed authority and files

已实际读取并对照：

- `docs/superpowers/specs/2026-07-20-stage08-c3-context-composition-design.md`
- `docs/superpowers/plans/2026-07-20-stage08-package-c3-composition-implementation.md`
- `.superpowers/sdd/stage08-package-c-task-c3-task-1-brief.md`
- `.superpowers/sdd/stage08-package-c-task-c3-task-1-report.md`
- `.superpowers/sdd/stage08-package-c-task-c3-task-1-review-report.md`
- `.superpowers/sdd/stage08-package-c-task-c3-task-2-brief.md`
- `.superpowers/sdd/stage08-package-c-task-c3-task-2-report.md`
- `backend/app/runtime/stage08_context_composition_contracts.py`
- `backend/app/services/stage08_context_composition.py`
- `backend/tests/unit/test_stage08_context_composition_contracts.py`
- `backend/tests/unit/test_stage08_context_composition_service.py`
- C1/C2 实现与私有接口：`stage08_context.py`、`stage08_group_context.py`、它们的 runtime contracts 及相关 unit tests。

## Final independent re-review

2026-07-20 按 `.superpowers/sdd/stage08-package-c-task-c3-task-2-review-fix-brief.md` 对修复后实现与测试做了 fresh re-review。最终无 Critical、Important 或 Minor 未关闭项，Task 2 可放行进入 Task 3，但不代表 Task 3/C3/Package C 完成。

复审确认：

- Important 已真实关闭：`backend/app/services/stage08_context_composition.py:365-403` 先重建验证 composite/window safe view，然后将 window selected count 与 opaque handle tuple、原 composite `_group_rendered_count`、composite view 的 window/rendered counts 和 status 绑定；有 group 时还核对 exact handle type、authority/window nonce 与 mapping relation。结构合法的 zero view 与残留 handle 不一致时返回 invalid `None`，不再渲染新 group body；合法原始 no-group composite 仍保持可用。
- 对应回归 `backend/tests/unit/test_stage08_context_composition_service.py:390-426` 完整构造 mapping-version drift + 结构合法 unavailable/zero view，并断言 renderer 返回 `None`。
- Minor 已真实关闭：`backend/tests/unit/test_stage08_context_composition_service.py:580-629` 使用 49 个精确 `_SelectedGroupContextFragment` 和精确 `_GroupContextMaterialization`，没有削弱生产 type guard；spy 证明 `_compose_direct_result` 实际收到 `24,500` group chars，随后命中 direct cap 并返回 no-consumer composite，未截断或渲染文本。
- 原始 C1/C2 接口、schema/API/permission、Provider/Telegram/Memory/RAG/Redis/LangGraph/audit/outbox 边界未改变。

独立验证结果：

```text
targeted remediation: 2 passed in 0.94s
Task 2 focused -W error: 20 passed in 1.10s
Task 1 + C1 + C2 + Task 2 unit regression: 178 passed in 1.65s
compileall: exit 0
prohibited dependency scan: no matches (rg exit 1)
public function scan: compose_stage08_context / render_stage08_composite_context only
scoped git diff --check: exit 0
```

## Historical findings (closed)

### Important 1 — 结构合法的 forged C2 window view 可绕过原 opaque lineage 复验

`backend/app/services/stage08_context_composition.py:362-365` 在读取原始 `GroupContextWindowView` 后，只要 `selected_fragments == 0` 就直接返回“无漂移”，没有核对 opaque window 内仍然存在的 `_projection_handles`。因此，将一个原本含 handle 的 private window 的 `_view` 替换为结构完全合法的 `group_context_unavailable`/0-fragment view，会跳过 `_materialize_group_context_window` 对原 authority/window lineage 的复验。

独立最小复现：

1. 构建含 `lineage-secret` fragment 的 composite。
2. 将 mapping version 递增，但保持当前 mapping 仍然可授权。
3. 未篡改 window view 时，renderer 正确不输出 group body。
4. 将原 window `_view` 替换为合法的 0-fragment unavailable view 后，renderer 重新输出 `lineage-secret`。

实际输出：

```text
without_forgery_contains_secret= False
with_forgery_contains_secret= True
```

这违反 Task 2 contract 要求的“original opaque C2 lineage blocks stale group body after mapping drift or forged window state”。当前用例 `backend/tests/unit/test_stage08_context_composition_service.py:377-387` 只把 `_view` 替换成 `object()`，因此只覆盖了验证异常，没有覆盖“结构合法但与 opaque handles 不一致”的 forged state。

建议最小修复：在任何 0-fragment 早返前，先以严格类型和数量核对 `window._projection_handles` 与 revalidated view；存在任何不一致时返回 invalid/`None`，并新增结构合法 forged view + mapping drift 的 RED/GREEN 用例。

### Minor 1 — over-budget 用例因 fake 类型错误提前失败，未命中预算分支

`backend/tests/unit/test_stage08_context_composition_service.py:542-554` 返回 `SimpleNamespace` materialization/fragment，但生产代码先在 `backend/app/services/stage08_context_composition.py:173-174` 要求 materialization 为精确 `_GroupContextMaterialization` 类型，且 `:323-325` 要求 fragment 为精确 `_SelectedGroupContextFragment` 类型。当前用例因类型检查提前 fail closed，没有真正证明 `group_chars > 24_000` 或 `total_chars > 36_000` 分支不截断、不渲染。

建议用精确 private C2 类型构造与 window usage/handle 数量一致、但实际 materialized char sum 超 direct cap 的测试状态，明确言及 `_compose_direct_result` 的预算失败分支。

## Confirmed behavior

除上述问题外，复审确认：

- service 仅有 `compose_stage08_context` 和 `render_stage08_composite_context` 两个非下划线函数；private composite/block 为普通 `__slots__` object，非 Pydantic/JSON，`repr` 只含安全 status/count。
- C1 plan 重建验证、actor-plan identity equality 和 C1 composition 都发生在任何 C2 authority 构建之前；跨 actor binding 用例正确 fail closed。
- C2 仅经现有 private authority/window/materializer 处理相同 business scope，没有 `Message`、历史 raw 字段、Telegram 网络或 caller-provided group identity fallback。
- renderer 每次重新读取 C1 当前记录/view/Memory；普通 projection/source/mapping/member/binding/relation drift 用例能正确丢弃旧 group body。
- C1 evidence 在前，D6 group blocks 在后；general marker 不与内部 evidence 混用；12,000/24,000/36,000 constants 与 direct arithmetic 实现正确。
- Task 2 compression branch 仍为不可消费 fail-closed，没有 raw group rendering、Provider/digest/persistence 副作用。
- 没有发现 C1/C2 public code、schema/migration、API/permission 或外部系统修改。

## Independent verification

### Task 2 focused

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py -W error
Pop-Location
```

实际：`19 passed in 1.83s`，exit `0`。

### Task 1 + C1 + C2 + Task 2 unit regression

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py
Pop-Location
```

实际：`177 passed in 1.69s`，exit `0`。

### Compileall / prohibited scan / public function scan

```text
compile_exit=0
prohibited_scan_exit=1  # rg 无匹配，符合预期
public functions:
93:def compose_stage08_context(
199:def render_stage08_composite_context(
```

### Scoped diff check

`git diff --check` 对 Task 1/2 C3 runtime、service、tests 和 Task2 report 返回 exit `0`。相关文件均为当前共享工作树中未跟踪新文件，本复审未执行 stage/commit/reset/checkout/clean。

## Scope and remaining work

- Task 2 两项独立复审发现已关闭，最终 Task 2 verdict 为 `PASS`。
- Task 3 compression pending、Task 4 PostgreSQL 组合证据、Task 5 C3 总复审均未由本报告证明，不得用本 PASS 声称 C3 或 Package C 完成。
- 本次 re-review 仅更新原复审报告；未修改实现、测试、数据库或项目阶段文档，未访问外部系统。
