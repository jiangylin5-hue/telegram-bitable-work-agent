# Stage 04 Local Acceptance Audit

## Status

- Document status: active local acceptance audit
- Scope: Stage 04 Tasks 1-9 本地实现、自动化测试、迁移链和文档一致性审计。
- Current Progress: 2026-07-07 本地验收审计已补齐并追加权限/错误契约/customer existence/list filters/inactive replacement/idempotent disable/view row-level safety/config fail-closed/confirm boundary/outbox bridge 复核。Final local preflight reran `pytest tests -q` with 172 passed / 17 skipped after the staging compose send-mode gate test was added; `alembic upgrade head --sql` reached `20260706_0011` and emitted `COMMIT`; token/private-key scan found no Telegram Bot token, private key or OpenRouter `sk-` key. Task 10 Tencent Cloud staging rehearsal remains pending and requires separate confirmation before any staging env change or real Telegram send.

## 1. Audit Boundary

本文件只回答一个问题：Stage 04 在进入 staging rehearsal 前，本地实现和文档是否已经逐项对齐 Stage 04 真源、开发计划和验收清单。

本文件不声明 Stage 04 最终验收通过，因为 Stage 04 Source Of Truth 的 Exit Gate 仍要求：

- 腾讯云 staging 部署 Stage 04 代码。
- 在 staging PostgreSQL 执行迁移。
- 通过 API 创建真实 binding。
- 让真实 Telegram 新消息在绑定后进入 `telegram_inbox` 的 bound 状态。
- 人工确认后向 allowlisted test chat 真实发送一条 Telegram test message。
- 记录 redacted staging evidence。

本地审计期间没有执行：

- staging server 变更。
- staging `.env` 修改。
- Telegram `sendMessage` 真实调用。
- 客户群发送。
- OpenRouter / LLM 调用。
- Meta、卡台、充值 provider 写入。
- 资金或账户外部操作。

## 2. Source Documents Audited

| Document | Audit purpose | Result |
| --- | --- | --- |
| [Stage 04 Source Of Truth](STAGE_04_SOURCE_OF_TRUTH.md) | Scope、out-of-scope、Bitable endpoint、Exit Gate | aligned locally; staging gate pending |
| [Stage 04 Implementation Plan](STAGE_04_IMPLEMENTATION_PLAN.md) | Tasks 0-10 implementation steps | Tasks 0-9 checked locally; Task 10 pending |
| [Stage 04 Acceptance Checklist](STAGE_04_ACCEPTANCE_CHECKLIST.md) | Requirement-by-requirement status | local rows updated with fresh evidence |
| [Stage 04 Module Index](STAGE_04_MODULE_INDEX.md) | Complex module doc coverage | module docs indexed and detailed |
| [Stage 04 API Contract](STAGE_04_API_CONTRACT.md) | Binding and send request API contract | routes and schemas implemented locally |
| [Stage 04 Database And Migration Design](STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md) | `telegram_send_requests` model/migration | offline migration chain verified |
| [Stage 04 Security And Permission Design](STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md) | permission, allowlist, fail-closed behavior | tests cover local safety gates |
| [Stage 04 Test Plan](STAGE_04_TEST_PLAN.md) | automated and manual verification split | automated suite fresh; manual staging pending |
| [Stage 04 Operations Runbook](STAGE_04_OPERATIONS_RUNBOOK.md) | staging execution procedure | still requires user confirmation before use |
| [Stage 04 Risk Register](STAGE_04_RISK_REGISTER.md) | remaining safety and operational risks | unchanged risks remain active |
| [Stage 04 Progress](STAGE_04_PROGRESS.md) | subphase evidence trail | updated with this audit record |
| [Stage 04 module docs](modules/) | detailed function behavior and edge cases | five complex module docs present |

## 3. Local Verification Commands

