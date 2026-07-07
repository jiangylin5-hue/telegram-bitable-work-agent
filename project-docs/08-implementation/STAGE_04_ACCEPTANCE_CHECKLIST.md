# Stage 04 Acceptance Checklist

## Status

- Document status: final acceptance checklist
- Scope: Stage 04 文档、binding management、new-message binding、intent placeholder、restricted test send 和 staging 验收。
- Current Progress: 2026-07-07 Stage 04 在已确认范围内完成 staging 验收。Full backend suite passed with 172 passed / 17 skipped; Tencent Cloud staging ran commit `360d376`, migration reached `20260706_0011`, API-created binding made real Telegram update `184365902` appear as `bound` and `intent_ready`, restricted test send request `05f46883-e4c7-4669-99cb-99a093629f70` reached `sent`, and staging was closed back to `TELEGRAM_SEND_MODE=dry_run`.

## 1. Acceptance Boundary

Stage 04 验收：

- Stage 04 文档包完整且一致。
- Binding management API。
- Binding create/disable/conflict audit。
- New messages resolve `chat` / `user` / `chat_user` binding。
- Historical messages are not rewritten。
- Intent placeholder without LLM。
- `telegram_send_requests` table and state machine。
- Restricted test send to allowlisted test chat only。
- Bitable views: `telegram_bindings`, `telegram_send_requests`, `telegram_intent_queue`, updated `telegram_inbox`。
- Tencent Cloud staging evidence。

Stage 04 不验收：

- UI / Mini App。
- Customer group sending。
- Customer reply drafts。
- OpenRouter / LangGraph。
- Real provider writes。
- Funds movement。
- Production cutover。

## 2. Documentation Acceptance

| Requirement | Status | Evidence |
| --- | --- | --- |
| Stage 04 decisions recorded | passed | `STAGE_04_SOURCE_OF_TRUTH.md` |
| Implementation plan exists | passed | `STAGE_04_IMPLEMENTATION_PLAN.md` |
| SDD exists | passed | `STAGE_04_SDD.md` |
| BDD exists with planned test mapping | passed | `STAGE_04_BDD.md` |
| API contract exists | passed | `STAGE_04_API_CONTRACT.md` |
| Database/migration design exists | passed | `STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md` |
| Security/permission design exists | passed | `STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md` |
| Test plan exists | passed | `STAGE_04_TEST_PLAN.md` |
| Operations runbook exists | passed | `STAGE_04_OPERATIONS_RUNBOOK.md` |
| Risk register exists | passed | `STAGE_04_RISK_REGISTER.md` |
| Local acceptance audit exists | passed | `STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md` |
| Module index exists | passed | `STAGE_04_MODULE_INDEX.md` |
| Module docs exist | passed | `modules/STAGE_04_BINDING_MANAGEMENT.md`; `modules/STAGE_04_NEW_MESSAGE_BINDING.md`; `modules/STAGE_04_BITABLE_VIEWS.md`; `modules/STAGE_04_RESTRICTED_TEST_SEND.md`; `modules/STAGE_04_INTENT_PLACEHOLDER.md` |
| Functional development docs are detailed | passed locally | Module docs cover purpose, files, states, edge cases, permissions, audit, Bitable endpoints, tests and staging gaps |
| Index docs updated | passed | `project-docs/08-implementation/README.md`; `project-docs/README.md` |
| Stage 04 docs were approved before code | passed | User confirmed Stage04 design before implementation; code changes are tracked in `STAGE_04_PROGRESS.md` |

## 3. Verification Commands For Code Phase

| Command | Expected result | Purpose |
| --- | --- | --- |
| `cd backend; pytest tests/integration/test_stage04_binding_management.py -v` | 15 passed | binding API, permission, customer existence, list filters, inactive replacement, idempotent disable, list/disable permission, not-found, conflict, audit |
| `cd backend; pytest tests/integration/test_stage04_new_message_binding.py -v` | pass | new-message binding and no historical rewrite |
| `cd backend; pytest tests/integration/test_stage04_intent_placeholder.py -v` | pass | no-LLM intent placeholder |
| `cd backend; pytest tests/integration/test_stage04_test_send.py -v` | 13 passed | send request state machine, schema limit, confirm=false, confirm-time allowlist drift, permission denial, not-found and fake send worker, including failed Telegram response |
| `cd backend; pytest tests/unit/test_stage04_config.py -v` | pass | restricted send config fail-closed behavior |
| `cd backend; pytest tests/unit/test_stage04_deploy_compose.py -v` | pass | staging runtime services can opt into `restricted_test`; migrate remains dry-run |
| `cd backend; pytest tests/unit/test_stage04_bitable_views.py -v` | 3 passed | new Bitable view contracts, masking and row-level safety |
| `cd backend; pytest tests/unit/test_stage04_telegram_bot_client.py -v` | pass | Telegram client request/response redaction |
| `cd backend; pytest tests/integration/test_stage03_redis_streams_bridge.py -v` | 4 passed | outbox to Redis stream projection, including Stage04 `request_id` field |
| `cd backend; pytest tests/integration/test_stage03_customer_binding.py tests/integration/test_stage03_worker_runtime.py -v` | pass | Stage 03 regression |
| `cd backend; alembic upgrade head --sql` | reaches Stage 04 migration | migration import/order |
| `cd backend; pytest tests -q` | 172 passed / 17 skipped | Stage 02 + Stage 03 + Stage 04 regression; online PostgreSQL smoke skipped without `STAGE02_ONLINE_DATABASE_URL` |
| Token/private-key scan over `backend`, `deploy`, `project-docs` | no Telegram token/private key/OpenRouter `sk-` key matches | Secret hygiene before Task 10; documented example database URLs are allowed |

