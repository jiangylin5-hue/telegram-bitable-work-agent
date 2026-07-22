# Stage08 F3 通用建议动作合同与可审计证据修复决定

## Status

- Decision status: approved implementation remediation
- Date: 2026-07-22
- Trigger: Package F final review `HOLD / 0 Critical / 1 Important`. R2 proved empty citations but did not prove that `general_advice` used an allowed action.
- Scope: F1 evaluator adapter、F2 synthetic evaluator/redacted internal DTO、F3 R3 versioned evidence. No public API/schema, business permission, default Provider, Telegram or deployment change.

## Contract completion

For `intent = general_advice`, accepted model output is exactly:

```text
action in {general_advice, deny}
AND citation_ordinals = []
```

`read_only` is invalid even with empty citations. It must fail closed through the same fixed invalid-input/unavailable route. A controlled `deny` is safe and valid, so the F2 terminal expectation must accept the corresponding safe `denied` terminal.

## Redacted action evidence

R3 must prove the allowed action without retaining raw answer or response. The internal evaluator may add a fixed enum projection only:

```text
analysis_action = none | read_only | general_advice | deny
```

Rules:

- `none` when Provider was not invoked, fault-unavailable, or no safe decision is available;
- parent DTO accepts only the exact enum; no arbitrary tool/action name;
- aggregate may count the enum; evidence may show the enum per fixed case;
- this is an evaluator-only, non-sensitive proof and does not create public API/audit/AgentRun persistence.

## Required implementation and tests

1. F1 uses the same sealed command snapshot already used for citation checks to reject `general_advice + read_only` and any nonempty citation; `deny` must be citation-empty.
2. F2 mock/fake/real adapter tests cover allowed `general_advice`, allowed `deny`, rejected `read_only`, rejected nonempty citation, and terminal mapping for deny.
3. Strict child/parent DTO and redacted evidence expose only `analysis_action` enum, never answer/prompt/response.
4. Preserve all F2 guards, telemetry, isolation, timeout, dry-run and historical F3/R2 evidence unchanged.

## R3 gate

After independent offline review passes, run one new separately named synthetic-only, max-12-case, single-batch real Provider evaluation. It must not overwrite F3/R2, retry automatically, send Telegram, call webhook, deploy or write externally beyond bounded OpenRouter inference.
