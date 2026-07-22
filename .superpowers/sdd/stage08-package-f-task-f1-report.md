# Stage08 Package F F1 任务报告

## Status

- Result：`PASS`
- Scope：仅实现 opt-in `OpenRouterStage08AnalysisProvider` 及聚焦单元测试。
- External actions：未发起任何真实 HTTP、OpenRouter、Telegram、webhook 或部署调用。

## Changed files

- `backend/app/services/stage08_openrouter_analysis_provider.py`
  - 新增显式注入的 OpenRouter-compatible analysis provider。
  - 只从构造参数接收 `api_key` / `base_url` / `model_name` 和 E5 剩余 deadline 回调，不读取或新增默认 env/config。
  - 每次 HTTP 调用显式传入 `httpx.Timeout(min(remaining E5 deadline, max_provider_time_ms))`。
  - 仅在进程内解封 command/provider material，对外 prompt 仅含 query、intent、requested action 和编号的已授权证据内容，不发送 workspace/employee/record/actor/idempotency 标识。
  - 模型输出使用 strict Pydantic shape；action 仅允许 `read_only` / `general_advice` / `deny`，因此 Provider 不能构造 `draft_intent`、field 或 value。
  - timeout/HTTP 错误统一返回 `analysis_provider_unavailable`；非 JSON、shape drift、非法引用、draft 输出统一返回 `invalid_input`。
- `backend/app/services/stage08_retrieval_provider.py`
  - 新增一个仅供 F Provider 使用的进程内受控检索证据投影函数；不新增公开 API、序列化能力或持久化路径。
- `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
  - 15 项聚焦单测，全部使用 `httpx.MockTransport`，无网络请求。

## Verification

1. `python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py`
   - Result：`15 passed in 1.37s`
2. `python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_service.py`
   - Result：`86 passed in 1.92s`
3. `python -m compileall -q app/services/stage08_openrouter_analysis_provider.py app/services/stage08_retrieval_provider.py tests/unit/test_stage08_openrouter_analysis_provider.py`
   - Result：exit `0`
4. `git diff --check`
   - Result：exit `0`；只有共享 dirty worktree 已有文件的 LF/CRLF 提示，无 whitespace error。

## Required behavior evidence

- no key：不解封、不调用 transport，返回 fixed unavailable。
- invalid private carrier：调用 transport 前 fail closed。
- timeout/5xx：fixed unavailable，无 decision。
- non-JSON/shape drift/draft action/extra draft value/UUID answer/超出当前证据序号：fixed invalid input，无 decision。
- bounded timeout：实测 HTTP request extensions 的 connect/read/write/pool 四项均为 `min(remaining, 20s)`。
- default wiring：`Stage08CollaborationDependencies().analysis_provider` 仍为 `UnavailableAnalysisProvider`。
- raw/private containment：provider 无 `__dict__`，repr/outcome/log 不含 key 或输入正文，outbound 不含内部 ID/actor/idempotency。

## Skipped / Remaining

- `ruff` 未运行：当前 Python 环境未安装 `ruff` (`No module named ruff`)。
- 本任务未做真实 OpenRouter 调用；那属于 F3。
- 本任务未实现 12-case runner/子进程隔离/汇总指标；那属于 F2。
- 本任务未更改 schema、migration、public API、permission、Telegram 或部署。
