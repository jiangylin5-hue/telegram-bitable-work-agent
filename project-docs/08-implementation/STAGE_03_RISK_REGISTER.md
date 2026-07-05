# Stage 03 Risk Register

## Status

- Document status: active risk register
- Scope: Stage 03 主要风险、影响、缓解措施、验收检查和退出条件。
- Current Progress: 2026-07-06 风险登记已建立并随代码实施继续跟踪；Task 3 已验证 invalid secret、allowlist blocked、malformed payload 不产生业务行，Task 4 已验证 binding conflict 不猜客户、`telegram_inbox` scope filtering/order/limit/redaction，真实服务器/DNS/webhook 和 Redis worker 风险仍待后续验收。

## 1. Risk Table

| Risk | Impact | Mitigation | Acceptance Check |
| --- | --- | --- | --- |
| Webhook secret leaked | Unauthorized requests may enter system | store secret only in server env; never log or return it | invalid secret test; log review |
| Bot Token committed | Bot account compromise | never write real token to repo; use env only | `git diff` review before commit |
| Real Telegram reply accidentally sent | Customer confusion or operational risk | `TELEGRAM_SEND_MODE=dry_run`; no send handler in Stage 03 | tests/config review |
| Redis job duplication | duplicate processing | idempotency key and message unique update id | duplicate worker test |
| Redis unavailable | backlog and stale inbox | PostgreSQL outbox remains pending/retryable | bridge failure test |
| Worker direct table mutation | audit/permission bypass | worker must call service/UOW | code review and tests |
| Customer misbinding | message attributed to wrong customer | no LLM guessing; explicit binding rules; conflict handling | binding tests |
| Unbound messages invisible | operators miss customer messages | `needs_manual_binding` inbox state visible to internal roles | inbox view test |
| Tencent Cloud security group too open | exposed DB/Redis | expose only 80/443 publicly | deployment checklist |
| Full raw update exposed | privacy leakage | normalize fields; view redaction | view redaction test |
| Stage03 scope expands into provider/LLM | schedule and safety risk | source-of-truth out-of-scope gate | scope review before implementation |
| Migration breaks Stage02 | regression | additive migration and full test suite | full `pytest tests -v` |

## 2. Blockers

Stage 03 implementation must pause if:

- User requests real provider write without new stage confirmation.
- User requests real Telegram send without new stage confirmation.
- Tencent Cloud credentials or DNS information are unavailable for staging rehearsal.
- Webhook secret or Bot Token appears in git diff.
- Stage 02 full test suite regresses and the failure is not understood.

## 3. Scope Creep Watchlist

These requests are valuable but not Stage 03 first batch:

- OpenRouter intent extraction.
- LangGraph Triager Agent.
- Telegram reply sending.
- Recharge draft generation from message intent.
- Account inventory allocation from Telegram message.
- Provider sandbox gateway.
- Mini App or Web dashboard.

Each should be recorded as a Stage 04+ candidate unless user explicitly changes Stage 03 source of truth.

## 4. Acceptance Criteria

- Every high-impact risk has a mitigation.
- Stage 03 acceptance checklist references the relevant risk checks.
- Final Stage 03 closeout lists unresolved risks and skipped tests.
