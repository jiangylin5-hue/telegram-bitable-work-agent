# Stage 05 Acceptance Checklist

## Status

- Document status: active acceptance checklist draft
- Scope: Stage05 documentation, implementation, local verification, staging verification and safety close.
- Current Progress: 2026-07-08 Documentation acceptance items are completed for draft. Phase 05.1 Task 1 runtime config and dependency gate, Task 2 AgentRun evidence model/service, Phase 05.2 Task 3 Router schema/state, Task 4 Supervisor Graph, Phase 05.3 Task 5 Draft Agents, Task 6 Service Draft API Enhancements, Phase 05.4 Task 7 Account Inventory Agent, Phase 05.5 Tasks 8-9 Confirmation Branches / Customer Reply Send Request, Phase 05.6 Task10 Bitable Views, Task11 Local Acceptance Audit and Task12 local readiness have completed local verification. Task12 approval was granted on `2026-07-08 00:15:10 +08:00`; real staging deployment, migration, real OpenRouter, real Telegram allowlisted receipt, staging no-op/account-exception evidence and safety close remain pending execution.
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
- Current Progress Update: 2026-07-08 Local real OpenRouter smoke gate was documented and passed. Redacted output showed `ok=true`, `model_provider=openrouter`, `model_name=openrouter/auto`, `prompt_version=stage05-router-v1`, request id and usage present, `intent_types=["recharge","bm_invite"]`, `overall_confidence=0.7350` and `requires_manual_review=true`; this is accepted as conservative schema-valid behavior before staging retry.

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
| Stage05 worker runtime injection reaches factory path | completed locally; redeploy pending | `stage03_runtime.py` now accepts/builds/injects `Stage05WorkflowTrigger` when `LLM_ENABLED=true` and `AGENT_WORKFLOW_MODE=real_openrouter`; `pytest tests/unit/test_stage03_worker_runtime_factory.py tests/integration/test_stage05_worker_runtime.py -q`: 7 passed |
| Stage05 router prompt contract guides real model output | completed locally; redeploy pending | `message_intake_router.py` now requires exact RouterResult keys, supported intent types and schema-shaped arrays/objects; `test_build_router_request_example_matches_router_schema` validates the embedded example against `RouterResult` |
| Local real OpenRouter smoke gate | completed locally; redeploy pending | `STAGE_05_LOCAL_OPENROUTER_ENV_SMOKE.md` added; local redacted smoke output returned schema-valid `recharge` + `bm_invite` with `requires_manual_review=true`, request id present and usage present |

## 4. Staging Acceptance

| Requirement | Status | Evidence |
| --- | --- | --- |
| User approved staging env changes | completed | explicit confirmation at `2026-07-08 00:15:10 +08:00`; bounded to Task12 staging rehearsal only |
| User approved Task12 approval packet | completed | explicit confirmation against `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md`; forbidden actions remain forbidden |
| Stage05 deployed to Tencent Cloud staging | partial; prompt-fix redeploy pending | Reviewed commit `17043e8176b25e85fcc022a259bd5a99ee473690` and runtime wiring fix `c9347dfb780e2af36c89894d5e2f8cd574f479f9` were deployed in separate rehearsals. Router prompt-contract fix is newer and must be committed/deployed before this row can pass. |
| Stage05 migration applied | completed for first rehearsal | Staging `alembic current` reached `20260707_0016`; no new migration is expected for runtime wiring or router prompt-contract fixes |
| Real OpenRouter enabled server-side | partial; repeat after redeploy | Redacted runtime proof showed OpenRouter key/model present and real workflow mode enabled in runtime containers |
| Real OpenRouter mode reaches runtime containers | partial; repeat after redeploy | API and worker summaries showed `LLM_ENABLED=true`, `AGENT_WORKFLOW_MODE=real_openrouter`, OpenRouter key/model present, raw prompt/response persistence disabled and provider disabled |
| Provider remains disabled | completed for first rehearsal; repeat after redeploy | Redacted runtime summaries showed `PROVIDER_MODE=disabled` |
| Restricted test send allowlist configured | completed for first rehearsal; repeat after redeploy | Redacted runtime summaries showed `telegram_send_mode=restricted_test` and allowlist present; raw allowlist was not recorded |
| Mixed Chinese/English Telegram message received | completed for first and second rehearsal | First message id `f17a2214-7f6c-4474-9361-6a586458f93b` stayed `intent_ready`; second message id `0c466049-309a-40f8-805a-6e682937de1e` reached Stage05 and failed with `agent_output_invalid` |
| AgentRun records real OpenRouter metadata | partial; prompt-fix retry pending | Second rehearsal produced `agent_runs` evidence with `model_provider=openrouter`, `model_name=openrouter/auto`, `prompt_version=stage05-router-v1`, `status=failed`, `error_code=agent_output_invalid`; succeeded or manual-review AgentRun evidence remains pending after prompt fix |
| Multiple service drafts created | pending | draft ids |
| Account exception branch verified | pending | status event or documented fixture |
| `customer_reply` confirmed | completed locally | draft becomes `confirmed`, linked by `reply-send:{draft_id}` trace, and creates/reuses a `telegram_send_requests` row in Task8 tests |
| Allowlisted test chat received reply | pending for real staging | local fake worker send passed; real Telegram receipt requires staging rehearsal and user confirmation |
| Business draft confirmed as no-op evidence | completed locally | Stage05 business draft becomes `service_record_created`, creates `ServiceRecord`, creates `ExecutionLog(provider=noop, execution_status=skipped)`, and creates no `ExecutionTicket` |
| Views show Stage05 records | completed locally; pending staging evidence | Local API view tests cover Stage05 view records and masking; staging evidence remains pending |
| Audit events recorded | pending | audit event list |
| Safety close completed | pending | dry-run/allowlist/provider evidence |
| Task12 evidence ledger completed | pending | completed redacted ledger from `STAGE_05_OPERATIONS_RUNBOOK.md` Section 7 |

## 5. Final Acceptance Result

Stage05 final result is not assigned until implementation and staging verification are complete.

Required final conclusion must explicitly state:

- Passed items.
- Skipped tests and reasons.
- External calls performed.
- External calls not performed.
- Remaining risks.
- Safety close status.
