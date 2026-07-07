# Stage 04 Risk Register

## Status

- Document status: active risk register
- Scope: Stage 04 binding operations、restricted test send、intent placeholder、staging risks。
- Current Progress: 2026-07-07 Stage04 local and staging mitigations are verified for permission checks, allowlist guard, response redaction, worker idempotency, fail-closed config, binding edge cases and test-send states. Staging proved bound inbox update `184365902`, sent request `05f46883-e4c7-4669-99cb-99a093629f70`, and post-test dry-run safety close. Production hardening remains out of Stage04 scope.

## 1. Risks

| Risk | Severity | Mitigation | Status |
| --- | --- | --- | --- |
| Wrong Telegram binding routes future customer messages to wrong customer | high | Active conflict checks, admin/manager-only API, audit every create/disable, no auto historical rewrite | mitigated locally and in staging test path; remains operational risk for future real bindings |
| Test send accidentally targets customer group | high | `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS`, human confirmation, worker re-check, customer group sends out of scope | mitigated locally and in staging private test chat path; keep customer groups out of allowlist |
| Bot token leaks through docs/logs/views | high | Server-only env, response redaction, no token in git, secret scans before acceptance | mitigated locally, final scan pending |
| Intent placeholder is mistaken for completed AI classification | medium | Use explicit `intent_ready`; no `service_drafts`; audit wording avoids "classified" | mitigated locally |
| Stage04 expands into UI/LLM/customer notification | medium | Source of truth out-of-scope and user confirmation required for scope change | open |
| Duplicate worker processing sends duplicate Telegram test message | high | Request status idempotency, outbox idempotency, worker checks `status=sent` before sending | mitigated locally |
| Staging env config permits unrestricted sending | high | Runtime validation rejects unrestricted send modes in production-like env | mitigated locally and in staging; post-test state restored to `TELEGRAM_SEND_MODE=dry_run` and allowlist cleared |
| Single-node staging does not represent production HA | medium | Record as production-readiness deferred risk | open |

## 2. Explicit Deferrals

These are not Stage 04 defects:

- No UI / Mini App。
- No LLM / OpenRouter。
- No LangGraph production Agent。
- No customer group send。
- No customer reply drafts。
- No historical replay。
- No provider writes。
- No production database readiness。

## 3. Risk Review Gate

Before Stage 04 acceptance:

- Every high risk must have either automated test evidence or manual staging evidence.
- Any unmitigated high risk must be listed in final acceptance report if one is created.
- Real test send evidence must state that no customer group send occurred.
