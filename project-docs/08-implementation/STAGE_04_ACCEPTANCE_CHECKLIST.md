# Stage 04 Acceptance Checklist

## Status

- Document status: active acceptance checklist draft
- Scope: Stage 04 文档、binding management、new-message binding、intent placeholder、restricted test send 和 staging 验收。
- Current Progress: 2026-07-07 Tasks 1-9 are implemented locally; full backend suite passed with 172 passed / 17 skipped after the staging compose send-mode gate test was added. [Stage 04 Local Acceptance Audit](STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md) records local readiness; staging rehearsal remains pending and requires separate confirmation before any real Telegram send.

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
| Staging compose send-mode override | passed locally | `pytest tests/unit/test_stage04_deploy_compose.py -v`; api/outbox-bridge/worker read `${TELEGRAM_SEND_MODE:-dry_run}`, while migrate stays `dry_run` |
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
| Staging binding rehearsal | pending | manual evidence |
| Staging test send rehearsal | pending | manual evidence |
| Safety locks: no customer group send, no LLM, no provider | passed locally, staging pending | `pytest tests -q`: 172 passed / 17 skipped; config tests keep `LLM_ENABLED=false` and `PROVIDER_MODE=disabled`; staging manual evidence pending |

## 5. Staging Manual Verification Template

```text
Date:
Environment:
Tencent Cloud CVM:
Domain:
Git commit:
Migration revision:
Services running:
TELEGRAM_SEND_MODE:
Test send allowlist configured: yes/no, value not recorded
Binding API request:
Observed binding row:
Observed new Telegram message:
Observed telegram_inbox record:
Observed intent placeholder state:
Test send request id:
Confirmation actor:
Observed Telegram test chat result:
Observed telegram_send_requests row:
Observed audit events:
Customer group send happened: no
LLM call happened: no
Provider write happened: no
Result:
```

## 6. Remaining Risks To Track

- Binding mistakes can route future customer messages incorrectly.
- Test send is a real Telegram write even when restricted to test chat.
- Bot token must stay server-only.
- Intent placeholder must not be mistaken for completed AI classification.
- Stage 04 still uses single-node staging, not production HA.
