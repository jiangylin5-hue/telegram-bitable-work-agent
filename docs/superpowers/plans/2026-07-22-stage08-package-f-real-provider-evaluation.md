# Stage08 Package F 真实 Provider 评测实施计划

## Order

1. F1：实现并单测 `OpenRouterStage08AnalysisProvider`，确保实际 HTTP timeout 由 E5 deadline/budget 控制，默认 API path 不启用它。
2. F2：实现 Stage08 12-case synthetic manifest、子进程隔离 runner 与严格 redacted result DTO；先跑 deterministic/unit/timeout mock 用例。
3. F3：用显式 ignored local env 进行一次 bounded real OpenRouter run；仅保留 aggregate/case ID/boolean/fixed code evidence，不存 prompt/response。
4. F4：独立 review，更新 F acceptance；Milvus 仅基于真实规模/SLO 证据另行决策，不在 F1–F3 引入。

## F1 files

- Create `backend/app/services/stage08_openrouter_analysis_provider.py`
- Create `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
- Modify only Stage08 collaboration dependency wiring where evaluator injection requires it

### Required tests

- no key/invalid input returns unavailable without network;
- HTTP timeout/5xx/non-JSON/shape drift returns fixed unavailable/failed-safe outcome;
- explicit `httpx.Timeout` does not exceed min(remaining E5 deadline, provider budget);
- prompt includes only F synthetic authorised projection and is never persisted/logged;
- output answer/citation/action strict validation; provider cannot form sealed draft intent.

## F2 files

- Create `backend/scripts/stage08_real_provider_evaluation.py`
- Create `backend/tests/unit/test_stage08_real_provider_evaluation.py`
- Create `project-docs/08-implementation/evidence/stage08-package-f-real-provider.md` after real run only

### Required runner behavior

- exactly 12 static case IDs; subprocess isolate; <=2 concurrency; parent revalidates redacted child DTO;
- force dry-run/disabled external action env; fixture is new in-memory synthetic workspace only;
- hard timeout kills child, fixed safe failure code, no sibling cancellation;
- no local output artifact or raw print; report JSON contains only permitted fields;
- real invocation requires explicit `STAGE08_F_ENV_FILE`; absence is a clean non-network failure.

## F3 exact boundary

Before external calls, run F1/F2 unit tests. Load only the ignored `.local` env in child process, call OpenRouter for at most 12 synthetic cases, then remove env. Do not reuse Telegram credentials or send messages. If a case fails a gate, record evidence and do not auto-tune prompts.

## Acceptance / review

Fresh reviewer must separately verify transport timeout (not merely E5 cooperative post-return checking), raw-data redaction, parent/child isolation and absence of Telegram/provider write. A successful run is `evidenced-pending`, not production deployment.
