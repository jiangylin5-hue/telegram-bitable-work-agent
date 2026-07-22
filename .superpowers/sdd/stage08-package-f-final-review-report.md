# Stage08 Package F 最终独立审查报告

## Status

- Result：`PASS`
- Findings：`0 Critical / 0 Important / 0 Minor`
- Review scope：F1 opt-in OpenRouter adapter、F2 固定 12-case 隔离评测器、general-advice/action-verdict 修复、初版 F3 / R2 / R3 版本化证据及 Package F 计划与 BDD。
- Review mode：全新、只读、严格离线；未读取或设置 `STAGE08_F_ENV_FILE`，未读取 `.local` 或任何 env 内容，未调用 OpenRouter、Telegram、webhook、部署、draft confirmation、notification write 或 Provider write。

## Findings

### Critical

无。

### Important

无。

### Minor

无。

## Blocking checks

### 1. F1 opt-in、deadline 与 strict output：PASS

- `OpenRouterStage08AnalysisProvider` 没有进入默认 API/router wiring；`Stage08CollaborationDependencies.analysis_provider` 仍默认为 `UnavailableAnalysisProvider`。仓库内该 adapter 的构造引用只存在于 F evaluator 和离线测试。
- 真正的 `httpx` 调用使用 `min(E5 remaining deadline, CollaborationBudget.max_provider_time_ms)` 形成 transport timeout；零/无效剩余时间、timeout、HTTP error 和异常均映射为固定 unavailable outcome。
- Provider 返回值使用 `extra="forbid"`、strict Pydantic 模型，并再次通过 `validate_analysis_decision`。answer 长度、citation ordinal、action 和 `draft_intent=None` 边界保持成立，模型不能形成 draft field/value。
- prompt 只由 process-local sealed material 解封；adapter 不日志化、不持久化 raw material，`repr` 不含 key/prompt，事件 observer 只允许 invoked/completed/usage-presence，action observer 只在严格决策通过后投影固定 enum。

### 2. F2 固定矩阵、隔离、并发、DTO 与安全环境：PASS

- manifest 恰好包含 12 个静态 case ID；父进程输入只含固定 case ID，不能注入自定义 identity、prompt 或 fixture。
- 每个 case 使用新的 `spawn` 子进程和新的合成 in-memory fixture；`ThreadPoolExecutor` 的并发上限严格为 1..2，单 child hard timeout 只清理该 child，后续 case 继续运行。
- child 只返回 exact-field `RedactedCaseResult` dict；parent 在模型构建前后重验 exact field set、strict enum、case identity 和 case/action 语义。伪造对象、subclass、extra field、raw answer、任意 failure text 和合法 enum 的错误 case/action 组合均不能进入 passed batch。
- parent/child 均强制 Telegram `dry_run`、Provider/notification write disabled、完整 prompt/response retention disabled。无显式评测 env 时不会构造真实 Provider，也不会触网。
- outbound prompt guard 在 F1 transport 前以 `casefold()` 检查四类真实 fixture marker；deterministic fake 与 F1 MockTransport mutation 回归均证明受限 marker 会 fail closed 且 transport 不进入。

### 3. `general_advice` 与逐 case action 证明：PASS

- F1 对 `intent=general_advice` 只接受 `action in {general_advice, deny}` 且 citations 为空；`read_only + []`、任何非空 citation、deny+非空 citation 均固定 fail closed。
- evaluator 的 `_ALLOWED_PASSED_ANALYSIS_ACTIONS` 为全部 12 个 case 定义静态动作集合；`RedactedCaseResult` 与 parent `_validated_child_payload()` 均执行相同语义校验。
- 离线回归直接证明伪造 `general_advice/read_only/evaluation_passed=true` 被拒绝并转为 `provider_invocation_invalid`，不能贡献 `passed_count`；合法 `general_advice` 和受控 `deny` 保持可接受。
- R3 逐 case action 与静态合同一致：`read_only=5`、`general_advice=1`、`deny=2`、`none=4`；其中 `general_advice` case 明确为 `general_advice`，不再依赖 R2 中缺失的动作证据。

### 4. R3 单批结果与脱敏证据：PASS

