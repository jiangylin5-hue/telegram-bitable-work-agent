# Stage08 Package C3 — Task 3 压缩等待语义执行报告

## Status

- Task status：`implementation complete; pending independent review`
- Scope：仅完成 C3 Task 3 已批准的 `group_compression_pending` 私有交接、消费前重组和失败关闭语义。
- Not claimed：不代表 C3、Package C、Package E/F、真实 PostgreSQL 组合验证、Provider/LLM、Telegram 外部活动、生产部署或生产可用已经完成。

## Changed files

- `backend/app/services/stage08_context_composition.py`
  - 将 C2 `compression_required=True` 从 Task 2 的安全占位改为真实私有 `group_compression_pending` composite。
  - pending safe view 只复制 C2 safe view 的 `group_status`、窗口条数与压缩标志；群正文渲染条数和字符数固定为 `0`，总内容字符数只等于当前 C1 internal evidence 字符数。
  - pending composite 只保留原有不透明 C2 authority/window 供未来 Package E 使用，不保存群正文 block、不生成 digest，也不新增公开 handoff API。
  - pending renderer 使用独立的当前态重组路径：重新读取当前 C1，并只重建/核对 C2 safe window 和 opaque handle lineage；不调用 C2 materializer。
  - 原 pending lineage 仍有效且当前 C1 仍是 `internal_evidence` 时，只输出当前 C1 renderer 文本；C1 general/no evidence 返回 `None`。
  - projection、source type、mapping version、member、binding、customer/project relation、retention、C1 view、actor、safe window 或 handle 漂移均 fail closed 为 `None`。
  - 原 pending 窗口后来降至 direct/unavailable 时仍要求显式 rebuild，renderer 返回 `None`，不会先读取或输出新 direct 群正文。
  - Task 2 direct 路径与其现有消费前物化/漂移语义保持不变。
- `backend/tests/unit/test_stage08_context_composition_service.py`
  - 新增真实 C2 高窗口夹具：49 条 × 500 Unicode code points = 24,500，严格大于 24,000，同时不超过 60,000 / 120 / 500 上限。
  - 新增 pending safe view 精确算术、opaque repr/JSON error 隐私、C1-only renderer、general/no-C1 不可渲染测试。
  - 通过 monkeypatch 令 C2 materializer 一旦调用立即失败，证明 compose、renderer、漂移和 pending→direct 分支均不读取群正文。
  - 新增 projection/source/mapping/member/binding/relation/retention/view/actor 漂移、伪造 window/handles、pending→direct 明确重建测试。
  - 新增无 Provider/LLM/digest、Telegram/network、Memory persistence、Redis/LangGraph、audit/outbox 等依赖的静态断言，并复用既有 side-effect 计数证明没有持久化副作用。
- `.superpowers/sdd/stage08-package-c-task-c3-task-3-report.md`
  - 记录本任务真实 RED/GREEN、范围、验证、跳过项和风险。

## TDD evidence

### RED — 高窗口 pending 行为尚未实现

在修改生产代码前先加入全部高窗口用例，运行：

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_context_composition_service.py -W error
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
```

Actual：`15 failed, 21 passed in 1.73s`。

15 个新增用例都在同一预期原因上失败：现有 Task 2 对 `compression_required=True` 返回 `no_evidence`，尚未传播 `group_compression_pending`；既有 21 个 direct/安全回归保持通过。没有 collection error、夹具错误或假 RED。

### GREEN — 最小 pending 传播与专用重组

实现 pending private composite、safe usage 和专用无物化 renderer 后复跑同一命令。

Actual：`36 passed in 2.93s`，无 warning。

### Actor-lineage security RED/GREEN

首轮 GREEN 后把 actor 漂移用例从“不同 actor id”强化为“相同 user id、不同 role”。这证明仅校验 `plan.actor_user_id` 不足以绑定原 opaque C2 authority：

```powershell
python -m pytest -q \
  tests/unit/test_stage08_context_composition_service.py::test_pending_renderer_fails_closed_on_original_lineage_drift[actor] \
  -W error
```

Actual RED：`1 failed in 1.48s`。renderer 错误输出了 C1 business evidence，说明修改后的 composite actor 与原 C2 authority actor 尚未绑定。

最小修复：深度重建并比较 composite actor 与原 authority actor 的完整 frozen `Actor` 值（`actor_type`、`actor_id`、`role`、`customer_ids`）。

Actual targeted GREEN：`1 passed in 0.98s`；最终 focused GREEN：`36 passed in 1.28s`。

## Regression verification

### Task 1 + C1 + C2 + Task 2 + Task 3 unit regression

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
$exitCode = $LASTEXITCODE
Pop-Location
exit $exitCode
```

Actual final：`194 passed in 2.38s`，无 warning。

### Compile and prohibited-boundary scan

```powershell
Push-Location backend
python -m compileall -q \
  app/runtime/stage08_context_composition_contracts.py \
  app/services/stage08_context_composition.py
```

Actual：exit `0`，无输出。

对 C3 production files 扫描以下禁止依赖/载体：

```text
Message raw_text raw_caption normalized_text TelegramBot sendMessage
httpx requests OpenRouter Provider LLM digest APIRouter add_api_route
Redis pgvector LangGraph MemoryItem AgentRun audit outbox
```

Actual：无匹配；包装命令 exit `0`。

尾随空白扫描覆盖本任务 production/test 文件，无匹配；包装命令 exit `0`。

`git diff --check -- <scoped files>` actual exit `0`。这两个 Stage08 文件在共享 worktree 中仍是 untracked，因此 Git 本身不会检查其全文；额外使用上述全文尾随空白扫描补足该限制，没有更改 Git state。

## Scope exclusions and skipped checks

- 未访问 PostgreSQL；C1/C2 真实组合事务、锁和 drift 验证属于 C3 Task 4。
- 未调用、导入或配置 Provider/LLM/OpenRouter；未创建或持久化 digest。真正压缩属于 Package E。
- 未调用 Telegram 网络或任何外部系统；未写 Memory/RAG/vector/Redis/LangGraph/checkpoint/audit/outbox/AgentRun。
- 未修改 C1/C2、schema/migration、API/route、permission、Mini App、部署配置或 Git state。
- 未运行全 backend suite；本任务按简报运行 C1/C2/C3 相关 unit corpus，Package-level integration/full regression 留给 Task 4/5。

## Remaining risks

- 当前 pending 证据来自 InMemory UoW；真实 PostgreSQL 在同一事务和并发漂移下的组合语义尚未由 Task 4 证明。
- opaque pending composite 只是 Package E 的未来内部输入，不包含 compressor、digest、token/provider/timeout budget，也不能被当作可消费的最终模型 context。
- 本任务必须经过 fresh independent review；在复审通过前不能标记 Task 3 final PASS，更不能宣称 C3 或 Package C 完成。

## Cleanup

- 无临时数据库、外部记录、Provider/Telegram 调用、缓存或持久化 digest。
- 无新增临时脚本、测试数据文件或后台进程。
