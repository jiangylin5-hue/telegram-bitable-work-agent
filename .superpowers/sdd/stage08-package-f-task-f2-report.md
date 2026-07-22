# Stage08 Package F — F2 任务报告

## Status

- Result：`PASS（实现完成，等待独立 review）`
- Scope：仅实现 12-case 合成清单、每 case 子进程隔离 runner、严格脱敏 DTO 与 offline fake-provider 测试。
- External actions：未发起 OpenRouter/HTTP、Telegram、webhook、通知、Provider 写入或部署调用。
- Contract changes：无 public API、schema、migration、permission 或默认 Provider wiring 变更。

## Changed files

- `backend/scripts/stage08_real_provider_evaluation.py`
  - 新增恰好 12 个固定 case ID：`visible_fact`、`hidden_field`、`revoked_scope`、`general_advice`、`group_freshness`、`rag_lifecycle`、`provider_unavailable`、`policy_deny`、`draft_pressure`、`budget_cancel`、`safe_replay`、`multilingual`。
  - 父进程的 case selector 只有静态 `case_id`；query、合成记录、群投影、知识来源及内部 UUID 只在子进程创建和使用。
  - 每个 case 使用 `spawn` 新建子进程和新的 `InMemoryStage06PlatformUnitOfWork`，最多两路并发；单 case 硬超时只 terminate/kill 该子进程，超时 Queue 使用 `cancel_join_thread`，后续 case 继续。
  - 子进程仅返回严格 dict 投影；父进程按精确字段集合重新构造 `RedactedCaseResult`，拒绝子类、`model_construct` 伪造、附加字段、错误 case ID 和非固定 failure label。
  - DTO 仅含静态 case ID、终态、固定失败标签、五项安全门禁、fixture 门禁、citation/draft count、latency bucket 以及 Provider/usage metadata presence 布尔值；无 prompt、answer、业务正文、UUID、token、request ID 或异常正文。
  - 强制 `TELEGRAM_SEND_MODE=dry_run`、Provider/Provider-write/notification disabled、full prompt/response retention disabled。
  - 未配置显式 `STAGE08_F_ENV_FILE` 时，在构造 F1 Provider 前返回固定 `configuration_missing` 脱敏结果，不发生网络调用。
  - real-mode 仅从显式 env 文件读取三个 OpenRouter 配置键，并将 F1 adapter 的 `remaining_deadline_seconds` 绑定到同一个 E5 runtime control 的真实剩余 deadline。
  - `_DeterministicAnalysisProvider` 只可由 Python 内部 `provider_mode="deterministic_fake"` 测试入口选择；CLI `main()` 固定使用 real mode，不存在环境变量或命令行 fake 开关。fake provider 通过 `Stage08CollaborationDependencies.analysis_provider` 注入，与 F1 使用同一个 E Coordinator port，且不会把 fake 计作真实 Provider metadata。
  - runner 不写文件；CLI 仅输出允许字段构成的 JSON。
  - 按既有 backend script 模式补入 `BACKEND_ROOT` bootstrap，可直接执行 `python scripts/stage08_real_provider_evaluation.py`，不依赖调用者预设 `PYTHONPATH`。
- `backend/tests/unit/test_stage08_real_provider_evaluation.py`
  - 新增固定 manifest、DTO 白名单、伪造 child payload、timeout cleanup、并发上限、后续 case 连续执行、安全 env、显式 env fail-closed、E5 deadline 绑定、F1/E injection seam、真实 spawn 与完整 12-case offline 矩阵测试。

## TDD evidence

1. 首轮 RED：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py
   ImportError: cannot import name 'stage08_real_provider_evaluation' from 'scripts'
   ```

   原因是 F2 runner 尚不存在，属于预期 feature-missing RED。

2. E5 deadline 绑定 RED：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py::test_real_provider_selection_uses_the_same_e5_remaining_deadline
   TypeError: _select_provider() got an unexpected keyword argument 'runtime_control'
   ```

   随后把 F1 timeout probe 绑定到同一 E5 runtime control，聚焦用例转绿。

## Verification

1. F2 focused：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py
   15 passed in 20.48s
   ```

2. 完整 12-case offline subprocess matrix：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py::test_complete_twelve_case_offline_matrix_runs_through_isolated_children
   1 passed in 17.73s
   ```

   该用例实际使用 `spawn`，结果为 12/12 case passed、0 failed、0 timed out、all gates passed。

3. F2 + F1 + 既有 Stage06 isolation evaluator fresh 回归：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage06_live_llm_skill_quality_eval.py
   63 passed in 20.20s
   ```

4. compile：

   ```text
   python -m compileall -q scripts/stage08_real_provider_evaluation.py tests/unit/test_stage08_real_provider_evaluation.py
   exit 0
   ```

5. 工作树差异检查：

   ```text
   git diff --check
   exit 0
   ```

   仅输出共享 dirty worktree 已有文件的 LF/CRLF 提示，无 whitespace error。针对三个 F2 新文件另以 `git diff --no-index --check` 检查，只有同类换行提示，无 whitespace diagnostics；其 exit `1` 是 untracked 文件与 `NUL` 存在内容差异的正常结果，不代表 whitespace failure。

6. 缺少显式 env 的直接 CLI fail-closed：

   ```json
   {"exit_code":1,"case_count":12,"passed_count":0,"failed_count":12,"provider_metadata_case_count":0,"usage_metadata_case_count":0,"configuration_missing_count":12}
   ```

   这是预期的 clean non-network 失败：12 个隔离 child 均返回固定 `configuration_missing`，没有构造 F1 Provider 或发起 HTTP。

## Skipped / Remaining

- 未调用真实 OpenRouter；真实调用属于 F3。
- 未生成 `project-docs/08-implementation/evidence/stage08-package-f-real-provider.md`；该文件只能在真实 F3 run 后创建。
- `usage_metadata_present` 已进入严格 DTO，但 F1 当前 outcome 不提供可脱敏 usage presence，因此 F2/Fake 为 `false`；F3 如需证实 usage presence，必须在既定合同内补足对应安全证据，不可回传 token/cost/request ID 值。
- 未发送 Telegram、未确认草稿、未更新 webhook、未部署。
- 未修改 API、schema、migration、权限或生产默认 `UnavailableAnalysisProvider`。
- 无临时输出文件或测试数据需要清理；pytest 自身临时目录由 pytest 管理。
