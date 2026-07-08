# Stage 05 Acceptance Checklist

## Status

- Document status: active acceptance checklist draft
- Scope: Stage05 documentation, implementation, local verification, staging verification and safety close.
- Current Progress: 2026-07-08 Documentation, local implementation, local verification, Task12 approval, Tencent Cloud staging rehearsal, real OpenRouter evidence, allowlisted Telegram receipt, business no-op evidence, controlled account exception evidence, additional three-message Telegram real-case exercise and safety close are completed for the Stage05 functional/staging scope. Remaining risks are artifact hygiene, optional online PostgreSQL smoke coverage, controlled staging test rows and later-stage reporting/balance query support.
- Current Progress Update: 2026-07-07 Requirement traceability audit added to map every major Stage05 requirement to `passed-local`, `pending-staging`, `guarded-out-of-scope` or `documented-only` evidence.
- Current Progress Update: 2026-07-07 Stage05 out-of-scope runtime guard added and verified locally; latest local focused suite is now 82 selected Stage05 tests and full backend suite is 255 passed / 17 skipped after the redacted runtime summary command.
- Current Progress Update: 2026-07-07 Completion audit tightened local dependency evidence: `langgraph` imports and `StateGraph` resolves in the current backend environment, and Stage05 graph tests execute locally. No package install, lock refresh, staging env change, OpenRouter call or Telegram send was performed.
- Current Progress Update: 2026-07-07 Task12 evidence ledger template added to the operations runbook and linked into final acceptance evidence requirements. This prepares staging verification without executing staging actions.
- Current Progress Update: 2026-07-07 Pre-staging approval packet added so Task12 external actions have an explicit review boundary before approval.
- Current Progress Update: 2026-07-07 Pre-approval local evidence snapshot refreshed and recorded in `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md`. Real Task12 approval and staging execution remain pending.
- Current Progress Update: 2026-07-07 Stage05 code readiness audit added to the pre-approval evidence set: runtime AST compile, key module import, TODO/NotImplemented scan and direct provider/network keyword scan were refreshed locally.
- Current Progress Update: 2026-07-07 Stage05 API/OpenAPI readiness audit added to the pre-approval evidence set: FastAPI app creation, OpenAPI generation and key Stage05 API paths were verified locally.
- Current Progress Update: 2026-07-07 Stage05 deployment config gate added: compose/env now keeps safe defaults while allowing approved real OpenRouter env to reach runtime services; local RED/GREEN `tests/unit/test_stage05_deploy_compose.py` and Stage04 compose regression passed.
- Current Progress Update: 2026-07-07 Redacted runtime summary command added and verified locally. `python -m app.core.runtime_summary` reports modes, booleans, key/token presence and runtime validation status without printing secrets, allowlists, webhook secret or connection URLs.
- Current Progress Update: 2026-07-08 Task12 approval captured. User approved the bounded staging rehearsal action subset while keeping production, real customer chat, customer groups, provider writes, funds movement, account production, automatic replacement and secret/raw allowlist recording forbidden.
- Current Progress Update: 2026-07-08 Stage05 development detail completion audit added. It checks implementation details against every pre-development Stage05 document and records the remaining reviewed-artifact and Task12 staging gaps.
- Current Progress Update: 2026-07-08 Task12 staging rehearsal started and exposed a runtime wiring gap. Deployment, migration, health, real-mode redacted runtime settings and private allowlisted Telegram inbound/binding evidence were collected, but the message remained `intent_ready` because `stage03_runtime.py` did not inject Stage05 workflow into the worker. Local fix now passes targeted runtime tests, Stage05 focused tests and full backend tests; staging acceptance remains blocked until the fix is committed, redeployed and proven with new evidence.
- Current Progress Update: 2026-07-08 Runtime wiring fix was redeployed and produced real OpenRouter AgentRun evidence, but the first post-fix staging message failed with `agent_output_invalid`. Following the updated local-first rule, the router prompt contract fix now passes targeted router/workflow tests, focused Stage05 tests and full backend tests locally before any new staging attempt.
- Current Progress Update: 2026-07-08 Local real OpenRouter workflow passed after the entity-key prompt contract fix. A routed draft scenario created `recharge` and `customer_reply` drafts in `pending_confirmation`, with `reply_text_present=true`, no provider execution, and no Telegram send. A default risk scenario selected recharge/BM/customer-reply/account-inventory agents but safely entered `manual_review` with no draft/provider/send side effects.
- Current Progress Update: 2026-07-08 Task12 real Tencent Cloud staging acceptance completed for the Stage05 functional scope. Evidence includes base commit `56a193d` plus hotfix diff `sha256:f0b96aeffb4b4169e053067cb8d40b6baa923270d3ef7509264963aea472e2bd`, staging migration `20260707_0016 (head)`, real OpenRouter AgentRun `b1d0afc2-03ad-45e1-9c8f-b34984d4d811`, Telegram trace `tg:184365906`, service drafts `bb98531f-3b94-44ab-8d29-f2066a5760e1` and `43e7c7fc-cd69-408b-bc6a-438818cbfaaa`, sent request `0d00bb20-5783-42ba-82e0-9c6c9a535e6a` with user-confirmed receipt, business no-op service record `1c58d7c3-d098-4281-80e7-931bf56b6b74`, noop execution log `7f884981-6bcc-4d83-af70-f086d151e20c`, controlled account exception event `fcd2db3c-d26e-47ba-86dc-528656d685f2`, and safety close showing dry-run send mode, empty allowlist, provider disabled, LLM off/fake workflow and unsafe send request count 0.

