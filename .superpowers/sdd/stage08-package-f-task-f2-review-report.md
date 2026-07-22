# Stage08 Package F — F2 独立审查报告

## Status

- Result：`HOLD`
- Findings：`0 Critical / 3 Important / 0 Minor`
- Gate：三个 `Important` 均会使 F3 的真实 Provider 结果产生不可解释或虚假的质量证据，因此在修复并复审前阻断 F3。
- Review mode：只读、纯离线；未设置或读取 `STAGE08_F_ENV_FILE`，未调用 OpenRouter、Telegram、webhook、部署或其他外部系统。

## Findings

### Important I-01：生命周期/隐藏信息 Case 没有验证 outbound prompt，当前门禁可产生安全假阳性

F-B02 要求真实模型只看到授权、最小、当前有效的合成上下文。但当前 evaluator 的 `no_hidden_leak` 只在模型返回的 `view.answer` 中搜索四个 marker（`backend/scripts/stage08_real_provider_evaluation.py:601-604`）；`citation_current` 只检查 ordinal 排序、范围以及是否非空（`606-616`），没有证明 prompt 不含隐藏字段、过期/撤销群投影或删除的 RAG source，也没有把 citation label/lifecycle 与 case 预期绑定。离线 `_DeterministicAnalysisProvider` 更是在 `analyse()` 中直接丢弃 `material`（`299-306`）。

因此，如果后续 C3/D4/权限投影发生回归，把受限 marker 放进 outbound prompt，但模型没有原样复述，该 Case 仍可得到 `no_hidden_leak=true`；如果 group/RAG Case 只引用普通业务表 evidence，也可满足当前的“非空 citation”条件。现有 12/12 结果不能作为 F-B02 的证明。

本次用 process-local 探针只检查布尔结果、未打印 prompt：当前实现的 `hidden_field`、`group_freshness`、`rag_lifecycle` 三个 Case 均为 `forbidden_seen=False`，说明被测主链目前没有观察到实际泄漏；问题在于 evaluator/test 没有把这个事实纳入门禁，无法防止未来假阳性。

**Required remediation：** 在子进程内、实际 F1 prompt 构造/HTTP 调用之前增加 evaluator-only guard，校验该 Case 的禁用 marker 不存在于 outbound prompt；只把固定 bool/failure label 带回父进程。deterministic fake 也必须经过同一 guard，并增加一个故意注入受限材料后必须失败的 mutation test。不得跨进程或写文件保存 prompt。

### Important I-02：`provider_metadata_present` 表示“已配置”而非“实际调用”，真实调用覆盖率会被高报

`_select_provider()` 在 env 可用时立即设置 `configured=True`（`906-930`），结果 DTO 随后无条件写入 `provider_metadata_present=selection.configured`（`646-661`）。它没有记录 `analyse()` 是否实际进入、是否得到 Provider outcome，也没有 usage metadata presence 的真实来源。

离线 process-local 探针得到：

```text
revoked_scope calls=0 reported_provider_metadata=True status=failed
budget_cancel calls=0 reported_provider_metadata=True status=cancelled
```

这两类 Case 正确地应在 Provider 前终止，但 F3 aggregate 会把它们统计为 Provider metadata present。与此同时 E 的 `AgentRun.usage_summary.provider_calls` 仍固定为 `0`。于是当前证据既可能把未调用的 Case 算成“Provider 存在”，又无法证明真正调用了多少次；这与 F3 的真实多 Case 覆盖、provider/usage presence 指标以及 Package E final review 留下的真实计数要求不一致。

**Required remediation：** 使用仅进程内的受控 tracking wrapper/callback，分别记录 Provider attempted/completed 与 usage metadata presence；父进程只接收 bool/count，不接收 model、token、cost、request ID 或响应正文。对于预期在 Provider 前终止的 Case，必须明确 `provider_invoked=false` 且仍能通过；其余真实模型 Case 必须以真实调用布尔值参与 gate。相关 process-local `AgentRun` 计数也不得继续与实际调用相反。

### Important I-03：offline fake 与 F1 真实输出合同不等价，真实模式下至少三个固定 Case 的预期结构性不可满足

离线 fake 为 `provider_unavailable` 直接返回 unavailable，并为 `policy_deny`、`safe_replay` 生成 F1 明确禁止的 `draft_update + draft_intent`（`307-339`）。真实 F1 adapter 的 output schema 只允许 `read_only/general_advice/deny`，且始终 `draft_intent=None`。但 F2 real mode 没有 case-specific fault/strategy：`_select_provider()` 对所有 Case 都构造同一个正常 OpenRouter adapter；`provider_unavailable` 没有 timeout/5xx/shape-drift 注入，`policy_deny` 的 command 还被构造成 `requested_action=read_only`（`851-873`），`safe_replay` 却只接受 `draft_pending`（`148-160`）。

