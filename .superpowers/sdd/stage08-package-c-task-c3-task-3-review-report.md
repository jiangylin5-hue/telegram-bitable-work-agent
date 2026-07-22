# Stage08 Package C3 / Task 3 独立安全与契约复审报告

## Status

- Review result: `PASS / 0 Critical / 0 Important / 0 Minor`
- Review scope: 仅复审 C3 Task 3 的 `group_compression_pending` 私有交接、消费前重组与失败关闭语义。
- Scope boundary: 未修改实现、测试、schema、API、数据库、Git 或任何外部系统；本报告不宣布 C3 或 Package C 完成。

## Findings

### Critical

- 无。

### Important

- 无。

### Minor

- 无。

## Contract and security evidence

1. **真实高窗口与真实状态算术**
   - `test_high_window_returns_opaque_pending_view_without_materializing_body` 使用 49 个受控投影，每个 500 code points，合计 `24,500`；严格大于 C3 direct 的 `24,000`，且仍在 C2 的 `120 fragments / 60,000 chars / 500 per fragment` 上限内。
   - 待压缩 safe view 保留 C2 的 `group_status`、窗口条数与 `group_compression_required=True`，但将 `group_rendered_fragments`、`group_rendered_chars` 固定为 0，`total_content_chars` 仅计当前 C1 internal evidence。`CompositeContextView` 的严格验证也强制 pending 状态不得携带已渲染群内容。
   - 待压缩 renderer 只在 C1 仍为 `internal_evidence` 时输出当前 C1；无 C1 或仅 general-advice marker 时返回 `None`。测试断言所有 49 个受控群片段都不出现在渲染结果、safe JSON、私有 `repr` 或 JSON 序列化错误中。

2. **不读取群正文、不压缩、不持久化、无外部调用**
   - `compose_stage08_context` 在 C2 `compression_required=True` 时直接进入 `_compose_pending_result`；该路径不调用 C2 materializer。
   - `_render_pending_composite` 只重建 C1 pack 和 C2 window/lineage；它不调用 materializer。测试用 monkeypatch 将 materializer 置为立即失败，覆盖 compose、正常 pending render、漂移和 pending-to-direct 分支，结果均未触发该函数。
   - 独立静态检查确认 `_compose_pending_result`、`_render_pending_composite`、`_pending_window_lineage_is_current` 均不引用 materializer、digest、provider、Telegram 或 outbox。
   - production 文件的禁止边界扫描无匹配：`Message/raw_text/raw_caption/normalized_text/TelegramBot/sendMessage/httpx/requests/OpenRouter/Provider/LLM/digest/APIRouter/add_api_route/Redis/pgvector/LangGraph/MemoryItem/AgentRun/audit/outbox`。
   - 任务测试的 side-effect 计数覆盖 records、memory、audit、outbox、agent runs、drafts、notifications、group projections；pending compose/render 前后保持不变。

3. **私有表面与泄漏检查**
   - `_Stage08CompositeContext` 和 `_Stage08CompositeBlock` 使用 `__slots__`；私有 `repr` 仅输出状态和 block 数量。safe view 为严格、冻结、`extra=forbid` 的计数型 Pydantic contract，不包含正文、scope 值、UUID、actor、authority、handle 或 renderer 字段。
   - service 模块的非下划线定义只有两个预期消费入口：`compose_stage08_context`、`render_stage08_composite_context`；其余对象是私有类型或 safe-view contract。
   - `json.dumps(composite)` 明确失败；相关错误文本和 `repr` 均不包含群正文、workspace/customer/project/binding/mapping 标识或 actor id。

4. **消费前 lineage 与权限漂移关闭**
   - pending renderer 要求 composite actor 与原 opaque authority 的完整 frozen `Actor` 值相同，并再次校验 actor 类型及 `plan.actor_user_id`。
   - 它重建当前 C1 pack 和当前 C2 window，并比较原/新 C2 safe view、authority nonce、mapping、投影 handle 序列及选择数；任一不一致返回 `None`。
   - 自动化用例覆盖 projection、source type、mapping version、workspace member、Telegram binding、customer/project relation、retention、C1 view 和同一 user id 但不同 role 的 actor 漂移，以及伪造 window view、伪造 handle 和 pending-to-direct 替换。均为 fail-closed，且 materializer 不会被调用。
   - 额外独立对抗检查按真实 C2 编辑模型操作：将一个 active projection 标为 `superseded`，为同一 `source_message_id` 写入 version 2 的新 active projection（仍保持 49 x 500 的窗口规模）。旧 pending composite 渲染结果为 `None`，证明 versioned edit 会因 projection handle lineage 改变而关闭。

5. **direct 回归**
   - direct 路径保持现有 C1-first、随后 D6 group header 的顺序；`test_direct_composition_merges_c1_then_group_in_deterministic_order` 与完整 C1/C2/C3 单元回归均通过。

## Commands and results

```powershell
Push-Location backend
python -m pytest tests/unit/test_stage08_context_composition_service.py -q -W error
```

Actual: `36 passed in 1.98s`.

```powershell
Push-Location backend
python -m pytest tests/unit/test_stage08_context_composition_contracts.py tests/unit/test_stage08_context_composition_service.py tests/unit/test_stage08_context_contracts.py tests/unit/test_stage08_context_service.py tests/unit/test_stage08_group_context_contracts.py tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage08_group_context_service.py -q -W error
python -m compileall -q app/runtime/stage08_context_composition_contracts.py app/services/stage08_context_composition.py
```

Actual: `194 passed in 2.01s`; compileall exit `0` with no output.

> Review brief 中列出的 `tests/unit/test_stage08_group_context_authority.py` 与 `tests/unit/test_stage08_group_context_window.py` 当前不存在，原命令因此报告 `file or directory not found`，未被记为通过。通过文件清单核对后，已运行当前仓库实际承载这两类覆盖的 group-context contracts/ingestion/service 回归集，如上所示。

Additional checks:

- `PENDING_PATH_STATIC_BOUNDARY: pass`：对三个 pending 私有函数的 `inspect.getsource` 断言均通过。
- `C2_VERSIONED_EDIT_DRIFT: fail-closed without materialization`：真实 versioned-edit 形态的手工对抗复现通过。
- 禁止依赖扫描无匹配；仅检测到预期的两个消费函数和两个 safe-view contract class。
- `git diff --check` 对已跟踪 scoped 路径无问题；这两个 C3 production 文件在当前共享 worktree 仍是 untracked，Git 不会检查其全文，已以 compileall、pytest、禁止依赖扫描补足该限制。

## Scope exclusions and remaining work

- 未访问 PostgreSQL；C3 Task 4 仍需以 disposable local PostgreSQL 验证 C1/C2 组合重读、事务与漂移。
- 未调用或配置 Provider/LLM/OpenRouter、Telegram、Redis、RAG/vector、LangGraph、Memory persistence、audit/outbox 或部署。
- Task 5 的 package-level independent review 与 Package C handoff 仍未执行。

## Conclusion

在 Task 3 的已批准范围内，pending 分支满足“如实报告待压缩、绝不读取或输出群正文、仅保留当前有效 C1、任一 lineage/权限漂移失败关闭”的契约；复审结论为 `PASS`。这不构成 C3、Package C、Package E/F、真实 LLM 评测或生产部署完成声明。