## 1. Acceptance Boundary

Stage05 accepts:

- Real OpenRouter Agent routing in staging.
- LangGraph Supervisor + child Agent graph.
- Multi-intent message handling.
- Draft generation for `recharge`, `card_binding`, `bm_invite`, `customer_reply`, `account_assignment`.
- Account inventory high-confidence abnormal status marking.
- No automatic replacement account recommendation/reservation/distribution.
- Customer reply allowlisted test send.
- Business draft no-op service evidence.
- Bitable-like views.
- Audit and AgentRun evidence.

Stage05 does not accept:

- UI / Mini App.
- RAG / pgvector implementation.
- Production launch.
- Real customer chat send.
- Customer group send.
- Account production.
- Provider writes.
- Funds movement.
- Agent skills/capabilities runtime registry before the main Stage05 workflow is accepted.

## 2. Documentation Acceptance

| Requirement | Status | Evidence |
| --- | --- | --- |
| Source of truth exists | completed for docs draft | `STAGE_05_SOURCE_OF_TRUTH.md` |
| Implementation plan exists | completed for docs draft | `STAGE_05_IMPLEMENTATION_PLAN.md` |
| SDD exists | completed for docs draft | `STAGE_05_SDD.md` |
| BDD exists | completed for docs draft | `STAGE_05_BDD.md` |
| API contract exists | completed for docs draft | `STAGE_05_API_CONTRACT.md` |
| Database/migration design exists | completed for docs draft | `STAGE_05_DATABASE_AND_MIGRATION_DESIGN.md` |
| Security/permission design exists | completed for docs draft | `STAGE_05_SECURITY_AND_PERMISSION_DESIGN.md` |
| Test plan exists | completed for docs draft | `STAGE_05_TEST_PLAN.md` |
| Operations runbook exists | completed for docs draft | `STAGE_05_OPERATIONS_RUNBOOK.md` |
| Pre-staging approval packet exists | completed locally | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` records Task12 approval boundary, allowed actions, forbidden actions, pre-approval evidence, execution order, abort conditions and evidence output |
| Risk register exists | completed for docs draft | `STAGE_05_RISK_REGISTER.md` |
| Progress doc exists | completed for docs draft | `STAGE_05_PROGRESS.md` |
| Final acceptance report shell exists | completed for docs draft | `STAGE_05_FINAL_ACCEPTANCE_REPORT.md` |
| Module index exists | completed for docs draft | `STAGE_05_MODULE_INDEX.md` |
| Module docs exist | completed for docs draft | Stage05 core module docs under `modules/`, plus Agent skills/capabilities as a post-acceptance reference doc |
| Project indexes updated | completed for docs draft | `project-docs/README.md`; `project-docs/08-implementation/README.md` |
| Account Inventory Agent high-level docs corrected | completed for docs draft | `project-docs/04-agents/ACCOUNT_INVENTORY_AGENT.md` and scenario doc |

## 3. Implementation Acceptance

| Requirement | Status | Evidence |
| --- | --- | --- |
| Stage05 code phase approved by user | completed for implementation start | User goal continuation requested strict Stage05 development against stage docs |
| LangGraph dependency added and import verified | completed locally | `backend/pyproject.toml`; `python -c "import langgraph; from langgraph.graph import StateGraph; print('langgraph-import-ok', StateGraph.__name__)"`: `langgraph-import-ok StateGraph`; Stage05 graph tests pass locally. No package install or lock refresh was run |
| OpenRouter config fail-closed behavior | completed locally | `pytest tests\unit\test_stage05_config.py -v`: 4 passed |
| AgentRun evidence model extended | completed locally | `pytest tests\unit\test_stage05_openrouter_evidence.py -v`: 5 passed; `alembic upgrade head --sql` reaches `20260707_0012` |
| Router schema validation | completed locally through prompt-contract fix | Latest `pytest tests/unit/test_stage05_router_schema.py tests/integration/test_stage05_agent_workflow.py -q`: 15 passed; router prompt now contains explicit RouterResult top-level keys and a schema-valid example |
| Supervisor graph happy path | completed locally | `pytest tests\integration\test_stage05_agent_workflow.py tests\integration\test_stage05_worker_runtime.py -v`: 9 passed |
| Duplicate workflow idempotency | completed locally | `test_workflow_duplicate_trigger_does_not_create_second_agent_run` |
| OpenRouter failure -> `agent_failed` | completed locally with fake runtime failure | `test_workflow_maps_llm_runtime_failure_to_agent_failed` |
| Low confidence -> manual review | completed locally | `test_workflow_marks_low_confidence_router_output_manual_review` |
| Multiple draft candidates from one message | completed locally | `test_workflow_routes_bound_intent_ready_message_and_records_agent_run` creates `recharge` and `customer_reply` drafts with distinct idempotency keys |
| Recharge child agent | completed locally | `tests\unit\test_stage05_child_agents.py`: recharge complete and missing-field cases |
| Card binding child agent | completed locally | `test_card_binding_agent_rejects_raw_card_data_without_persisting_secret` |
| BM invite child agent | completed locally | `test_bm_invite_agent_marks_missing_invitee_as_needs_more_info` |
| Customer reply child agent | completed locally | `test_customer_reply_agent_creates_reviewable_reply_without_send_request` |
| Account Inventory Agent does not produce accounts | completed locally | `test_account_assignment_agent_creates_review_draft_without_inventory_mutation` |
| High-confidence account abnormal auto-mark | completed locally | blocked/risk-control unit tests plus workflow `test_workflow_marks_high_confidence_account_exception_status_event` |
| Ambiguous account risk manual review | completed locally | `test_uncertain_account_risk_enters_manual_review_without_mutation` |
| No automatic replacement account behavior | completed locally | account assignment draft requires human confirmation and exception audit records `replacement_action = none`; no assignment/status replacement side effects in tests |
| Service draft filters | completed locally | `pytest tests\unit\test_service_drafts_api.py -v`: status/draft_type/customer_id/source_message_id/trace_id/limit filters and Stage05 response fields covered |
| Customer reply confirmation creates send request | completed locally | `test_customer_reply_confirmation_creates_send_request_without_ticket_or_outbox`; API response covered by `test_confirmation_api_returns_stage05_customer_reply_side_effect_fields` |
| Business draft confirmation creates no-op evidence | completed locally | `test_stage05_business_confirmation_creates_noop_evidence_without_ticket` covers `recharge`, `card_binding`, `bm_invite`, `account_assignment` |
| Non-allowlisted reply target blocked | completed locally | request creation: `test_customer_reply_confirmation_blocks_non_allowlisted_target_without_outbox`; confirm/worker re-check: `test_customer_reply_send_confirm_blocks_allowlist_drift_without_outbox`, `test_customer_reply_worker_rechecks_allowlist_before_send` |
| Stage05 views implemented | completed locally | `pytest tests\unit\test_stage05_bitable_views.py -v`: 5 passed; covers `service_drafts`, `agent_review_queue`, `pending_confirmation`, `customer_reply_send_requests`, enhanced `telegram_inbox`, enhanced `account_inventory`, scoped masking and row-level filtering |
| Stage03/Stage04 regressions pass | completed locally | `pytest tests\integration\test_stage03_customer_binding.py tests\integration\test_stage03_worker_runtime.py tests\integration\test_stage04_intent_placeholder.py tests\integration\test_stage04_test_send.py tests\unit\test_stage04_bitable_views.py tests\unit\test_stage04_config.py -v`: 33 passed |
| Customer reply send confirm and fake worker path | completed locally | `test_customer_reply_draft_to_confirmed_send_request_to_fake_worker_send` creates linked send request, confirms it, queues outbox and fake-sends through the existing worker |
| Full backend suite pass | completed locally through router prompt-contract fix | Latest `pytest tests -q`: 259 passed / 17 skipped |
| Alembic offline SQL reaches Stage05 head | completed locally | `alembic upgrade head --sql` reaches `20260707_0016` and emits customer reply send link columns |
| Secret scan passes | completed locally | scan found config names, placeholders, documented scan patterns and fake test values only |
| Local acceptance audit recorded | completed locally | `STAGE_05_LOCAL_ACCEPTANCE_AUDIT.md` records focused Stage05, Stage03/Stage04 regression, full suite, migration SQL, secret scan, whitespace check, skipped tests and remaining staging gaps |
| Development detail completion audit recorded | completed locally | `STAGE_05_DEVELOPMENT_DETAIL_COMPLETION_AUDIT.md` checks Stage05 source, plan, SDD, BDD, API, DB, security, test, module, runbook, risk, index and Account Inventory documents against current implementation evidence |
| Staging env contract preflight | completed locally | `pytest tests\integration\test_stage05_staging_contract.py -v`: 5 passed; verifies real OpenRouter env contract, restricted Telegram send allowlist requirement, provider-disabled invariant and safety close dry-run contract |
| Requirement traceability audit recorded | completed locally | `STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md` maps source-of-truth, implementation, test, security, view and staging exit-gate requirements to current evidence and remaining work |
| Stage05 out-of-scope runtime guard | completed locally | `pytest tests\unit\test_stage05_scope_guards.py -v`: 4 passed; verifies Stage05 runtime files avoid provider/ticket/account-production paths and do not add deferred UI/RAG/skills runtime surfaces |
| Final report local out-of-scope confirmation recorded | completed locally | `STAGE_05_FINAL_ACCEPTANCE_REPORT.md` Section 3 records local evidence for UI/Mini App, RAG, production launch, real customer/group send, provider/funds, account production, automatic replacement and skills runtime registry boundaries |
| Risk register local mitigation evidence recorded | completed locally | `STAGE_05_RISK_REGISTER.md` records local mitigation evidence for R05-01 through R05-14 and identifies remaining staging risks |
| Task12 staging evidence ledger template prepared | completed locally | `STAGE_05_OPERATIONS_RUNBOOK.md` Section 7 defines required redacted values, pass conditions and failure actions for approval, deployment, migration, env proof, real OpenRouter AgentRun, drafts, reply send, no-op evidence, account exception, views, audit, out-of-scope confirmation and safety close |
| Task12 approval packet prepared | completed locally | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` defines the exact actions that later approval may permit and the actions that remain forbidden |
| Task12 pre-approval evidence refreshed | completed locally | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` records current local pre-approval evidence: Stage05 focused 82 passed, scope guard 4 passed, staging contract 5 passed, deployment config gate 2 passed, runtime summary 3 passed, full backend suite 255 passed / 17 skipped, Alembic offline SQL reaches Stage05 head, strict secret scan has no high-risk matches and whitespace check has no errors |
| Stage05 code readiness audit refreshed | completed locally | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` records runtime AST compile `compiled=50`, key module import `stage05-imports-ok`, no TODO/NotImplemented markers, and no direct provider/network action-import matches |
| Stage05 API/OpenAPI readiness refreshed | completed locally | `create_app().openapi()` generated 13 paths from 18 routes and included the Stage05 key paths for service drafts, confirmation actions, send confirmation and view records |
| Stage05 deployment config gate | completed locally | RED/GREEN `pytest tests\unit\test_stage05_deploy_compose.py -v`: old compose/env shape failed, updated compose/env passed 2/2; `pytest tests\unit\test_stage04_deploy_compose.py -v`: 1 passed |
| Redacted runtime summary command | completed locally | RED/GREEN `pytest tests\unit\test_stage05_runtime_summary.py -v`: missing module failed first, then passed 3/3 after adding `app.core.runtime_summary`; direct `python -m app.core.runtime_summary` prints JSON without secret values, raw allowlists, webhook secret or database URL |
| Stage05 worker runtime injection reaches factory path | completed locally and staging-verified | `stage03_runtime.py` builds/injects `Stage05WorkflowTrigger` when `LLM_ENABLED=true` and `AGENT_WORKFLOW_MODE=real_openrouter`; staging trace `tg:184365906` reached Stage05 workflow and produced real OpenRouter AgentRun/draft evidence |
| Stage05 router prompt contract guides real model output | completed locally and staging-verified | Prompt contract tests pass locally; staging AgentRun `b1d0afc2-03ad-45e1-9c8f-b34984d4d811` succeeded with schema-valid structured output |
| Local real OpenRouter workflow gate | completed locally and staging-verified | `backend/scripts/stage05_local_real_workflow.py` passed routed and manual-review scenarios before staging retry; staging later produced `recharge`, `customer_reply` and additional `bm_invite` draft evidence |