离线使用与 F1 相同的合法 action/无 draft-intent 形状探测，结果为：

```text
provider_unavailable + healthy read_only -> completed / terminal_unexpected
safe_replay + deny or read_only          -> denied / replay_invalid / draft_count=0
policy_deny + deny                       -> completed / terminal_unexpected
```

也就是说，即使 OpenRouter 完全遵守 F1 系统提示与 schema，F3 仍会把这些 harness 合同矛盾记成模型质量失败；`provider_unavailable` 也没有实际覆盖要求的 transport failure。现有 12/12 fake 结果不能推导 real mode matrix 可解释。

**Required remediation：** 明确每个 Case 的真实 Provider 策略并在 child 内固定：`provider_unavailable` 应通过 F1 adapter 的 process-local fault transport 验证 timeout/5xx/shape drift；`policy_deny` 应发送真实的受控写请求并以 F1 可表达的拒绝结果验收；`safe_replay` 要么明确作为“不调用真实 Provider”的既有 E replay Case，要么把预期改为符合 F1 首发“不 materialize provider draft”的安全终态。DTO 需显式证明哪些 Case 预期/实际调用 Provider，避免把 deterministic coordinator Case 伪装成真实 LLM Case。

## Blocking questions 核查

1. **固定 manifest / 无 caller prompt：部分 PASS。** 恰好 12 个静态 ID，parent selector 只有 `case_id`，raw query/fixture/UUID 都在 child 创建；但 real-mode Case 语义存在 I-03。
2. **fresh spawn / <=2 并发 / 单 Case timeout：PASS。** `spawn` 每 Case 新进程，`ThreadPoolExecutor` 最大值严格限制为 2，超时仅 terminate/kill 当前 child，后续 Case 继续。
3. **严格 DTO / parent revalidation：PASS。** 精确字段集合、strict Pydantic、静态 enum、case identity 复核、subclass/model_construct/extra field 拒绝均存在；异常正文没有进入 DTO。
4. **安全 env / 无显式 env 不触网：PASS。** child 强制 Telegram dry-run、Provider write/notification/full prompt/full response disabled；缺少显式 `STAGE08_F_ENV_FILE` 时在构造 F1 provider 前返回固定 `configuration_missing`。
5. **fake seam / E5 deadline：部分 PASS。** fake 通过同一个 `analysis_provider` dependency port 注入，F1 deadline probe 使用同一 E5 runtime control；但 fake 能产生 F1 不允许的 decision，导致 I-03。
6. **无 public contract / artifact：PASS。** F2 文件没有新增 public API、schema、permission、migration 或输出文件；CLI 仅 stdout redacted JSON。

## Fresh verification

1. F2 + F1 + 既有 isolation evaluator 离线回归：

   ```text
   python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage06_live_llm_skill_quality_eval.py
   63 passed in 34.36s
   ```

2. 编译检查：

   ```text
   python -m compileall -q scripts/stage08_real_provider_evaluation.py tests/unit/test_stage08_real_provider_evaluation.py
   exit 0
   ```

3. 额外离线 process-local probes：
   - 当前三个生命周期/隐藏 Case 的实际 F1 prompt marker 检查均为 false，但 evaluator 未将其纳入 verdict（I-01）。
   - `revoked_scope`、`budget_cancel` 的 Provider 调用数为 0，而 DTO 报告 metadata present（I-02）。
   - 使用 F1 合法 action/no-draft shape 时，三个 Case 出现固定 harness mismatch（I-03）。

## Skipped / Remaining

- 按审查 brief 未运行真实 OpenRouter；未读取、设置或打印任何 `.local` env/密钥。
- 未发送 Telegram、未确认草稿、未更新 webhook、未部署。
- 未运行 full backend/repository/UI suite；三个阻断项均可由聚焦离线测试与源码证明，无需扩大回归范围。
- 未修改业务实现或测试；本轮只新增独立审查报告。

## Final verdict

F2 的进程隔离、DTO 白名单、并发/硬超时和 fail-closed env 基础是成立的，但当前 12-case runner 不能可靠证明 outbound prompt 安全、不能准确统计真实 Provider 调用，并且 offline fake 的若干预期与 F1 真实输出合同结构性冲突。结论为 `HOLD`；关闭 I-01～I-03 并通过独立复审前，不应启动 F3 外部调用。
