# Stage08 Package C — C3 Direct-to-Pending Renderer 修复报告

## Status

- 修复状态：`implementation complete; pending package-level review`
- 缺陷来源：Package C Task 5 独立复审发现的 Important C3 renderer 缺陷。
- Scope：仅修复“旧 direct composite 在当前 C2 窗口升为 compression pending 后丢失当前 C1 internal evidence”的渲染分支。
- Not claimed：不代表 C3、Package C、Package E/F、真实 PostgreSQL 组合验证、Provider/LLM、Telegram 外部操作、部署或生产可用已完成。

## Changed files

- `backend/app/services/stage08_context_composition.py`
  - renderer 在获得当前重组 composite 后，先验证其 private safe view/window。
  - 若**当前**状态是 `group_compression_pending`，转入既有私有 `_render_pending_composite`：只重新验证当前 C1 与 C2 pending lineage，并只返回当前 C1 internal evidence。
  - 因此不再继续使用旧 direct composite 的 materializer/blocks；不会输出旧 direct 群正文，也不会读取新 pending 群正文。
  - 当前 C1 非 internal evidence、当前 pending lineage 无效或任何 private view/window 验证失败时均返回 `None`。
- `backend/tests/unit/test_stage08_context_composition_service.py`
  - 新增 direct → real pending 回归：先组成一条 500 字符 direct 群片段，再增加 48 条 500 字符片段，使当前 C2 工作窗口精确达到 `49 × 500 = 24,500`。
  - 断言 renderer 只保留当前 C1 `business_data`，旧 direct secret 和 48 条新 pending secret 均不出现。
  - 新增 materializer fail-fast 测试：在 transition renderer 调用前替换 C2 materializer；修复后必须零调用。
- `.superpowers/sdd/stage08-package-c-c3-pending-transition-remediation-report.md`
  - 记录独立发现后的真实 RED/GREEN、回归和范围审计。

## TDD evidence

### RED

先添加两条 direct → pending 回归，未修改生产代码时运行：

```powershell
Push-Location backend
python -m pytest -q \
  tests/unit/test_stage08_context_composition_service.py::test_direct_composite_transitioning_to_pending_renders_current_c1_only \
  tests/unit/test_stage08_context_composition_service.py::test_direct_to_pending_renderer_never_materializes_group_body \
  -W error
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
```

Actual：`2 failed in 1.32s`。

- 第一条的实际旧输出是精确空字符串 `''`，因此缺失当前 C1 `[business_data:01 ...]` 和 `Launch C3`。
- 第二条在旧 renderer 的 `_original_group_window_drifted` 调用了 C2 materializer 时故意失败，证明旧 direct path 会在 transition 中读取旧群正文。

以上均为设计缺陷本身的失败，而非夹具、导入或 collection error。

### GREEN

最小修复让 renderer 基于**当前重组的 pending 状态**选择 `_render_pending_composite`，而不再使用旧 direct blocks/path。复跑同一命令：

Actual：`2 passed in 1.15s`，无 warning。

完整 C3 service unit：

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py -W error
```

Actual：`38 passed in 1.51s`，无 warning。

## Regression and scope verification

```powershell
Push-Location backend
python -m pytest -q \
  tests/unit/test_stage08_context_composition_contracts.py \
  tests/unit/test_stage08_context_composition_service.py \
  tests/unit/test_stage08_context_contracts.py \
  tests/unit/test_stage08_context_service.py \
  tests/unit/test_stage08_group_context_contracts.py \
  tests/unit/test_stage08_group_context_ingestion.py \
  tests/unit/test_stage08_group_context_service.py \
  -W error
```

Actual：`196 passed in 2.06s`，无 warning。

```powershell
python -m compileall -q \
  app/runtime/stage08_context_composition_contracts.py \
  app/services/stage08_context_composition.py
```

Actual：exit `0`，无输出。

扫描 C3 production files 的禁止边界：

```text
Message raw_text raw_caption normalized_text TelegramBot sendMessage
httpx requests OpenRouter Provider LLM digest APIRouter add_api_route
Redis pgvector LangGraph MemoryItem AgentRun audit outbox
```

Actual：无匹配；包装命令 exit `0`。

## Scope exclusions and risks

- 未修改 C1/C2、schema/migration、API/route、permission、database integration、Mini App、部署或 Git state。
- 未访问 PostgreSQL、网络、Telegram、Provider/LLM、Redis、RAG/vector、LangGraph；未生成 digest 或写入任何持久化对象。
- 真实 PostgreSQL/并发组合验证仍属于 C3 Task 4；本修复不替代 Package-level fresh review。
- 不宣称 C3 或 Package C 完成。

## Cleanup

- 无临时数据库、外部记录、Provider/Telegram 调用、缓存、digest 或后台进程。