## 4. Implementation Requirement Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| Stage 04 code development approved by user | passed | User confirmed after Stage04 docs review |
| Binding permission actions | passed | `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding management API | passed locally | create/list/disable covered by `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding customer existence boundary | passed locally | unknown `customer_id` returns 404 FastAPI `detail` without binding/audit; `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding list filter boundary | passed locally | `telegram_chat_id`, `telegram_user_id`, `status`, empty result and invalid status covered; `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding inactive replacement boundary | passed locally | inactive same-scope/key binding does not block new active binding; `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding idempotent disable boundary | passed locally | disabling an already inactive row keeps inactive state and writes before/after audit; `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding list permission boundary | passed locally | unauthorized list returns 403 and writes `permission_denied`; `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding disable permission boundary | passed locally | unauthorized disable returns 403, binding remains active and writes `permission_denied`; `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding disable not-found error | passed locally | missing binding returns 404 `telegram_binding_not_found`; `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding conflict rejection | passed locally | conflict 409 covered by `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| Binding disable audit | passed locally | `telegram.binding.disabled` audit covered by `pytest tests/integration/test_stage04_binding_management.py -v`: 15 passed |
| New message resolves `chat_user` binding | passed locally | `pytest tests/integration/test_stage04_new_message_binding.py -v`: 5 passed |
| New message resolves `chat` binding | passed locally | `pytest tests/integration/test_stage04_new_message_binding.py -v`: 5 passed |
| New message resolves `user` binding | passed locally | `pytest tests/integration/test_stage04_new_message_binding.py -v`: 5 passed |
| Inactive binding ignored | passed locally | `pytest tests/integration/test_stage04_new_message_binding.py -v`: 5 passed |
| Historical messages not rewritten | passed locally | `pytest tests/integration/test_stage04_new_message_binding.py -v`: 5 passed |
| `telegram_bindings` view | passed locally | `pytest tests/unit/test_stage04_bitable_views.py -v`: 3 passed |
| `telegram_send_requests` view | passed locally | `pytest tests/unit/test_stage04_bitable_views.py -v`: 3 passed |
| `telegram_intent_queue` view | passed locally | `pytest tests/unit/test_stage04_bitable_views.py -v`: 3 passed |
| View row-level safety | passed locally | sales actor cannot see unbound/conflict inbox rows or send request rows; `pytest tests/unit/test_stage04_bitable_views.py -v`: 3 passed |
| Intent placeholder without LLM | passed locally | `pytest tests/integration/test_stage04_intent_placeholder.py tests/integration/test_stage03_worker_runtime.py tests/unit/test_stage03_worker_runtime_factory.py -v`: 8 passed |
| `telegram_send_requests` migration | passed locally | `pytest tests/unit/test_model_metadata.py -v`: 3 passed; `alembic upgrade head --sql` reached `20260706_0011` |
| Restricted send config | passed locally | `pytest tests/unit/test_stage04_config.py tests/unit/test_stage03_config.py -v`: 13 passed |
| Staging compose send-mode override | passed locally | `pytest tests/unit/test_stage04_deploy_compose.py -v`; service-specific assertions prove api/outbox-bridge/worker read `${TELEGRAM_SEND_MODE:-dry_run}`, while migrate stays `dry_run` |
| Send request API | passed locally | `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send request schema limit | passed locally | `message_text` over 1000 chars returns 422 without request/outbox/audit; `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send request permission boundary | passed locally | unauthorized request returns 403 and writes `permission_denied`; `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send confirmation API | passed locally | `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send outbox-to-Redis bridge | passed locally | `telegram.test_send_requested` outbox event projects `request_id` into Redis stream fields; `pytest tests/integration/test_stage03_redis_streams_bridge.py -v`: 4 passed |
| Send confirmation explicit true boundary | passed locally | `confirm=false` returns 400 without request/outbox/audit mutation; `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send confirmation allowlist drift boundary | passed locally | target removed from current allowlist at confirm time returns 409, marks request `blocked`, writes block audit and creates no outbox; `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send confirmation permission boundary | passed locally | unauthorized confirm returns 403 and writes `permission_denied`; `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send confirmation not-found error | passed locally | missing request returns 404 `telegram_send_request_not_found`; `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Non-allowlisted target blocked | passed locally | `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Telegram Bot client redaction | passed locally | `pytest tests/unit/test_stage04_telegram_bot_client.py -v`: 2 passed |
| Send worker idempotency | passed locally | `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed |
| Send worker failed response state | passed locally | `pytest tests/integration/test_stage04_test_send.py -v`: 13 passed; request becomes `failed`, outbox becomes `dead_letter`, safe error is recorded |
| Staging binding rehearsal | passed | API-created binding `76413f27-7de9-4bb4-8e51-ca0ded8f46eb`; real update `184365902` appeared in `/views/telegram_inbox/records` with `binding_status=bound`, `customer_id=00000000-0000-4000-8000-000000000404`, `processing_status=processed`, `outbox_status=processed`, `intent_status=intent_ready` |
| Staging test send rehearsal | passed | Request `05f46883-e4c7-4669-99cb-99a093629f70` moved `pending_confirmation -> confirmed -> sent`; `/views/telegram_send_requests/records` showed `status=sent`, Telegram response summary `ok=true`, outbox `telegram.test_send_requested` processed, user confirmed private test chat received the message |
| Safety locks: no customer group send, no LLM, no provider | passed | `pytest tests -q`: 172 passed / 17 skipped; staging env was temporarily `restricted_test` only for allowlisted private test chat, then closed back to `TELEGRAM_SEND_MODE=dry_run`, `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS_present=no`, `LLM_ENABLED=false`, `PROVIDER_MODE=disabled`; no customer group send, provider write, LLM call or funds movement occurred |

