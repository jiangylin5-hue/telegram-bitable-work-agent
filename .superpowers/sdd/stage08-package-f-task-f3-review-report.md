# Stage08 Package F — F3 真实 Provider 脱敏证据独立审查报告

## Status

- Result：`HOLD`
- Findings：`0 Critical / 1 Important / 0 Minor`
- Review mode：严格离线、只读实现与既有证据；未读取或设置 evaluator env，未读取 `.local`，未调用 OpenRouter、Telegram、webhook、部署或其他外部系统。
- Fresh verification：F1/F2 聚焦离线回归 `42 passed in 20.21s`。

## 结论摘要

本次 F3 证据的脱敏字段、12-case 计数和 Provider 调用计数内部一致；证据也诚实保留为 `11/12`、`all_gates_passed=false`、`HOLD`，没有把真实失败改写成验收通过。当前实现仍保留 F2 的固定 synthetic manifest、每 case 独立 `spawn`、最多 2 路并发、严格父子 DTO、child 内安全环境和受限 HTTP adapter 边界。

唯一失败 `general_advice -> citation_invalid` 是现行已批准质量合同下的有效行为失败，不是 evaluator-contract defect。它同时暴露了 F1 adapter 未把“通用建议不得引用内部业务事实”明确编码进模型指令和输出一致性校验的缺口，因此 Package F 继续 `HOLD`。

## Findings

### Important I-01：真实模型为 `general_advice` 返回了引用，违反已批准的无业务引用合同；F1 尚未显式约束该条件

Package F BDD 对 `general_advice` 的要求是“没有业务事实时明确通用建议，不伪造引用”；Stage08 总体真源还要求内部资料不足时必须标明未依据内部资料。F2 evaluator 将这一要求确定性实现为：普通事实 case 必须有当前引用，而 `general_advice` 的 `view.citations` 必须为空。该判断不依赖自由文本相似度，也没有读取或推断原始回答。

本次脱敏结果只足以证明：`general_advice` 以 `completed` 结束、Provider 确实 invoked/completed、其余安全门禁均为 true，但 `citation_current=false` 且固定标签为 `citation_invalid`。结合 evaluator 的唯一分支，可以确认该 safe view 出现了非空引用；不能据此推断引用 ordinal、引用正文、answer 或模型原始响应。

这不是 evaluator 自行增加的新规则。相反，当前 F1 `_SYSTEM_PROMPT` 只要求使用编号 evidence 并返回 `citation_ordinals`，没有说明 `action=general_advice` 时引用必须为空；严格 payload 也允许 `general_advice` 携带任意范围内 ordinal。于是模型生成了 schema 合法、但业务语义不合格的组合，runner 正确将其记录为质量失败。

该问题为 `Important` 而非 `Critical`：本批次没有隐藏信息泄漏、直接写入或外部 side effect 的证据，且默认生产依赖仍未启用 F1 adapter；但它阻断 F3/Package F 质量验收。

**最小下一步：**

1. 在 F1 system prompt 明确：当 intent/action 为 `general_advice` 或输入只含 `general_advice` policy marker 时，`citation_ordinals` 必须为空，并在回答中说明未依据内部业务资料。
2. 在 F1 adapter 的 process-local 输出一致性校验中拒绝 `action=general_advice` 且引用非空的 payload，继续映射为固定 `invalid_input`，不得把引用带入 safe view。
3. 增加纯离线测试：`general_advice + empty citations` 通过；`general_advice + non-empty citations` fail closed；事实型 `read_only` 的当前引用合同保持不变。
4. 修复和独立复审通过后，另建版本化证据执行一次新的 bounded synthetic real Provider batch。不得覆盖、删除或改绿本次 `11/12` 历史证据；仅靠 validator 把结果变成 degraded 也不等于质量通过。

## Blocking questions 核查

### 1. 脱敏与内部一致性：PASS