## 4. Staging Acceptance

| Requirement | Status | Evidence |
| --- | --- | --- |
| User approved staging env changes | completed | explicit confirmation at `2026-07-08 00:15:10 +08:00`; bounded to Task12 staging rehearsal only |
| User approved Task12 approval packet | completed | explicit confirmation against `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md`; forbidden actions remain forbidden |
| Stage05 deployed to Tencent Cloud staging | completed with explicit hotfix artifact identity | Base staging repo commit `56a193d`; deployed hotfix diff `sha256:f0b96aeffb4b4169e053067cb8d40b6baa923270d3ef7509264963aea472e2bd`; API/worker/outbox rebuilt and restarted |
| Stage05 migration applied | completed | Staging `alembic current` returned `20260707_0016 (head)` |
| Real OpenRouter enabled server-side | completed during rehearsal; safety-closed after | Runtime proof before rehearsal showed real OpenRouter mode and server-side key/model presence; after safety close API/worker show `LLM_ENABLED=false` and `AGENT_WORKFLOW_MODE=fake` |
| Real OpenRouter mode reaches runtime containers | completed during rehearsal | Real AgentRun `b1d0afc2-03ad-45e1-9c8f-b34984d4d811` succeeded with `model_provider=openrouter`, `model_name=openrouter/auto`, `prompt_version=stage05-router-v1`, `usage_summary.total_tokens=919`, `cost=0.011145`, `redaction_policy=summary_only` |
| Provider remains disabled | completed | Rehearsal and safety-close summaries show `PROVIDER_MODE=disabled`; business no-op execution log has `provider=noop` and `external_call_performed=false` |
| Restricted test send allowlist configured | completed during rehearsal; cleared after safety close | Customer reply send request reached `sent`; after safety close API/worker show `TELEGRAM_SEND_MODE=dry_run` and `telegram_test_send_allowlist_present=false` |
| Mixed Chinese/English Telegram message received | completed | Trace `tg:184365906`; message id `df39012d-4705-4abd-8008-b7e93fe95c72`; inbox showed `intent_status=routed`, `agent_status=succeeded`, `draft_count=2` |
| AgentRun records real OpenRouter metadata | completed | AgentRun `b1d0afc2-03ad-45e1-9c8f-b34984d4d811`, `status=succeeded`, `model_provider=openrouter`, `model_name=openrouter/auto`, usage/cost summary present and raw prompt/response not recorded |
| Multiple service drafts created | completed | `recharge` draft `bb98531f-3b94-44ab-8d29-f2066a5760e1`; `customer_reply` draft `43e7c7fc-cd69-408b-bc6a-438818cbfaaa` |
| Account exception branch verified | completed | Controlled fixture account `24eb5124-80ab-438f-a4cd-b427a76345a0`; status event `fcd2db3c-d26e-47ba-86dc-528656d685f2`; `after_status=risk_controlled`; `replacement_action=none`; `assignment_count=0` |
| `customer_reply` confirmed | completed | Draft `43e7c7fc-cd69-408b-bc6a-438818cbfaaa` became `confirmed` and created send request `0d00bb20-5783-42ba-82e0-9c6c9a535e6a` |
| Allowlisted test chat received reply | completed | Send request `0d00bb20-5783-42ba-82e0-9c6c9a535e6a` reached `sent`, Telegram response summary `ok=true`, message id `9`; user confirmed receipt |
| Business draft confirmed as no-op evidence | completed | Recharge draft `bb98531f-3b94-44ab-8d29-f2066a5760e1` became `service_record_created`; service record `1c58d7c3-d098-4281-80e7-931bf56b6b74`; execution log `7f884981-6bcc-4d83-af70-f086d151e20c`; `execution_ticket_count=0` |
| Views show Stage05 records | completed | `telegram_inbox`, `service_drafts`, `pending_confirmation`, `customer_reply_send_requests` and `account_inventory` view/API readbacks captured expected ids/statuses; `pending_confirmation` became empty after confirmations |
| Audit events recorded | completed | No-op audit events include `business_noop_evidence_created` and `draft_confirmed`; account exception audit includes `account.exception_marked` with `replacement_action=none` |
| Additional real Telegram cases tested | completed with one expected manual-review boundary | `tg:184365907` generated `recharge` draft `04dc4e65-5f91-4674-83f3-51873a266332`; `tg:184365908` generated `bm_invite` draft `8ab46b89-8b84-4544-a916-4276fffd544f`; `tg:184365909` asked for spend/balance and correctly entered manual review as unsupported in Stage05; all three had no service record, execution ticket, execution log or Telegram send side effects |
| Safety close completed | completed | API/worker summaries show `llm_enabled=false`, `agent_workflow_mode=fake`, `telegram_send_mode=dry_run`, allowlist absent, `provider_mode=disabled`; DB pending/confirmed/sending send request count `0` |
| Task12 evidence ledger completed | completed in acceptance docs | Evidence summarized in this checklist, `STAGE_05_FINAL_ACCEPTANCE_REPORT.md`, `STAGE_05_PROGRESS.md` and `STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md` |

## 5. Final Acceptance Result

Stage05 final result: passed for Stage05 functional/staging acceptance on 2026-07-08.

This is not a production launch and not approval for provider writes, funds movement, customer/group sends, account production or automatic replacement.

Remaining risks are tracked rather than hidden:

- The final staging hotfix was deployed as base commit `56a193d` plus explicit diff hash, not yet as a committed durable repo revision.
- 17 online PostgreSQL smoke tests remain skipped locally because `STAGE02_ONLINE_DATABASE_URL` is not configured.
- Staging contains controlled test/evidence rows and must not be treated as production data.
- Reporting/balance query support is not a Stage05 capability; real trace `tg:184365909` correctly entered manual review and should be considered for Stage06+ if needed.

Required final conclusion must explicitly state:

- Passed items.
- Skipped tests and reasons.
- External calls performed.
- External calls not performed.
- Remaining risks.
- Safety close status.
