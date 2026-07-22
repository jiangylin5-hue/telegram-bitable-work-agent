# Stage08 F3 通用建议空引用合同修复决定

## Status

- Decision status: approved implementation remediation
- Date: 2026-07-22
- Trigger: F3 single bounded real Provider batch recorded `general_advice -> citation_invalid`; independent review classified it as a real quality failure, not an evaluator defect.
- Scope: F1 OpenRouter evaluator adapter、F2 synthetic case contract/tests 和 F3 R2 versioned evidence only. No public API, database schema, permission, default Provider, Telegram or deployment change.

## Product rule

当 command 的内部 intent 是 `general_advice` 时，回答不是基于内部业务事实，因而不得伪造或附带内部 evidence ordinal：

```text
intent = general_advice
-> action = general_advice 或受控 deny
-> citation_ordinals = []
```

模型可以选择安全拒绝；若选择 `general_advice`，非空 `citation_ordinals` 是合同违反，adapter 必须 fail closed，不能把该输出当成已通过的分析。

## 实现要求

1. F1 system/user payload 明确写出：当 intent 为 `general_advice`，返回 `citation_ordinals: []`，不得把任何 ordinal 作为通用建议依据。
2. F1 在严格 JSON parse 后，以内部 command snapshot 验证：
   - `general_advice` 的非空 citations 返回固定 unavailable/invalid-input outcome；
   - 普通 facts 的 citation 范围校验保持；
   - 不记录 prompt、answer、ordinal 原始响应或异常正文。
3. F2 的 `general_advice` fixture、fake 和 F1 mock output 必须覆盖：空引用成功、非空引用被 adapter 拒绝、`deny` 不伪造引用。
4. 修复后的 F3 只可创建新的版本化证据文件；2026-07-22 的原 `11/12` evidence 不得改写、覆盖或删除。

## 验收与外部调用门槛

- 先完成离线单元/runner 回归并获得新的独立 review `PASS / 0 Critical / 0 Important`。
- 然后以同样的 synthetic-only、最多 12 case、最多 2 并发、单次批次限制运行 F3 R2。
- Telegram 永远 dry-run；无 webhook、draft confirmation、Provider-write、部署或自动重试。
- 真实模型若仍违反合同，保留脱敏失败 evidence，不调低 gate 或修改旧证据。
