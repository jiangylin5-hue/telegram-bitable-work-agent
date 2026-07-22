# Stage08 Package F — F3 通用建议空引用修复独立审查报告

## Status

- Review result：`PASS`
- Findings：`0 Critical / 0 Important / 0 Minor`
- Review mode：全新独立离线审查；未读取或设置 `STAGE08_F_ENV_FILE`，未读取 `.local`，未调用 OpenRouter、Telegram、webhook、部署或其他外部系统。
- R2 gate：已满足代码与离线复核前置门槛；R2 仍未在本审查中执行。

## 审查结论

本次修复把原 F3 `general_advice -> citation_invalid` 暴露出的合同缺口同时编码进真实 F1 模型输入和严格输出校验。模型侧合同明确要求：输入 intent 为 `general_advice` 时只能选择 `general_advice` 或受控 `deny`，且 `citation_ordinals` 必须为 `[]`；任何 `deny` 也必须返回空引用。adapter 在严格 JSON parse 后复用构造 prompt 时取得的同一份内部 command snapshot，对 general-advice command 的非空引用以及 deny action 的非空引用统一 fail closed 为固定 `unavailable / invalid_input`，没有把原始回答、ordinal、异常正文或 Provider response 写入结果、日志或持久化对象。

普通事实的证据规则没有被放宽：ordinal 仍必须处于本次 safe evidence 的 `1..evidence_count` 范围，既有严格 schema、answer 上限、禁止 draft field/value、固定 telemetry 和 transport deadline 逻辑继续生效。

## Blocking checks

### 1. 模型可见合同：PASS

- `_SYSTEM_PROMPT` 明确写出 general-advice intent 和 deny action 的空引用规则。
- user payload 增加固定 `citation_policy`，只包含规则字符串，不增加 prompt、answer、ID、token、request ID 或异常正文的记录面。
- 现有 `__slots__`、安全 `repr` 和无 logger 路径保持；聚焦测试继续验证授权 prompt 只进入受控 transport body，不进入 outcome、`repr` 或日志。

### 2. strict parse 后的一致性校验：PASS

- `_build_prompt` 对 command 只做一次内部 snapshot，并把该 snapshot 的 intent 与 evidence count 一并返回给 adapter 的后置校验。
- general-advice command 携带任意非空 citations 时固定拒绝；deny action 携带任意非空 citations 时固定拒绝。
- 普通 fact 的超范围 citation 仍由 `ordinal > evidence_count` 校验拒绝；`AnalysisDecision` 的有序、去重和 `1..12` 结构合同仍由原 validator 保持。

### 3. F1/F2 实际 seam 与 runner 保证：PASS

- F1 测试覆盖：模型可见空引用指令、general-advice 空引用成功、general-advice 非空引用失败、deny 空/非空两条路径，以及普通事实合法/越界引用。
- F2 测试不是绕过 adapter 的自由 mock：它把真实 `OpenRouterStage08AnalysisProvider` 注入既有 E Coordinator dependency seam，并通过 `httpx.MockTransport` 覆盖空引用完成与非空引用安全降级；同时断言 telemetry、redacted DTO、hidden-leak 和 external-side-effect 门禁。
- 12-case 离线矩阵仍使用固定 manifest、每 case fresh `spawn`、父进程严格 DTO 重验、最大 2 并发、child/parent 强制 safety environment、无直接写入和无外部副作用门禁。

### 4. 两个 env 专项测试的排除：PASS

本次离线命令只排除了两个会直接读取或设置 `STAGE08_F_ENV_FILE` 的既有测试：缺失显式 env 的 runner 行为，以及从临时 env 文件构造 real Provider/deadline probe。它们没有被删除或改写。其本次修复所依赖的等价底层保证仍由已执行的 F1 测试覆盖：无 key 时不构造网络调用，真实 `httpx.Timeout` 继续取 E5 剩余 deadline 与 provider budget 的较小值；F2 的 safety environment、dependency seam、spawn/DTO/telemetry 测试也全部保留并执行。因此此次排除符合 no-env 审查边界，没有形成修复盲区。

### 5. 历史证据与 R2 边界：PASS

- 旧证据 `project-docs/08-implementation/evidence/stage08-package-f-real-provider.md` 仍记录 `HOLD`、`Retry count=0`、`11/12` 和 `general_advice -> citation_invalid`，未出现 R2 或调绿改写。
- 当前 SHA-256：`314AEB2C87FD7E41F52E3A671CE930CD896FF9F8B116CBF70FAF138DB9ABB8D1`。
- 旧证据最后写入时间为 `2026-07-22 06:06:05`，早于 adapter 修复与修复报告，和“历史 evidence 保持不变”的任务记录一致。

## Fresh verification

```text
python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py -k "not test_absent_explicit_env_file_is_clean_non_network_result and not test_real_provider_selection_uses_the_same_e5_remaining_deadline"
46 passed, 2 deselected in 20.98s

python -m pytest -q tests/unit/test_stage08_real_provider_evaluation.py::test_complete_twelve_case_offline_matrix_runs_through_isolated_children
1 passed in 17.40s

python -m compileall -q app/services/stage08_openrouter_analysis_provider.py scripts/stage08_real_provider_evaluation.py tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py
exit code 0
```

## Exact F3 R2 gate

本报告满足 R2 所需的 `PASS / 0 Critical / 0 Important` 离线审查门槛。下一步只允许执行一次新的受控 R2 批次，并同时满足以下条件：

1. 仅使用既有 12 个固定 synthetic cases，最多 2 并发、每 case 既有硬超时，只有 F1 OpenRouter 推理可出网。
2. Telegram 始终 `dry_run`；不得调用 webhook、draft confirmation、Provider write、notification write 或部署。
3. 使用显式受控本地 env 只完成 Provider 构造，不读取、输出或持久化密钥值。
4. R2 结果写入新的版本化 evidence 文件；不得修改、覆盖、删除或重命名原 11/12 evidence。
5. 不自动重试。若 R2 仍有任一合同失败，原样保留新的脱敏失败 evidence，并继续 `HOLD`，不得降低 gate 或修改期望来调绿。

## Final verdict

`PASS / 0 Critical / 0 Important / 0 Minor`。F3 R2 的离线前置门槛已满足；本审查本身没有执行任何真实 Provider 批次或其他外部写入。