| Command | Date | Result | Notes |
| --- | --- | --- | --- |
| `cd backend; pytest tests/integration/test_stage04_binding_management.py -v` | 2026-07-07 | 15 passed | Added direct coverage for unknown customer, list filters, invalid status filter, inactive replacement, idempotent disable, unauthorized binding list/disable and missing-binding not-found error |
| `cd backend; pytest tests/integration/test_stage04_test_send.py -v` | 2026-07-07 | 13 passed | Added direct coverage for schema text limit, confirm=false, confirm-time allowlist drift, unauthorized request/confirm, missing request not-found error and failed Telegram worker response path |
| `cd backend; pytest tests/integration/test_stage03_redis_streams_bridge.py -v` | 2026-07-07 | 4 passed | Includes Stage04 evidence that `telegram.test_send_requested` projects `request_id` to Redis fields |
| `cd backend; pytest tests/unit/test_stage04_bitable_views.py tests/unit/test_bitable_views.py tests/unit/test_stage03_telegram_inbox_view.py -v` | 2026-07-07 | 17 passed | Added direct Stage04 coverage for hiding unbound/conflict inbox and send request rows from customer-scoped actors |
| `cd backend; pytest tests/unit/test_stage04_deploy_compose.py -v` | 2026-07-07 | passed | Verifies api/outbox-bridge/worker can use server-side `TELEGRAM_SEND_MODE=restricted_test`; migrate remains dry-run |
| `cd backend; pytest tests -q` | 2026-07-07 | 172 passed / 17 skipped | Skips are online PostgreSQL smoke tests requiring `STAGE02_ONLINE_DATABASE_URL` |
| `cd backend; alembic upgrade head --sql` | 2026-07-07 | reached `20260706_0011`; emitted `COMMIT` | Offline migration chain only; no staging DB touched |
| `git diff --check` | 2026-07-07 | passed with CRLF warnings only | No whitespace errors |
| Token/private-key scan | 2026-07-07 | no matches | Searched for Telegram Bot token shape, private key headers and OpenRouter `sk-` keys in `backend`, `deploy` and `project-docs`; broad database URL scan only matched documented local/disposable/example URLs |
| Stage04 stale-status scan | 2026-07-07 | no active stale status found | Matches are historical progress-log descriptions of earlier scans/counts, not current status fields |

## 4. Task-By-Task Audit

| Task | Stage 04 requirement | Local status | Evidence | Staging status |
| --- | --- | --- | --- | --- |
| Task 0 | Documentation package | passed locally | Stage04 source, plan, SDD, BDD, API, DB, security, test, runbook, risk, progress, acceptance and module docs exist | no staging dependency |
| Task 1 | Permission actions and binding schemas | passed locally | `test_stage04_binding_management.py`: manager/sales permission and schema validation covered | no staging dependency |
| Task 2 | Binding management service and API | passed locally | create/list filters/disable/customer existence/inactive replacement/idempotent disable/list permission/conflict/audit covered by binding management tests | API-created binding still needs staging verification |
| Task 3 | Bitable views | passed locally | `telegram_bindings`, `telegram_send_requests`, `telegram_intent_queue` view contract tests plus customer-scoped row filtering for unbound/conflict inbox and send request rows | real staging rows still pending |
| Task 4 | New-message binding | passed locally | `chat_user`, `chat`, `user`, inactive and no-history-rewrite tests | real webhook after API-created binding still pending |
| Task 5 | Intent placeholder without LLM | passed locally | bound message becomes `intent_ready`; unbound stays review; no service draft audit | staging evidence still pending |
| Task 6 | Restricted test send config | passed locally | config tests require token and allowlist for `restricted_test`; unrestricted modes rejected; compose test verifies runtime services can opt into server-side `restricted_test` | staging env config still pending |
| Task 7 | `telegram_send_requests` model and migration | passed locally | metadata tests; Alembic offline SQL reaches `20260706_0011` | staging migration still pending |
| Task 8 | Test send request and confirm API | passed locally | request, confirm, confirm=false, confirm-time allowlist drift, permission denial, blocked target and invalid state tests | real API call in staging still pending |
| Task 9 | Telegram Bot client and worker handler | passed locally | client redaction tests; outbox bridge `request_id` projection; worker sent, blocked, failed and idempotency tests | real allowlisted Telegram send still pending |
| Task 10 | Tencent Cloud staging rehearsal | pending | not executed in this local audit | pending by design; requires user confirmation |