- 固定 12 个 case，`11 passed + 1 failed + 0 timed out = 12`。
- terminal 计数 `6 completed + 1 draft_pending + 1 degraded + 2 denied + 1 failed + 1 cancelled = 12`。
- latency bucket 计数 `4 under_250ms + 4 under_5s + 4 over_5s = 12`。
- 9 个预期进入 Provider 的 case 均为 `provider_invoked=true` 且 `provider_completed=true`；其中受控 503 fault case 无 usage，另外 8 个 case 为 usage presence，因此 `9/9/8` 与逐 case 表一致。
- 持久化 evidence/report 未出现 UUID、Bearer/key、token/cost 数值、request ID、prompt/answer 正文、异常正文或原始 Provider response。env 文件路径是 brief 要求的 command boundary，不包含 env 值。

### 2. F2 保证保持情况：PASS，但需区分证据与执行声明

**源码与离线测试可直接证明：**

- parent selector 只有固定 `case_id`；synthetic workspace、记录、群投影和 source 在 child 内创建。
- 每 case 使用 fresh `spawn` 进程；父级并发参数严格限制在 1–2；单 child 超时只清理该进程。
- child payload 只允许 `RedactedCaseResult` 精确字段，父进程重新做 strict model、字段集合和 case identity 校验。
- parent 在启动 child 前、child worker 在运行 case 前都调用 `_force_safety_environment()`；Telegram 为 `dry_run`，Provider write、notification、full prompt/response retention 强制关闭。
- runner 使用内存 UoW；唯一真实网络出口是 F1 OpenRouter-compatible HTTP POST。runner/adapter 源码没有 Telegram send、webhook 或部署调用路径。

**既有执行记录所声明、但本次离线复审无法从外部审计系统独立证明：**

- 实际批次没有发送 Telegram、没有 webhook/deployment/draft confirmation/Provider write。
- `Retry count=0`，未执行第二批次，且运行后没有修改 prompt、routing、case expectation 或实现来调绿。

这些声明与当前源码、脱敏结果、任务报告及文件中保留的失败完全一致，未发现反证；但仓库中没有不可变的外部调用审计日志，因此不应把它们表述成独立第三方审计证明。

### 3. `general_advice` 失败性质：有效质量/行为失败

- evaluator gate 与已批准 BDD 一致；不是评测器把合法业务引用误判为非法。
- 失败反映模型行为不符合通用建议的引用语义，同时暴露 F1 prompt/adapter 条件约束未编码完整。
- 不读取 raw response 也足以得出上述合同结论；不得推测模型具体说了什么或引用了哪条 evidence。

### 4. Gate 状态与重试：HOLD 保持正确

- 当前 evidence 清楚记录 `Batch exit code=1`、`Retry count=0`、`all_cases_passed=false`、`all_gates_passed=false`。
- 任务报告同样记录只执行一次真实批次、未重试、未自动调 prompt/路由/期望。
- 现有证据不能标记为 F3 acceptance、Package F complete 或 production readiness。

## Fresh verification

```text
python -m pytest -q tests/unit/test_stage08_openrouter_analysis_provider.py tests/unit/test_stage08_real_provider_evaluation.py
42 passed in 20.21s
```

另对 F3 evidence/report 做了固定敏感形态扫描；唯一命中是“未保存 prompt/answer/token/request ID”的说明文字，没有实际敏感值或业务正文。

## Skipped / unchanged

- 未运行真实 OpenRouter 或任何网络调用。
- 未读取、设置或打印 `STAGE08_F_ENV_FILE`、`.local` 或密钥。
- 未调用 Telegram、webhook、部署、draft confirmation 或 Provider write。
- 未修改 F1/F2 实现、F3 evidence 或 F3 task report；仅新增本独立审查报告。
- 未运行 full backend/repository/UI suite；本审查结论由 F1/F2 聚焦离线测试、当前源码和已记录脱敏 evidence 充分支持。

## Final verdict

F3 真实批次本身执行边界清楚、脱敏证据自洽且诚实保留失败，但 `general_advice` 未满足已批准的“无内部业务引用”质量合同。结论为 `HOLD / 0 Critical / 1 Important / 0 Minor`。先完成 F1 条件化 citation 约束与离线复审，再生成新的版本化真实批次；当前 `11/12` 证据必须原样保留。
