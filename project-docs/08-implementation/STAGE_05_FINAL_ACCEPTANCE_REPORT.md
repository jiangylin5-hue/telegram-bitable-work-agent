# Stage 05 Final Acceptance Report

## Status

- Document status: final acceptance report draft
- Scope: Stage05 final local and staging acceptance evidence once implementation is complete.
- Current Progress: 2026-07-08 Report updated after local implementation and local acceptance. Stage05 local/non-staging scope has passed through Task11 and Task12 local readiness. Task12 approval was granted on `2026-07-08 00:15:10 +08:00`. Stage05 final acceptance is not passed yet because Tencent Cloud staging deployment, staging migration, real OpenRouter evidence, real allowlisted Telegram receipt, staging business no-op evidence, staging account exception evidence and safety close are still pending execution.
- Current Progress Update: 2026-07-07 Added requirement traceability audit reference. Final acceptance remains not passed until all `pending-staging` rows in the traceability audit have redacted staging evidence.
- Current Progress Update: 2026-07-07 Added local out-of-scope runtime guard evidence. Local/non-staging evidence now includes 82 selected Stage05 tests, 255-test backend suite and a 4-test source guard for forbidden Stage05 runtime surfaces.
- Current Progress Update: 2026-07-07 Added local out-of-scope confirmation and risk summary. Final report now records what did not happen locally and which risks still require staging evidence.
- Current Progress Update: 2026-07-07 Added Task12 evidence ledger requirement. Final acceptance must include the completed redacted ledger from the operations runbook after staging approval and execution.
- Current Progress Update: 2026-07-07 Added pre-staging approval packet requirement. Final acceptance must record explicit approval against the packet before any Task12 external action.
- Current Progress Update: 2026-07-07 Refreshed local pre-approval evidence snapshot in the approval packet. Final acceptance still requires explicit approval, real staging evidence and safety close.
- Current Progress Update: 2026-07-07 Added local code readiness evidence to the approval packet. Final acceptance still depends on real staging evidence.
- Current Progress Update: 2026-07-07 Added local API/OpenAPI readiness evidence to the approval packet. Final acceptance still depends on staging API/runtime evidence.
- Current Progress Update: 2026-07-07 Added local deployment config gate evidence. Compose/env now supports approved real OpenRouter rehearsal env for runtime services while preserving safe defaults; final acceptance still requires redacted container runtime evidence in staging.
- Current Progress Update: 2026-07-07 Added local redacted runtime summary evidence. `python -m app.core.runtime_summary` is now the documented container command for proving Stage05 runtime settings without exposing secrets.
- Current Progress Update: 2026-07-08 Captured explicit Task12 approval. Approval covers the bounded staging rehearsal action subset only and does not permit production, real customer chat, customer group, provider write, funds movement, account production, automatic replacement or secret/raw allowlist recording.
- Current Progress Update: 2026-07-08 Added development detail completion audit. Final acceptance must treat `STAGE_05_DEVELOPMENT_DETAIL_COMPLETION_AUDIT.md` as the document-level implementation completeness check before continuing Task12 external staging steps.
- Current Progress Update: 2026-07-08 Task12 staging rehearsal produced partial external evidence and one blocking defect. Reviewed commit `17043e8176b25e85fcc022a259bd5a99ee473690` deployed to Tencent Cloud staging, migration reached `20260707_0016`, health returned HTTP 200, redacted runtime summaries proved real OpenRouter/restricted-test/provider-disabled settings, and a private allowlisted Telegram message was received/bound/processed. The message remained `intent_ready` with no AgentRun/draft evidence because `stage03_runtime.py` did not inject the Stage05 workflow into the Redis worker. A local runtime wiring fix now passes targeted, Stage05-focused and full backend tests, but final acceptance remains blocked until the fix is committed, redeployed and proven in staging.
- Current Progress Update: 2026-07-08 Runtime wiring fix was redeployed and produced real OpenRouter AgentRun evidence, but the first post-fix staging message failed schema validation with `agent_output_invalid`. Local follow-up now strengthens the router prompt contract and validates the embedded example against `RouterResult`; targeted router/workflow tests, Stage05 focused tests and full backend tests pass locally before any further staging attempt.
- Current Progress Update: 2026-07-08 Local real OpenRouter smoke gate was added and passed after the router prompt-contract fix. The redacted local smoke proves real OpenRouter can return a schema-valid conservative result before the next staging retry; raw key, raw prompt and raw response were not recorded.

