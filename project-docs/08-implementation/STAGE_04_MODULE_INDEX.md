# Stage 04 Module Index

## Status

- Document status: active module index
- Scope: Stage 04 complex module boundaries, detailed functional development docs and read order.
- Current Progress: 2026-07-07 Stage04 complex modules have detailed standalone docs, and local readiness is summarized in `STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md`. Staging evidence remains pending.

## 1. Module Read Order

1. [Stage 04 Source Of Truth](STAGE_04_SOURCE_OF_TRUTH.md)
2. [Stage 04 SDD](STAGE_04_SDD.md)
3. [Stage 04 API Contract](STAGE_04_API_CONTRACT.md)
4. [Stage 04 Database And Migration Design](STAGE_04_DATABASE_AND_MIGRATION_DESIGN.md)
5. [Stage 04 Security And Permission Design](STAGE_04_SECURITY_AND_PERMISSION_DESIGN.md)
6. [Stage 04 Local Acceptance Audit](STAGE_04_LOCAL_ACCEPTANCE_AUDIT.md)
7. Module docs:
   - [Stage 04 Binding Management](modules/STAGE_04_BINDING_MANAGEMENT.md)
   - [Stage 04 New Message Binding](modules/STAGE_04_NEW_MESSAGE_BINDING.md)
   - [Stage 04 Bitable Views](modules/STAGE_04_BITABLE_VIEWS.md)
   - [Stage 04 Restricted Test Send](modules/STAGE_04_RESTRICTED_TEST_SEND.md)
   - [Stage 04 Intent Placeholder](modules/STAGE_04_INTENT_PLACEHOLDER.md)

## 2. Modules

| Module | Purpose | Primary files | Bitable endpoint |
| --- | --- | --- | --- |
| Binding Management | Manage Telegram chat/user/customer bindings | `telegram_binding_management.py`, `telegram_bindings.py` | `telegram_bindings` view and audit |
| New Message Binding | Ensure future messages use active binding | `customer_binding.py`, `telegram_ingestion.py` | `telegram_inbox` bound state |
| Bitable Views | Expose Stage04 operational evidence through view contracts | `bitable_views.py`, `views.py` | `telegram_bindings`, `telegram_send_requests`, `telegram_intent_queue`, `telegram_inbox` |
| Intent Placeholder | Reserve no-LLM intent extraction boundary | `telegram_intent_placeholder.py`, worker handler | `telegram_intent_queue` view and audit |
| Restricted Test Send | Send confirmed test message to allowlisted test chat | `telegram_send_requests.py`, `telegram_bot.py`, worker handler | `telegram_send_requests` view and audit |

## 3. Functional Detail Coverage

Each module doc must describe:

- Purpose and explicit non-goals.
- Implemented files and ownership boundary.
- Inputs, outputs and Bitable endpoints.
- State machine or state transition matrix.
- Permission and security rules.
- Error and edge-case behavior.
- Audit contract.
- Automated test evidence.
- Staging/manual evidence still required.

Current coverage:

| Module doc | Covers state/edge cases | Covers implementation path | Covers tests | Staging pending clearly marked |
| --- | --- | --- | --- | --- |
| `STAGE_04_BINDING_MANAGEMENT.md` | yes | yes | yes | yes |
| `STAGE_04_NEW_MESSAGE_BINDING.md` | yes | yes | yes | yes |
| `STAGE_04_BITABLE_VIEWS.md` | yes | yes | yes | yes |
| `STAGE_04_INTENT_PLACEHOLDER.md` | yes | yes | yes | yes |
| `STAGE_04_RESTRICTED_TEST_SEND.md` | yes | yes | yes | yes |

## 4. Stage Boundary

If a task needs UI, OpenRouter, LangGraph, customer group send, provider execution, history replay or production cutover, stop and record it as Stage 05+ candidate unless user explicitly changes Stage 04 source of truth.
