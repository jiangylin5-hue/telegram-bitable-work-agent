# Stage 05 Test Plan

## Status

- Document status: active test plan draft
- Scope: Stage05 unit, integration, regression, migration, secret scan and staging validation.
- Current Progress: 2026-07-07 Test plan drafted. Phase 05.1 Task 1 added `tests/unit/test_stage05_config.py`; Task 2 added `tests/unit/test_stage05_openrouter_evidence.py`; Phase 05.2 Task 3 added `tests/unit/test_stage05_router_schema.py`; Task 4 added `tests/integration/test_stage05_agent_workflow.py` and `tests/integration/test_stage05_worker_runtime.py`; Phase 05.3 Task 5 added `tests/unit/test_stage05_child_agents.py` and extended workflow integration for multi-draft persistence; Task 6 extended `tests/unit/test_service_drafts_api.py` for Service Draft API filters and Stage05 response fields; Phase 05.4 Task 7 added `tests/unit/test_stage05_account_inventory_agent.py` and account inventory workflow integration; Phase 05.5 Task 8 added `tests/integration/test_stage05_service_draft_confirmation.py` for confirmation branches, no-op evidence, wrong states, idempotency and permission boundaries; Task9 added `tests/integration/test_stage05_customer_reply_send.py` for persisted draft link, send confirmation, fake worker send, confirm-time allowlist drift, worker re-check and migration head; Phase 05.6 Task10 added `tests/unit/test_stage05_bitable_views.py` for view fields, row-level scope, scoped masking and derived Agent evidence; Task12 preflight added `tests/integration/test_stage05_staging_contract.py` for staging env safety assumptions; local scope guard added `tests/unit/test_stage05_scope_guards.py` for Stage05 out-of-scope runtime boundaries; deployment config gate added `tests/unit/test_stage05_deploy_compose.py` for Stage05 real OpenRouter compose/env readiness while keeping safe defaults; runtime summary added `tests/unit/test_stage05_runtime_summary.py` for redacted container settings evidence. These completed local RED/GREEN or preflight verification. Task11 local acceptance passed for non-staging scope; real staging tests are pending.

## 1. Test Strategy

Stage05 uses real OpenRouter in staging, but local automated tests must be deterministic. Therefore:

- Local tests use fake LLM clients and fake Telegram clients.
- Unit tests validate schema, state policy, permission and view behavior.
- Integration tests validate persistence and worker flow.
- A local real OpenRouter workflow script validates router prompt/schema compatibility and the Stage05 in-memory workflow after deterministic tests pass and before any further staging retry.
- Staging validates real OpenRouter in deployed worker context and allowlisted Telegram send once the local suite and local real OpenRouter workflow pass.
- Stage03/Stage04 regression is mandatory because Stage05 extends their runtime paths.

## 2. Unit Tests

| Test file | Coverage |
| --- | --- |
| `tests/unit/test_stage05_config.py` | OpenRouter/LangGraph settings, fail-closed config, prompt/raw response persistence defaults |
| `tests/unit/test_stage05_openrouter_evidence.py` | AgentRun metadata, usage/cost/latency, redaction policy, no raw prompt exposure |
| `tests/unit/test_stage05_router_schema.py` | Router JSON schema, multi-intent validation, intent-to-child-agent selection, StateGraph-compatible state initialization, invalid JSON/output handling |
| `tests/unit/test_stage05_child_agents.py` | Recharge/card/BM/reply draft candidate generation |
| `tests/unit/test_service_drafts_api.py` | Service draft list route filters, response shape and no raw LLM prompt/response exposure |
| `tests/unit/test_stage05_account_inventory_agent.py` | No production path, high-confidence abnormal auto-mark, ambiguous risk manual review |
| `tests/unit/test_stage05_bitable_views.py` | `service_drafts`, `agent_review_queue`, `pending_confirmation`, `customer_reply_send_requests`, enhanced `telegram_inbox`, enhanced `account_inventory`, row-level safety, scoped masking and manager/admin operational evidence |
| `tests/unit/test_stage05_scope_guards.py` | Stage05 runtime source guard for provider/ticket/account-production calls, reply/no-op confirmation branches and deferred UI/RAG/skills runtime surfaces |
| `tests/unit/test_stage05_deploy_compose.py` | Stage05 deployment compose/env gate: runtime services can receive approved real OpenRouter env, defaults remain LLM-off/fake, `migrate` remains LLM-off/fake, provider remains disabled |
| `tests/unit/test_stage05_runtime_summary.py` | Redacted runtime evidence command: `python -m app.core.runtime_summary` prints booleans/presence/validation only and omits keys, tokens, allowlists, webhook secret and database URL |

Minimum cases:

- Mixed Chinese/English message maps to multiple intents.
- Missing amount produces `needs_more_info`.
- Raw card-like sensitive data is not stored in draft payload.
- Customer reply text is not sent without confirmation.
- Account production request is out of scope.
- High-confidence blocked account writes allowed status.
- Attempted automatic allocation/replacement is rejected.
- AgentRun summary has model and usage metadata but no full prompt in view.

Deferred:

- Agent skills/capabilities registry tests are intentionally not part of the main Stage05 acceptance suite. They should be added only after Stage05 main workflow acceptance, when the post-acceptance skills extension starts.

## 3. Integration Tests

| Test file | Coverage |
| --- | --- |
| `tests/integration/test_stage05_agent_workflow.py` | message -> LangGraph Supervisor -> Router AgentRun -> status transitions -> multiple `service_drafts` from supported child agents |
| `tests/integration/test_stage05_worker_runtime.py` | optional `intent_ready` worker trigger delegation and Stage04 placeholder preservation |
| `tests/integration/test_stage05_service_draft_confirmation.py` | Stage05 customer reply draft confirmation, business no-op evidence, wrong-state conflicts, duplicate confirmation and manager/admin confirmation boundary |
| `tests/integration/test_stage05_customer_reply_send.py` | customer reply draft -> linked send request -> send confirmation -> allowlisted fake worker send; non-allowlisted confirm/worker blocks; reply-send migration |
| `tests/integration/test_stage05_staging_contract.py` | local contract checks for staging env assumptions: real OpenRouter mode, restricted Telegram send allowlist, provider-disabled invariant, safety close dry-run |

Required integration scenarios:

- Bound `intent_ready` message becomes `routed`.
- Duplicate workflow trigger creates no duplicate AgentRun.
- OpenRouter fake failure leads to `agent_failed`.
- Low-confidence fake output leads to `manual_review`.
- Multiple child drafts share one trace id and distinct idempotency keys.
- Service draft list supports `status`, `draft_type`, `customer_id`, `source_message_id`, `trace_id` and `limit` query filters.
- Service draft list response exposes Stage05 operational fields and does not expose raw LLM prompt/response fields.
- High-confidence `account_status_exception` writes `account_status_events`, inventory status and audit.
- `account_assignment` creates a reviewable draft without assignment side effects.
- Business draft confirmation creates service/no-op evidence only.
- Customer reply confirmation creates send request.
- Non-allowlisted customer reply request is blocked during Task8 request creation and Task9 send-confirm/worker re-check.
- Stage05 views expose operational evidence without raw prompt/response or raw draft payload.
- `pending_confirmation` excludes non-confirmable drafts with wrong state, missing fields or missing customer.
- `agent_review_queue` includes manual-review messages, manual-review drafts and failed AgentRuns.
- Customer-scoped actors see only authorized customer rows and masked sensitive fields in views.

## 4. Regression Tests

Before Stage05 local acceptance:

```text
cd backend
pytest tests/integration/test_stage03_customer_binding.py -v
pytest tests/integration/test_stage03_worker_runtime.py -v
pytest tests/integration/test_stage04_intent_placeholder.py -v
pytest tests/integration/test_stage04_test_send.py -v
pytest tests/unit/test_stage04_bitable_views.py -v
pytest tests/unit/test_stage04_config.py -v
pytest tests/unit/test_stage04_deploy_compose.py -v
pytest tests/unit/test_stage05_deploy_compose.py -v
pytest tests/unit/test_stage05_runtime_summary.py -v
```

Full suite:

```text
cd backend
pytest tests -q
```

Expected result after implementation:

- All non-online tests pass.
- Online PostgreSQL smoke tests may remain skipped unless `STAGE02_ONLINE_DATABASE_URL` is configured.
- Any new skip must be documented with reason.

## 4.1 Local Real OpenRouter Workflow

Before any Stage05 Task12 staging retry that depends on router prompt/schema behavior, run the local real OpenRouter workflow in [Stage 05 Local Real Workflow Env](STAGE_05_LOCAL_REAL_WORKFLOW_ENV.md).

This workflow is intentionally separate from deterministic automated tests:

- It reads local secrets from `.local/stage05-real-workflow.env`, which is ignored by git.
- It makes a real OpenRouter call through `OpenRouterStructuredLLMClient`.
- It runs `Stage05AgentWorkflowService` with an in-memory UOW.
- It verifies Router -> LangGraph Supervisor -> child Draft Agents -> AgentRun/draft/account-exception/audit evidence.
- It prints only redacted operational evidence.
- It must not print raw prompt, raw response, key, Telegram token, raw allowlist, database URL or Redis URL.

Command:

```text
cd backend
python scripts/stage05_local_real_workflow.py
```