- R3 task brief、执行报告与 evidence 对执行事实的记录一致：一个 bounded real Provider batch、固定 12 case、最大并发 2、无 retry、无 prompt tuning；未发现第二个 R3 artifact 或与该声明冲突的仓库证据。
- R3 evidence 为 `12/12 passed`、`0 failed`、`0 timed out`、`all_cases_passed=true`、`all_gates_passed=true`；Provider `9 invoked / 9 completed / 8 usage-present`。逐 case 行数、terminal、latency、citation、draft 和 action 汇总均自洽。
- 逐 case 表仅包含固定 case ID、枚举、布尔值和计数。独立扫描得到 `case_rows=12`，credential/Bearer/API key assignment、URL、UUID 等敏感值形态命中为 `0`；未发现 prompt、answer、fixture body、业务 ID、token/cost 数值、request ID、异常正文或原始 Provider response。
- “恰好一次、无重试”属于 task report/evidence 与仓库留痕一致的执行声明；仓库没有第三方不可变 Provider 调用审计，因此本结论不扩大为外部审计证明或生产稳定性证明。

### 5. 历史证据不可变性：PASS

- 初版 F3 `11/12 HOLD` evidence 当前 SHA-256：`314AEB2C87FD7E41F52E3A671CE930CD896FF9F8B116CBF70FAF138DB9ABB8D1`。
- R2 `12/12` evidence 当前 SHA-256：`788B0ED35416F97A31D3230E14995E1F9FF1605684A70C2A4BA6D13C59365FDE`。
- 两个值均与 R3 brief/report/evidence 记录一致；R3 使用独立新文件，没有覆盖或改绿历史失败证据。

### 6. 范围漂移与完成声明：PASS

- F1/F2/F3 的实现改动限定于 evaluator adapter、runner、离线测试、内部决策/报告和版本化 evidence；没有新增 Package F public API、schema、permission、migration 或默认 Provider wiring。
- R3 evidence 和执行报告明确声明不代表 Stage08 整体完成、真实 Telegram 发送、部署完成或生产就绪。阶段真源、BDD 和验收矩阵仍保留 F4 后更新门，不存在用本次 12-case 结果冒充生产验收的声明。
- Package F 之外仍需阶段级状态/验收矩阵一致性更新，以及后续服务器 env/secret、真实 PostgreSQL/pgvector/Redis、HTTPS/webhook、部署回滚/观测、受控 Telegram smoke 和生产权限审计；这些不构成本次 F1-F4 质量证据审查的阻断项。

## Fresh offline verification

在 `backend/` 下执行，仅排除两项会主动删除、设置或读取 `STAGE08_F_ENV_FILE` 的 env 专项测试：

```text
python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py tests/unit/test_stage08_collaboration_contracts.py tests/unit/test_stage08_collaboration_graph.py tests/unit/test_stage08_collaboration_service.py -k "not test_absent_explicit_env_file_is_clean_non_network_result and not test_real_provider_selection_uses_the_same_e5_remaining_deadline"
152 passed, 2 deselected in 21.40s
```

编译检查：

```text
python -m compileall -q backend/app/services/stage08_openrouter_analysis_provider.py backend/scripts/stage08_real_provider_evaluation.py backend/tests/unit/test_stage08_openrouter_analysis_provider.py backend/tests/unit/test_stage08_real_provider_evaluation.py
exit 0
```

独立 evidence 检查：

```text
R3 fixed case rows = 12
forbidden value-shape hits = 0
historical F3/R2 SHA-256 = expected values
```

## Skipped / unchanged

- 未运行两项会操作真实评测 env selector 的测试；其既有 F1/F2 离线证据保留，本次审查没有读取或设置该变量。
- 未重新运行真实 Provider；R3 要求单批、零重试，最终审查不得制造第二批外部调用。
- 未调用 Telegram、webhook、部署、draft confirmation、notification write 或 Provider write。
- 未运行 full backend、全迁移链、全 PostgreSQL、UI 或生产部署回归；本报告只关闭 Package F 的 F1-F4 质量证据审查，不替代 Stage08 总体验收。
- 未修改业务代码、测试、阶段真源、BDD、验收矩阵或历史 evidence；仅替换本最终审查报告。

## Final verdict

`PASS / 0 Critical / 0 Important / 0 Minor`。F1 opt-in transport adapter、F2 固定 12-case 隔离/脱敏 evaluator、general-advice/action 防伪闭环和 R3 版本化真实 Provider 合成证据相互一致，可以关闭 Package F 的当前质量证据范围。该 PASS 不等于 Stage08 整体完成、生产部署完成或真实 Telegram 上线验收。
