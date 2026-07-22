# Stage08 Package F — F1 独立审查报告

## Status

- Result：`PASS`
- Review scope：仅审查 opt-in `OpenRouterStage08AnalysisProvider`、F1 内部受控证据投影路径及其聚焦测试。
- Findings：`0 Critical / 0 Important / 0 Minor`
- Gate：未发现阻塞 F2 的 F1 问题；本结论不代表 F2/F3、真实 OpenRouter 调用或生产部署已验收。
- External actions：未发起网络、OpenRouter、Telegram、webhook、部署或其他外部系统调用。

## 审查范围

已直接阅读并对照：

- `.superpowers/sdd/stage08-package-f-task-f1-brief.md`
- `.superpowers/sdd/stage08-package-f-task-f1-report.md`
- `project-docs/08-implementation/STAGE_08_PACKAGE_F_QUALITY_BDD_AND_ACCEPTANCE.md`
- `docs/superpowers/plans/2026-07-22-stage08-package-f-real-provider-evaluation.md`
- `project-docs/08-implementation/decisions/STAGE_08_E5_PRODUCTION_COORDINATOR_EXECUTION_DECISION.md`
- `backend/app/services/stage08_openrouter_analysis_provider.py`
- `backend/app/services/stage08_retrieval_provider.py`
- `backend/app/runtime/stage08_collaboration_contracts.py`
- `backend/app/services/stage08_collaboration.py`
- `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`

## Blocking questions 核查

### 1. 默认 API 不可达，仅 F evaluator 可显式注入

`PASS`。生产依赖 `Stage08CollaborationDependencies.analysis_provider` 仍固定默认为 `UnavailableAnalysisProvider()`。对 `backend/app`、`backend/scripts` 及测试的静态搜索表明，`OpenRouterStage08AnalysisProvider` 只在其定义模块和 F1 单测中出现，没有被 API route、`main.py` 或默认 dependency wiring 导入。

### 2. 真实 HTTP 传输超时受 E5 deadline 和 Provider budget 双重限制

`PASS`。每次 `_post` 都显式接收 `httpx.Timeout(timeout_seconds)`，其中 `timeout_seconds = min(max(0, remaining_deadline_seconds()), max_provider_time_ms / 1000)`。同一 timeout 被直接传给 `httpx.Client.post`，不是仅在 HTTP 返回后检查耗时。聚焦测试实际检查 request extension 中 `connect/read/write/pool` 四项值，并覆盖 deadline 较小和 provider budget 较小两种情况。deadline 已归零时不调用 transport。

### 3. 错误和非法输出 fail closed，不泄露异常正文

`PASS`。

- 缺少 key/config、deadline 归零、timeout 和 HTTP error 统一返回无 decision 的固定 `analysis_provider_unavailable` outcome。
- 非法 private carrier、非 JSON、OpenRouter shape drift、多余字段、越界 citation、UUID answer 和非法 action 统一返回无 decision 的固定 `invalid_input` outcome。
- 实现中没有记录或将 caught exception 写入 outcome，Pydantic 严格配置启用 `hide_input_in_errors=True`。

### 4. 仅从密封的内部载体生成最小 prompt，无 raw 持久化或日志

`PASS`。Provider 先验证 `_Stage08ProviderInput -> analysis_material -> _Stage08PrivateMaterial`链路，检索证据仅能经由带模块内 issuer 的 `_Stage08PrivateEvidence` 受控投影。对外 prompt 仅包含 query、intent、requested action 和编号 evidence，不包含 workspace/employee/record/actor/idempotency 标识。Provider 无日志、审计、outbox 或数据库写入路径；`repr` 不包含 key 或输入正文，outcome 不包含 raw prompt/response/request ID/usage 值。

### 5. 模型输出无法生成草稿字段或值，也无法绕过 E3

`PASS`。Provider 输出 schema 只允许 `answer`、`citation_ordinals`和 `action`，且 action 仅可为 `read_only/general_advice/deny`；`extra="forbid"` 会拒绝 `draft_value`等额外内容。构造 `AnalysisDecision` 时 `draft_intent` 被硬编码为 `None`，因此模型输出不能形成密封草稿载体，也不会进入 E3 draft materialization 条件。

### 6. 修改仅限 F1

`PASS`。未发现 public API、schema、migration、permission、Telegram、webhook、部署或默认 Provider wiring 扩展；也未发起真实外部调用。`stage08_retrieval_provider.py` 的新增能力是一个 underscore 命名、仅进程内、只接受既有密封 evidence 的 F Provider 投影函数，与 F1 文档规定的内部受控解封路径一致。

## Fresh verification

1. 聚焦 F1 + E 合同/服务/图回归：

   ```text
   python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_service.py tests/unit/test_stage08_collaboration_graph.py
   100 passed in 1.97s
   ```

2. 编译检查：

   ```text
   python -m compileall -q app/services/stage08_openrouter_analysis_provider.py app/services/stage08_retrieval_provider.py tests/unit/test_stage08_openrouter_analysis_provider.py
   exit 0
   ```

3. 相关文件 whitespace 检查：

   ```text
   git diff --check -- backend/app/services/stage08_openrouter_analysis_provider.py backend/app/services/stage08_retrieval_provider.py backend/tests/unit/test_stage08_openrouter_analysis_provider.py
   exit 0
   ```

## Skipped / Remaining

- 未运行真实 OpenRouter 调用：属于 F3，且本审查 brief 明确禁止网络调用。
- 未审查 12-case manifest、子进程隔离、红线 DTO 和 aggregate metrics：属于 F2/F3。
- 未审查生产服务器 env、HTTPS/webhook、Telegram controlled smoke、观测、回滚或部署：不属于 F1。
- F2 仍需用独立子进程硬超时覆盖 `httpx` 单次 I/O timeout 不保证整个 case wall-clock 上限的边界；这是既有 F2 验收项，不是 F1 finding。