## 1. Result

Stage05 final result is not passed yet.

Local/non-staging result:

- Passed locally: Stage05 focused tests.
- Passed locally: Stage03/Stage04 regression tests.
- Passed locally: full backend suite except documented online PostgreSQL smoke skips.
- Passed locally: Alembic offline SQL to Stage05 head.
- Passed locally: secret scan and whitespace check.
- Passed locally: staging env contract preflight.
- Passed locally: Stage05 deployment compose/env gate.

Remaining final acceptance blockers:

- Tencent Cloud staging deployment.
- Real OpenRouter AgentRun evidence.
- Real allowlisted private Telegram test-chat receipt.
- Business no-op evidence verified in staging.
- Account Inventory exception branch verified in staging or documented staging fixture.
- Safety close evidence.

This report must not be marked passed until:

- Stage05 documentation has been approved.
- Stage05 code has been implemented.
- Local focused tests and full regression have run.
- Alembic migration has been verified.
- Tencent Cloud staging has run real OpenRouter.
- Allowlisted customer reply test send has been verified.
- Business draft no-op evidence has been verified.
- Account Inventory Agent exception branch has been verified.
- Safety close has been completed.

## 2. Evidence To Fill After Implementation

| Item | Evidence |
| --- | --- |
| Date | Local evidence: 2026-07-07; staging evidence pending |
| Environment | Local test environment completed; Tencent Cloud staging pending |
| Staging commit | Pending |
| Migration revision | Local Alembic offline SQL reaches `20260707_0016`; staging `alembic current` pending |
| Local backend suite | Latest after router prompt-contract fix: `pytest tests -q`: 259 passed / 17 skipped |
| Stage05 focused tests | Latest after router prompt-contract fix: `pytest tests -k stage05 -q`: 86 passed / 190 deselected |
| Staging contract preflight | `pytest tests\integration\test_stage05_staging_contract.py -v`: 5 passed |
| Stage05 out-of-scope runtime guard | `pytest tests\unit\test_stage05_scope_guards.py -v`: 4 passed |
| Requirement traceability audit | `STAGE_05_REQUIREMENT_TRACEABILITY_AUDIT.md`: local requirements mapped; staging exit gates remain pending |
| Development detail completion audit | `STAGE_05_DEVELOPMENT_DETAIL_COMPLETION_AUDIT.md`: pre-development Stage05 documents checked against implementation evidence; reviewed artifact and Task12 staging evidence remain pending |
| Telegram update/message evidence | Not evaluated in Stage05 staging; local tests do not call Telegram |
| OpenRouter AgentRun evidence | Local fake/error metadata passed; staging produced failed real OpenRouter AgentRun with `agent_output_invalid`; succeeded or manual-review AgentRun evidence pending after prompt-contract redeploy |
| Service draft evidence | Local multi-draft persistence passed; staging draft ids pending |
| Account inventory exception evidence | Local auto-mark/manual-review tests passed; staging status event or fixture evidence pending |
| Customer reply send evidence | Local linked send request and fake worker send passed; real allowlisted Telegram receipt pending |
| Business no-op service evidence | Local business draft confirmation creates `ServiceRecord` and noop `ExecutionLog`; staging no-op evidence pending |
| Audit evidence | Local audit branches covered in tests; staging audit event list pending |
| Safety close | Local safety-close env contract passed; real staging safety close pending |
| Task12 evidence ledger | Template prepared in `STAGE_05_OPERATIONS_RUNBOOK.md` Section 7; completed staging ledger pending |
| Task12 approval packet | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` prepared; explicit approval captured at `2026-07-08 00:15:10 +08:00` |
| Task12 pre-approval evidence snapshot | Current local evidence recorded in `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md`; real staging evidence pending |
| Stage05 code readiness audit | Runtime AST compile/import and TODO/provider keyword scan evidence recorded in `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md`; real staging runtime evidence pending |
| Stage05 API/OpenAPI readiness audit | FastAPI app/OpenAPI key-path evidence recorded in `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md`; real staging API evidence pending |
| Stage05 deployment config gate | `pytest tests\unit\test_stage05_deploy_compose.py -v`: 2 passed; `pytest tests\unit\test_stage04_deploy_compose.py -v`: 1 passed; real container runtime proof pending staging |
| Redacted runtime summary command | `pytest tests\unit\test_stage05_runtime_summary.py -v`: 3 passed; `python -m app.core.runtime_summary` prints only modes, booleans, presence flags and validation status; deployed-container proof pending staging |
| Task12 runtime wiring fix | `backend/app/workers/stage03_runtime.py` now builds/injects `Stage05AgentWorkflowService` in real OpenRouter mode; `pytest tests/unit/test_stage03_worker_runtime_factory.py tests/integration/test_stage05_worker_runtime.py -q`: 7 passed; redeploy evidence pending |
| Task12 router prompt-contract fix | `backend/app/agents/message_intake_router.py` now gives real models an explicit RouterResult output contract and schema-valid example; `pytest tests/unit/test_stage05_router_schema.py tests/integration/test_stage05_agent_workflow.py -q`: 15 passed; redeploy evidence pending |
| Local real OpenRouter smoke gate | `STAGE_05_LOCAL_OPENROUTER_ENV_SMOKE.md`; local redacted smoke returned `ok=true`, `model_provider=openrouter`, `model_name=openrouter/auto`, `prompt_version=stage05-router-v1`, request id present, usage present, `intent_types=["recharge","bm_invite"]`, `overall_confidence=0.7350`, `requires_manual_review=true`; staging retry pending |

## 3. Out Of Scope Confirmation

This table records local/non-staging evidence only. The same boundaries must be checked again after any approved staging rehearsal.

| Out-of-scope item | Local status | Local evidence | Staging follow-up |
| --- | --- | --- | --- |
| UI / Mini App implementation | did not happen locally | No Stage05 frontend/Mini App runtime surface; `test_stage05_scope_guards.py` checks forbidden runtime path names | Reconfirm no UI/Mini App deploy in staging |
| RAG / pgvector implementation | did not happen locally | No Stage05 RAG/pgvector runtime surface; source guard checks deferred retrieval surfaces | Future stage only |
| Production launch | did not happen locally | No production deployment action was run or recorded | Reconfirm no production cutover after staging |
| Real customer chat send | did not happen locally | Local tests use fake Telegram client; no real Telegram API call was executed | Staging send must target private allowlisted test chat only |
| Customer group send | did not happen locally | No group-send workflow added; send path is restricted to `telegram_send_requests` and allowlist checks | Reconfirm no customer group target in staging |
| Provider write | did not happen locally | Business draft confirmation creates `ExecutionLog(provider=noop, execution_status=skipped)` and no `ExecutionTicket`; scope guard blocks Stage05 provider execution calls | Staging must prove `PROVIDER_MODE=disabled` |
| Funds movement | did not happen locally | No provider call or funds action path is invoked by Stage05 business confirmation | Reconfirm no provider/funds execution in staging |
| Account production by Agent | did not happen locally | Account Inventory Agent creates review draft or abnormal status event only; scope guard blocks Stage05 account production calls | Future stage only |
| Automatic replacement recommendation/reservation/distribution | did not happen locally | Account exception evidence records `replacement_action = none`; workflow creates reviewable `account_assignment` draft only | Reconfirm no automatic replacement in staging |
| Agent skills/capabilities runtime registry before main Stage05 acceptance | did not happen locally | Skills/capabilities doc is reference-only; scope guard checks no Stage05 skill/capability registry runtime surface | Revisit only after main Stage05 final acceptance |

## 4. Remaining Risks

Risk details are tracked in [Stage 05 Risk Register](STAGE_05_RISK_REGISTER.md). Current local status:

| Risk ID | Current local status | Evidence | Remaining staging risk |
| --- | --- | --- | --- |
| R05-01 OpenRouter hallucinated intent/entities | locally mitigated; first real staging output still failed schema | Router schema, confidence/manual-review and invalid-output tests pass; router prompt contract now includes explicit top-level keys, allowed intent types and schema-valid example; local real OpenRouter smoke returns schema-valid conservative manual-review output | Deployed worker still needs retry evidence after prompt-contract redeploy |
| R05-02 prompt/raw response leak | locally mitigated | AgentRun evidence, config defaults, service draft API and secret scans avoid raw prompt/response exposure | Repeat redacted evidence review after real OpenRouter |
| R05-03 incorrect account abnormal marking | locally mitigated | High-confidence, allowed-status and ambiguous-risk manual-review tests pass | Controlled staging account exception sample still pending |
| R05-04 auto-replacement despite scope | locally guarded | Replacement action remains `none`; scope guard blocks assignment confirmation/activation from Stage05 workflow | Reconfirm after staging |
| R05-05 customer reply sent to real customer chat | locally mitigated | Allowlist request/confirm/worker tests pass; local fake worker send only | Real Telegram receipt must be private allowlisted test chat only |
| R05-06 business draft triggers provider | locally guarded | No-op business evidence tests and scope guard pass | Staging provider-disabled evidence pending |
| R05-07 duplicate worker delivery duplicates drafts | locally mitigated | Duplicate workflow idempotency test passes | Reconfirm no duplicate staging records |
| R05-08 LangGraph/PostgreSQL state divergence | locally mitigated | Workflow persists through services and local integration tests pass | Staging runtime observation pending |
| R05-09 key/token committed or logged | locally mitigated | Secret scan returns config names/placeholders/fake values only | Repeat before and after staging evidence capture |
| R05-10 Stage04 regression | locally mitigated | Stage03/Stage04 regression command passed 33 tests | Re-run or smoke relevant staging path after deploy |
| R05-11 safety close forgotten | locally preflighted | Safety-close env contract test passes | Real staging close still pending |
| R05-12 unexpected LLM cost | not evaluated with real LLM | AgentRun usage/cost fields exist locally; deploy config gate requires real mode only after approved env and runtime proof | Real OpenRouter usage/cost evidence pending |
| R05-13 Bitable views expose sensitive fields | locally mitigated | Stage05 view masking/row-scope tests pass | Staging view/API evidence pending |
| R05-14 account production boundary confusion | locally mitigated | Account docs updated and scope guard blocks Stage05 production paths | Keep boundary in future stages |

## 5. Task12 Evidence Ledger

Final acceptance must attach or summarize the completed redacted ledger from `STAGE_05_OPERATIONS_RUNBOOK.md` Section 7. Until then, this section remains pending.

| Ledger area | Status | Evidence |
| --- | --- | --- |
| Approval, deployment, migration and service health | partial; prompt-fix redeploy pending | Approval captured; commit `17043e8176b25e85fcc022a259bd5a99ee473690` deployed first; runtime wiring fix `c9347dfb780e2af36c89894d5e2f8cd574f479f9` later deployed; staging migration reached `20260707_0016`; `/health` returned HTTP 200. Router prompt-contract fix is not yet redeployed. |
| Redacted env proof for OpenRouter, provider-disabled and restricted Telegram send | partial; must repeat after prompt-fix redeploy | API and worker redacted runtime summaries showed real OpenRouter mode, key/model presence, restricted Telegram test send allowlist presence, prompt/response storage disabled and provider disabled. Repeat after router prompt-contract redeploy. |
| Mixed-language inbound Telegram message and AgentRun evidence | partial; retry required | Private allowlisted message `f17a2214-7f6c-4474-9361-6a586458f93b` was received/bound/processed but stayed `intent_ready` before runtime wiring fix. Message `0c466049-309a-40f8-805a-6e682937de1e` reached Stage05 and created a real OpenRouter AgentRun with `status=failed`, `error_code=agent_output_invalid`, `model_provider=openrouter`, `model_name=openrouter/auto`; successful or manual-review output remains pending after prompt-contract redeploy. |
| Draft creation, customer reply send and business no-op evidence | pending staging | Not executed |
| Account exception branch and view/audit evidence | pending staging | Not executed |
| Out-of-scope reconfirmation and safety close | pending staging | Not executed |

## 6. Task12 Approval Packet

Final acceptance must record explicit approval against `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` before any real staging env change, OpenRouter call or Telegram send is counted as valid Stage05 evidence.

| Approval item | Status | Evidence |
| --- | --- | --- |
| Approval packet prepared | completed locally | `STAGE_05_PRE_STAGING_APPROVAL_PACKET.md` |
| Approved action subset recorded | completed | User approved bounded Task12 staging rehearsal action subset at `2026-07-08 00:15:10 +08:00` |
| Still-forbidden action list reconfirmed | completed | Production, real customer chat, customer group, provider write, funds movement, account production, automatic replacement and secret/raw allowlist recording remain forbidden |
| Approval timestamp recorded | completed | `2026-07-08 00:15:10 +08:00` |