Pass criteria:

- `ok=true`.
- `workflow_status` is `routed` or `manual_review`.
- `agent_runs[0].model_provider=openrouter`.
- `agent_runs[0].prompt_version=stage05-router-v1`.
- `agent_runs[0].status=succeeded`.
- `provider_mode=disabled`.
- `telegram_send_mode=dry_run`.
- Any created service draft remains reviewable and does not permit provider execution.

Current pass evidence after the entity-key prompt contract fix:

- Routed draft scenario: `ok=true`, `workflow_status=routed`, `model_provider=openrouter`, `prompt_version=stage05-router-v1`, `intent_types=["recharge","customer_reply"]`, `requires_manual_review=false`, `service_drafts=["recharge:pending_confirmation","customer_reply:pending_confirmation"]`, `reply_text_present=true`, `provider_execution_allowed=false`, `send_request_created=false`.
- Default risk scenario: `ok=true`, `workflow_status=manual_review`, `intent_types=["recharge","bm_invite","customer_reply","account_status_exception"]`, `requires_manual_review=true`, no service drafts, `provider_mode=disabled`, `telegram_send_mode=dry_run`.

Do not proceed to staging if this gate fails with `agent_output_invalid` or any safety preflight error.

## 5. Migration Tests

Commands:

```text
cd backend
alembic upgrade head --sql
```

Expected:

- Offline SQL reaches Stage05 head revision.
- SQL includes only additive changes.
- SQL contains no secrets.

Metadata tests must verify:

- New columns exist if implemented.
- Idempotency constraints remain.
- No raw secret/payment/prompt columns are introduced.

## 6. Security Tests

Required automated checks:

- Missing OpenRouter key in real mode fails before external call.
- `AGENT_SAVE_FULL_PROMPT=false` and `AGENT_SAVE_FULL_RESPONSE=false` by default.
- Agent cannot confirm draft.
- Agent cannot allocate account directly.
- Agent cannot create production account.
- Agent can only auto-mark allowed abnormal account statuses.
- Non-allowlisted Telegram target is blocked.
- Provider adapters are not called for business drafts.
- Stage05 runtime files do not call provider execution, execution-ticket production, account production, account assignment confirmation or account activation paths.
- Deferred UI, Mini App, RAG/pgvector and Agent skills/capabilities runtime surfaces are not introduced before main Stage05 acceptance.

Secret scan before staging:

```text
rg -n "OPENROUTER_API_KEY|TELEGRAM_BOT_TOKEN|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS" backend deploy project-docs
```

Expected:

- Only placeholder/example names appear.
- No actual token, private key or allowlist value appears.

## 7. Staging Test Plan

Preconditions:

- User approves staging env changes.
- Stage05 code is committed/deployable.
- Local tests pass.
- OpenRouter key is supplied server-side only.
- Telegram test chat id is configured server-side only for the rehearsal window.
- Provider mode remains disabled.

Staging steps:

1. Deploy Stage05 to Tencent Cloud staging.
2. Run Alembic migration.
3. Confirm `LLM_ENABLED=true` and `AGENT_WORKFLOW_MODE=real_openrouter` are visible inside `api` and `worker` containers through redacted runtime summaries.
4. Confirm `PROVIDER_MODE=disabled`.
5. Enable `TELEGRAM_SEND_MODE=restricted_test`.
6. Configure allowlisted private test chat.
7. Send mixed Chinese/English Telegram message to test bot.
8. Verify `messages.intent_status`.
9. Verify `agent_runs` row with OpenRouter metadata.
10. Verify multiple `service_drafts`.
11. Verify `service_drafts` view.
12. Confirm `customer_reply` draft.
13. Verify allowlisted private test chat receives reply.
14. Confirm business draft and verify no-op service evidence.
15. Exercise account exception branch with a controlled message or fixture.
16. Verify `account_status_events` and audit.
17. Restore staging to dry-run send mode and clear allowlist.
18. Record redacted evidence.

## 8. Acceptance Evidence

Stage05 final acceptance must record:

- Git commit.
- Migration head.
- Local full test result.
- Focused Stage05 test result.
- Staging message id/update id.
- Agent run id(s).
- OpenRouter model metadata and usage summary.
- Draft ids.
- Account status event id if branch exercised.
- Customer reply send request id and sent/failed status.
- Confirmation/no-op service evidence id.
- Safety close result.
- Completed Task12 evidence ledger from `STAGE_05_OPERATIONS_RUNBOOK.md`, including pass/fail status for approval, deployment, migration, redacted env proof, real AgentRun, draft creation, reply send, business no-op evidence, account exception, view evidence, audit evidence, out-of-scope confirmation and safety close.

No secrets or raw allowlist values should be recorded.
