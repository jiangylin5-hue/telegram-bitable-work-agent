# Stage08 Package F — F3 general-advice action remediation 独立离线复核报告

## Status

- Review result: **HOLD**
- Critical: **0**
- Important: **1**
- Minor: **0**
- R3 gate: **blocked**；修复 I-01 并完成独立复核前，不应执行新的真实 Provider batch。
- Review boundary: 纯离线、只读代码与证据复核；未读取或设置 `.local` / evaluator env，未调用 OpenRouter、Telegram、webhook、部署或任何外部写入。

## Findings

### I-01 — general-advice 的动作只被记录，没有进入父进程与批次通过判定

位置：

- `backend/scripts/stage08_real_provider_evaluation.py:249-272`
- `backend/scripts/stage08_real_provider_evaluation.py:651-660`
- `backend/scripts/stage08_real_provider_evaluation.py:719-778`
- `backend/scripts/stage08_real_provider_evaluation.py:1206-1235`

`RedactedCaseResult` 目前只验证 `analysis_action` 属于固定枚举，并仅要求非 `none` 动作必须伴随 `provider_completed=true`。`_validated_child_payload()` 会据此接受子进程结果；`_execute_synthetic_case()` 的 failure labels 与 `passed` 计算没有验证 general-advice 的动作必须是 `general_advice | deny`；`_batch_result()` 又直接信任 `evaluation_passed`。

因此，一个字段集合完全合法、没有原文泄露、但语义为以下组合的子进程 payload 会被父进程接受并使批次通过：

```text
case_id=general_advice
terminal_status=completed
analysis_action=read_only
evaluation_passed=true
failure_labels=[]
all safety gates=true
```

独立最小复现结果：

```text
parent_accepts= True
case_passed= True
batch_passed= True
```

同理，若动作 observer 接线漂移，`general_advice + completed + analysis_action=none` 也没有 fail-closed 语义门禁。当前 F1 adapter 本身确实会把真实 `general_advice + read_only` 判为 `invalid_input`，现有 mock 测试也能通过；但 R3 evaluator 的职责是独立证明真实批次使用了允许动作，不能只依赖被评对象恰好没有回归。否则 R3 evidence 即使明确投影出 `read_only`，仍可能同时宣称 `12/12 passed`，无法关闭触发本次修复的 Important finding。

建议最小修复：在 strict result validator 或父进程 verdict 重算边界加入 case/action 语义约束，至少要求已通过的 `general_advice` 结果满足 `analysis_action in {general_advice, deny}`；`read_only` 与 `none` 必须 fail closed。补充直接构造/父进程重验测试，证明合法枚举但错误 case/action 组合不能进入 passed batch。保留故障、未调用和无安全 decision 路径的 `none` 语义，但这些路径不得伪装成已通过的 general-advice 成功终态。

## Blocking-check results

1. **F1 sealed command / action-citation contract: PASS**
   - `_build_prompt()` 从同一个 `_command_snapshot(command)` 同时派生 outbound intent 与返回的 `command_intent`。
   - general-advice 仅接受 `general_advice | deny` 且引用为空；`read_only` 和非空引用均走固定 `invalid_input` fail-closed。
   - fact citation ordinal 上界校验保持存在；`deny` 的非空引用同样被拒绝。
2. **严格枚举与动作 telemetry: PARTIAL / blocked by I-01**
   - child/parent DTO 字段集合严格，`analysis_action` 仅允许 `none | read_only | general_advice | deny`，没有 raw content carrier。
   - F1 只在 strict payload 与 `AnalysisDecision` 都校验成功后调用 observer；invalid/fault/not-invoked 路径维持 `none`。
   - 但父进程不校验 case/action 语义，无法把“投影到错误但枚举合法的动作”转成失败。
3. **general-advice terminal / read-only rejection: PARTIAL / blocked by I-01**
   - terminal allowlist 已允许 `completed | denied`，mock seam 证明当前 adapter 的 read-only 输出会 degraded/fail。
   - evaluator 自身仍接受语义伪造的 passed read-only child result，故门禁不完整。
4. **回归、隔离、证据完整性: PASS**
   - F1/F2 + collaboration contracts/service/graph 离线回归通过。
   - 独立 12-case spawned deterministic matrix 通过。
   - 初版 F3 evidence SHA-256 仍为 `314AEB2C87FD7E41F52E3A671CE930CD896FF9F8B116CBF70FAF138DB9ABB8D1`，与既有基线一致。
   - R2 evidence SHA-256 为 `788B0ED35416F97A31D3230E14995E1F9FF1605684A70C2A4BA6D13C59365FDE`；文件时间早于本次 action-contract decision，未见本任务改写迹象。

## Verification

- Focused offline suite, with all three env-mutating tests deliberately deselected to honor this review boundary: `137 passed, 3 deselected`.
- Spawned deterministic 12-case matrix: `1 passed`（测试内部断言 `12/12`）。
- `python -m compileall` for the two changed Python implementation files: passed.
- No external calls or business writes were executed.

## Conclusion

F1 的 action/citation 修复本身正确，动作投影也保持严格脱敏；但 evaluator 尚未让该动作参与可信 verdict。由于这正是 R3 必须新增的可审计证明，本轮为 `HOLD / 0 Critical / 1 Important / 0 Minor`。修复 I-01 后应重新做一次纯离线独立复核；在复核 PASS 前不得启动 R3 real Provider batch。
