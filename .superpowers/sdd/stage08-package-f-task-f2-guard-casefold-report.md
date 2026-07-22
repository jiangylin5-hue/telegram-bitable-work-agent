# Stage08 Package F — F2 outbound guard casefold 修复报告

## Status

- Result: `IMPLEMENTED`
- Scope: F2 evaluator-only outbound prompt guard 与四类真实 fixture marker mutation 覆盖
- External calls: `NONE`
- Environment access: 未读取、未设置 `STAGE08_F_ENV_FILE`，未读取 `.local`

## Changed files

- `backend/scripts/stage08_real_provider_evaluation.py`
- `backend/tests/unit/test_stage08_real_provider_evaluation.py`
- `.superpowers/sdd/stage08-package-f-task-f2-guard-casefold-report.md`

## What changed

1. 将四类受限内容提取为 fixture 内唯一 marker 常量，并由 hidden field、expired group、revoked group、deleted RAG fixture 共同引用，避免测试 marker 与真实 fixture 值漂移。
2. `_OutboundPromptGuard` 对最终 outbound prompt 和每个 forbidden marker 分别执行 Unicode-safe `casefold()` 后再比较，关闭大小写绕过。
3. answer leak 检查同步对 marker 执行 `casefold()`，保持 marker 改为真实 fixture 大小写后原有泄漏检测语义不变。
4. 新的参数化 mutation 测试逐个将四类真实 marker 注入可见 `title`：
   - deterministic fake 路径固定以首个 failure label `outbound_prompt_unsafe` 失败；
   - F1 `OpenRouterStage08AnalysisProvider` 使用相同 child-local guard，MockTransport 证明 guard 在 transport 前阻断；
   - 两条路径的 strict DTO 均不包含 marker、prompt 或 answer 字段；
   - 全程保持现有 E5 runtime deadline、telemetry、fixture isolation 和 safety environment 行为。

## Verification

```text
python -m pytest backend/tests/unit/test_stage08_real_provider_evaluation.py backend/tests/unit/test_stage08_openrouter_analysis_provider.py -q
42 passed in 19.88s
```

该命令包含完整 12-case offline spawned matrix、四类 marker 的 fake/F1 双路径 mutation，以及 F1 adapter 既有 transport-before-call 契约测试。

```text
python -m compileall -q backend/scripts/stage08_real_provider_evaluation.py backend/tests/unit/test_stage08_real_provider_evaluation.py backend/app/services/stage08_openrouter_analysis_provider.py backend/tests/unit/test_stage08_openrouter_analysis_provider.py
PASS
```

```text
git diff --check -- backend/scripts/stage08_real_provider_evaluation.py backend/tests/unit/test_stage08_real_provider_evaluation.py
PASS
```

## Boundaries preserved

- 未调用 OpenRouter、Telegram、webhook 或部署。
- 未新增/修改 public API、schema、permission、migration 或 default provider wiring。
- 未生成 raw prompt/response artifact。
- 未更改 12-case manifest、spawn isolation、最多 2 并发、hard timeout、strict child/parent DTO、fail-closed env 或 Telegram dry-run 设计。

## Gate

实现修复已完成；F3 仍需等待 fresh independent reviewer 对四类真实 marker 与 transport-before-call 行为给出 `PASS`，且无 Critical/Important finding。