## 5. Recorded Staging Verification

```text
Date: 2026-07-07
Environment: Tencent Cloud staging
Tencent Cloud CVM: VM-0-10-ubuntu, public IP 43.160.215.224
Domain: api.jiangtest1.online
Git commit: 360d376 Fix Stage04 staging worker send mode
Migration revision: 20260706_0011 (head)
Services running: api, caddy, outbox-bridge, postgres, redis, worker; postgres/redis healthy
TELEGRAM_SEND_MODE during send rehearsal: restricted_test
TELEGRAM_SEND_MODE after safety close: dry_run
Test send allowlist configured: yes during rehearsal, value not recorded here; cleared after rehearsal
Binding API request: POST /telegram/bindings created binding 76413f27-7de9-4bb4-8e51-ca0ded8f46eb
Observed binding row: telegram_bindings active chat_user binding for customer 00000000-0000-4000-8000-000000000404
Observed new Telegram message: update 184365902, private test chat/user redacted, text stage04 binding test 2026-07-07
Observed telegram_inbox record: binding_status=bound, processing_status=processed, outbox_status=processed, intent_status=intent_ready, trace_id=tg:184365902
Observed intent placeholder state: audit telegram.intent_placeholder.ready for message caec8652-4495-47e5-8345-3d1c7993a15d
Test send request id: 05f46883-e4c7-4669-99cb-99a093629f70
Confirmation actor: stage-02-system
Observed Telegram test chat result: user confirmed the private test chat received Stage04 restricted test send 2026-07-07
Observed telegram_send_requests row: status=sent, last_error_code=null, sent_at=2026-07-07T08:49:01.613390Z, response summary ok=true and telegram_message_id=4
Observed outbox events: telegram.test_send_requested status=processed for request 05f46883-e4c7-4669-99cb-99a093629f70
Observed audit events: telegram.test_send.requested, telegram.test_send.confirmed, telegram.test_send.sent, telegram.binding.created, message_ingested, telegram.binding.resolved, telegram.intent_placeholder.ready, telegram.message_processed
Customer group send happened: no
LLM call happened: no
Provider write happened: no
Funds movement happened: no
Result: passed
```

## 6. Remaining Risks To Track

- Binding mistakes can route future customer messages incorrectly.
- Test send is a real Telegram write even when restricted to test chat.
- Bot token must stay server-only.
- Intent placeholder must not be mistaken for completed AI classification.
- Stage 04 still uses single-node staging, not production HA.
- Stage 04 staging test customer and binding remain in staging as test data unless a later cleanup task disables or removes them.