## 5. Exit Gate Audit

| Exit Gate Item | Local audit result | Evidence | Remaining gap |
| --- | --- | --- | --- |
| Binding management API has permission checks, audit and tests | met locally | binding management focused tests, including unauthorized create/list | staging API call evidence |
| `chat`, `user`, `chat_user` active binding resolves new messages | met locally | new-message binding regression tests | real webhook message after API-created binding |
| inactive binding is ignored | met locally | inactive binding regression test | staging confirmation optional |
| conflict does not guess customer | met locally for API conflict | active conflict returns 409 and audit | inbox conflict display needs real-data confirmation if conflict appears in staging |
| new message after binding becomes bound in `telegram_inbox` | met locally by ingestion/view contract | new-message binding + view tests | real staging `telegram_inbox` evidence |
| intent placeholder creates state/audit without LLM | met locally | intent placeholder and worker runtime tests | staging evidence and env check |
| `telegram_send_requests` supports request/confirm/blocked/sent/failed | met locally | send request API permission/state tests and worker sent/blocked/failed tests | real `sent` state in staging after allowlisted send |
| real send only to allowlisted test chat and requires confirmation | met locally by API and worker checks | confirm creates outbox only; worker rechecks allowlist | staging must prove allowlist is server-side and target is test chat |
| staging records binding and test-send evidence | not met | not executed | Task 10 |
| full backend suite passes or skipped items are explained | met locally | 172 passed / 17 skipped; skips require `STAGE02_ONLINE_DATABASE_URL` | disposable online DB smoke remains skipped |
| no customer group send, LLM call, provider write or funds movement | met locally | config and code path boundaries; no external operation executed in audit | staging run must record the same negative evidence |

## 6. Bitable Endpoint Audit

| Workflow | Endpoint / state | Local audit result |
| --- | --- | --- |
| Create binding | `telegram_bindings` active row + `ops_audit_events` | covered locally |
| Disable binding | `telegram_bindings.status = inactive` + audit | covered locally |
| Binding conflict | API conflict response and audit; inbox conflict state reserved | covered locally for API conflict |
| New message after binding | `telegram_inbox.customer_id` and `binding_status = bound` | covered locally; staging pending |
| Intent placeholder | `telegram_intent_queue.intent_status` | covered locally |
| Test send requested | `telegram_send_requests.status = pending_confirmation` or `blocked` | covered locally |
| Test send confirmed | `telegram_send_requests.status = confirmed` + outbox event + Redis stream `request_id` field | covered locally |
| Test send blocked | `telegram_send_requests.status = blocked` | covered locally at API and worker layers |
| Test send sent | `telegram_send_requests.status = sent` + response summary + audit | covered locally with fake client; real send pending |
| Test send failed | `telegram_send_requests.status = failed` + safe error + audit | covered locally with fake failed Telegram response |

## 7. Skipped Tests

The 17 skipped tests are online PostgreSQL smoke tests gated by `STAGE02_ONLINE_DATABASE_URL`.

This does not prove staging acceptance. It means the local backend suite did not run disposable online PostgreSQL smoke coverage in this audit. Stage 04 still needs:

- disposable DB smoke rerun when `STAGE02_ONLINE_DATABASE_URL` is available, or
- explicit acceptance that Tencent Cloud staging migration evidence is sufficient for this phase.

## 8. Remaining Risks

- Binding mistakes can route future Telegram messages to the wrong customer until disabled.
- Restricted test send is still a real Telegram write once staging is configured.
- Test chat allowlist and bot token must stay server-only and redacted from docs.
- Intent placeholder must not be presented as real AI classification.
- Stage 04 is not production HA and does not include monitoring, alerting, PITR, backup validation or production cutover.

## 9. Local Audit Conclusion

Stage 04 Tasks 1-9 are locally ready for Task 10 staging rehearsal. This is a local readiness conclusion only, not final Stage 04 acceptance.

The next gate is explicit user confirmation for Tencent Cloud staging deployment/migration and one allowlisted Telegram test send.
