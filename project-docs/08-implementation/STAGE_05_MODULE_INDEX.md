# Stage 05 Module Index

## Status

- Document status: active module index draft
- Scope: Stage 05 complex module boundaries, detailed functional docs and read order.
- Current Progress: 2026-07-08 Stage05 module docs have been created for six core modules: Agent graph/routing, Account Inventory Agent, draft agents, confirmation/send, Bitable views and OpenRouter evidence. The main module set has local and staging acceptance evidence. Agent skills/capabilities remains a post-acceptance reference doc only and is not part of the current Stage05 implementation/acceptance blocker set.
- Current Progress Update: 2026-07-07 Stage05 pre-staging approval packet was added to the read order as the Task12 approval boundary before real staging execution.

## 1. Module Read Order

1. [Stage 05 Source Of Truth](STAGE_05_SOURCE_OF_TRUTH.md)
2. [Stage 05 SDD](STAGE_05_SDD.md)
3. [Stage 05 API Contract](STAGE_05_API_CONTRACT.md)
4. [Stage 05 Database And Migration Design](STAGE_05_DATABASE_AND_MIGRATION_DESIGN.md)
5. [Stage 05 Security And Permission Design](STAGE_05_SECURITY_AND_PERMISSION_DESIGN.md)
6. Core module docs:
   - [Stage 05 Agent Graph And Routing](modules/STAGE_05_AGENT_GRAPH_AND_ROUTING.md)
   - [Stage 05 Account Inventory Agent](modules/STAGE_05_ACCOUNT_INVENTORY_AGENT.md)
   - [Stage 05 Draft Agents](modules/STAGE_05_DRAFT_AGENTS.md)
   - [Stage 05 Confirmation And Send](modules/STAGE_05_CONFIRMATION_AND_SEND.md)
   - [Stage 05 Bitable Views](modules/STAGE_05_BITABLE_VIEWS.md)
   - [Stage 05 OpenRouter Evidence](modules/STAGE_05_OPENROUTER_EVIDENCE.md)
7. Post-acceptance reference docs:
   - [Stage 05 Agent Skills And Capabilities](modules/STAGE_05_AGENT_SKILLS_AND_CAPABILITIES.md)
8. [Stage 05 Test Plan](STAGE_05_TEST_PLAN.md)
9. [Stage 05 Acceptance Checklist](STAGE_05_ACCEPTANCE_CHECKLIST.md)
10. [Stage 05 Operations Runbook](STAGE_05_OPERATIONS_RUNBOOK.md)
11. [Stage 05 Pre-Staging Approval Packet](STAGE_05_PRE_STAGING_APPROVAL_PACKET.md)
12. [Stage 05 Risk Register](STAGE_05_RISK_REGISTER.md)
13. [Stage 05 Progress](STAGE_05_PROGRESS.md)

## 2. Modules

| Module | Purpose | Primary files | Bitable endpoint |
| --- | --- | --- | --- |
| Agent Graph And Routing | Supervisor graph, Router schema, multi-intent selection and worker trigger | `stage05_supervisor.py`, `message_intake_router.py`, `agent_workflows.py` | `agent_runs`, `telegram_inbox`, `service_drafts`, audit |
| Agent Skills And Capabilities | Post-acceptance reference only. Feishu CLI-inspired skill registry structure, capability contracts and safety gates for later business Agent skill work | No current Stage05 runtime file; future post-acceptance extension may add registry/constants | Reference only until Stage05 main acceptance is complete |
| Account Inventory Agent | Account distribution drafts, inventory exception detection and high-confidence risk/block status marking | `account_inventory_agent.py`, `account_inventory.py` | `account_inventory`, `account_status_events`, `agent_review_queue`, audit |
| Draft Agents | Recharge, card binding, BM invite and customer reply draft generation | child agent files, `service_drafts.py` | `service_drafts`, `pending_confirmation`, audit |
| Confirmation And Send | Draft confirmation, customer reply allowlisted send and business no-op service evidence | `confirmation.py`, `confirmations.py`, `telegram_send_requests.py` | `service_records`, `execution_logs`, `telegram_send_requests`, `customer_reply_send_requests`, audit |
| Bitable Views | Stage05 business-first operational views; implemented locally in Task10 | `bitable_views.py`, `views.py` | `service_drafts`, `agent_review_queue`, `pending_confirmation`, `customer_reply_send_requests`, enhanced `telegram_inbox`, enhanced `account_inventory` |
| OpenRouter Evidence | Real LLM call metadata, redacted summaries, usage/cost/latency and failure evidence | `llm_openrouter.py`, `agent_runs.py` | `agent_runs`, audit |

## 3. Functional Detail Coverage Required

Each module doc must describe:

- Purpose and explicit non-goals.
- Existing Stage04/Stage02 dependencies.
- Inputs, outputs and Bitable endpoints.
- State machine or transition matrix.
- Permission and security rules.
- Error and edge-case behavior.
- Idempotency rules.
- Audit contract.
- Automated test plan.
- Staging/manual evidence required.

## 4. Stage Boundary

If a task needs UI, Mini App, RAG, production cutover, customer group send, true customer send, provider execution, funds movement, account production or automatic replacement distribution, stop and record it as Stage06+ candidate unless the user explicitly changes the Stage05 source of truth.

If a task needs Agent skills/capabilities runtime registry or capability tests, keep it as the documented post-acceptance Stage05 extension until the main Stage05 workflow has completed final acceptance.
