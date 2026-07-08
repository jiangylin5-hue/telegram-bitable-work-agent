# Stage 05 Final Acceptance Report

## Status

- Document status: final acceptance report
- Scope: Stage05 final local and Tencent Cloud staging acceptance evidence.
- Current Progress: 2026-07-09 Stage05 functional/staging acceptance remains passed. The Stage05 skills sidecar extension commit `558493b2fb95a58ba3a457f68312f824b6a71704` was deployed to Tencent Cloud staging and re-accepted with six real Telegram inbound messages under a safety window. Evidence covers real OpenRouter AgentRuns, `skill_evidence` persistence, business skill matches, platform/future workflow skill matches, no side effects and safety close. This is not a production launch and does not approve provider writes, funds movement, customer/group sends, account production or automatic replacement.

## 1. Result

Stage05 final result: passed for Stage05 functional/staging acceptance on 2026-07-08.

This conclusion is limited to the Stage05 scope:

- Real Telegram inbound in staging.
- Real OpenRouter routing and AgentRun evidence.
- LangGraph Supervisor plus child agent workflow.
- Draft generation for Stage05 business intents.
- Human-confirmed customer reply send to private allowlisted test chat.
- Business draft confirmation as no-op service evidence only.
- Controlled Account Inventory exception evidence.
- Bitable-like view and audit evidence.
- Safety close after staging.

This is not production readiness.

## 2. Evidence Summary

| Area | Evidence |
| --- | --- |
| Local backend suite | `cd backend; pytest tests -q`: 259 passed / 17 skipped. Skips are online PostgreSQL smoke tests requiring `STAGE02_ONLINE_DATABASE_URL`. |
| Focused Stage05 suite | `cd backend; pytest tests -k stage05 -q`: 86 passed / 190 deselected. |
| Targeted no-op regression | `pytest backend\tests\integration\test_stage05_service_draft_confirmation.py -q`: 16 passed after fixing ServiceRecord/ExecutionLog ORM relationship ordering. |
| Migration | Local `alembic upgrade head --sql` reaches `20260707_0016`; staging `alembic current` returned `20260707_0016 (head)`. |
| Deployment artifact | Staging used base commit `56a193d` plus explicit hotfix diff `sha256:f0b96aeffb4b4169e053067cb8d40b6baa923270d3ef7509264963aea472e2bd`. |
| Main real Telegram trace | `tg:184365906`, message `df39012d-4705-4abd-8008-b7e93fe95c72`, inbox status `routed`, AgentRun succeeded. |
| Real OpenRouter AgentRun | `b1d0afc2-03ad-45e1-9c8f-b34984d4d811`, `model_provider=openrouter`, `model_name=openrouter/auto`, `prompt_version=stage05-router-v1`, `usage_summary.total_tokens=919`, `cost=0.011145`, `redaction_policy=summary_only`. |
| Draft evidence | `recharge` draft `bb98531f-3b94-44ab-8d29-f2066a5760e1`; `customer_reply` draft `43e7c7fc-cd69-408b-bc6a-438818cbfaaa`. |
| Customer reply send | Send request `0d00bb20-5783-42ba-82e0-9c6c9a535e6a` reached `sent`, Telegram response `ok=true`, message id `9`; user confirmed receipt. |
| Business no-op evidence | Recharge draft confirmed to service record `1c58d7c3-d098-4281-80e7-931bf56b6b74` and execution log `7f884981-6bcc-4d83-af70-f086d151e20c`; `provider=noop`, `external_call_performed=false`, `execution_ticket_count=0`. |
| Account exception branch | Controlled fixture account `24eb5124-80ab-438f-a4cd-b427a76345a0`; status event `fcd2db3c-d26e-47ba-86dc-528656d685f2`; `after_status=risk_controlled`, `replacement_action=none`, `assignment_count=0`. |
| Safety close | API and worker summaries show `llm_enabled=false`, `agent_workflow_mode=fake`, `telegram_send_mode=dry_run`, allowlist absent, `provider_mode=disabled`; pending/confirmed/sending Telegram request count is 0. |

## 3. Additional Real-Case Telegram Exercise

After the main acceptance flow, the user sent three additional real Telegram messages in staging. The real LLM handled all three without provider/send side effects:

| Trace | Message summary | LLM result | Draft / review result | Side effects |
| --- | --- | --- | --- | --- |
| `tg:184365907` | Recharge `act_stage05_mc_01` for `88 USD` | `intent_type=recharge`, confidence `0.9700` | Draft `04dc4e65-5f91-4674-83f3-51873a266332`, `pending_confirmation` | No service record, execution ticket, execution log or Telegram send request. |
| `tg:184365908` | Invite `user@example.com` to BM `123456789` | `intent_type=bm_invite`, confidence `0.9700` | Draft `8ab46b89-8b84-4544-a916-4276fffd544f`, `pending_confirmation` | No service record, execution ticket, execution log or Telegram send request. |
| `tg:184365909` | Ask for today's spend and balance | `intent_type=unknown`, `requires_manual_review=true`, reason `unsupported_request_type_for_available_intents` | Entered manual review; no draft | No service record, execution ticket, execution log or Telegram send request. |

This round did not create a new `customer_reply` draft because none of the three messages asked the agent to draft a customer-facing reply. The `customer_reply` path is still covered by trace `tg:184365906`, including a real allowlisted Telegram receipt confirmed by the user.

The reporting/balance query in `tg:184365909` is a useful boundary finding: Stage05 correctly avoided inventing unsupported spend/balance facts and routed the message to manual review. Reporting/balance query support should be treated as a later-stage feature, not a Stage05 completion blocker.

## 4. Out Of Scope Confirmation

The following did not happen during Stage05 acceptance:

- No production deployment or production cutover.
- No real customer chat send and no customer group send.
- No provider write, Meta/BM/card/recharge provider call or funds movement.
- No account production, account import, automatic replacement, reservation or redistribution.
- No execution ticket was created for Stage05 business no-op confirmation.
- No raw prompt, raw LLM response, bot token, OpenRouter key, database URL or raw allowlist value was recorded in the report.

## 4.1 Skills Extension Staging Re-Acceptance

On 2026-07-09, commit `558493b2fb95a58ba3a457f68312f824b6a71704` was deployed to Tencent Cloud staging by transferring a local git bundle and fast-forwarding the staging repo. The prior uncommitted staging hotfix was already preserved by durable commit `b5812f8`, so the temporary server stash was dropped after deployment.

Deployment and runtime evidence:

| Area | Evidence |
| --- | --- |
| Staging commit | `558493b2fb95a58ba3a457f68312f824b6a71704` |
| Migration | `20260707_0016 (head)` |
| Health | `GET /health` returned `{"status":"ok"}` |
| Real OpenRouter window | API/worker summaries showed `llm_enabled=true`, `agent_workflow_mode=real_openrouter`, OpenRouter key present, `telegram_send_mode=dry_run`, allowlist absent, `provider_mode=disabled`, raw prompt/response storage disabled |
| Safety close | API/worker summaries returned to `llm_enabled=false`, `agent_workflow_mode=fake`, `telegram_send_mode=dry_run`, allowlist absent, `provider_mode=disabled`; pending/sendable Telegram requests `0`, execution tickets `0` |

Real Telegram traces:

| Trace | Purpose | Result | Skill evidence | Side effects |
| --- | --- | --- | --- | --- |
| `tg:184365910` | Recharge request | `recharge` draft `e16bf18d-0c6b-44b3-86da-7aa24b91a7db`, `pending_confirmation` | `project-base`, `project-shared`, `project-im`, `project-event`, `recharge-draft` | No send request, service record, execution ticket or execution log |
| `tg:184365911` | BM invite request | `bm_invite` draft `85badebb-515e-4ff0-aade-082c3d54a9b7`, `pending_confirmation` | `project-base`, `project-shared`, `project-im`, `project-event`, `bm-invite-draft`, `project-contact` | No send request, service record, execution ticket or execution log |
| `tg:184365912` | Spend/balance query | `manual_review`, no draft | `project-base`, `project-shared`, `project-im`, `project-event`, `manual-review-handoff`, `spend-query`, `project-tabular-analysis` | No side effects |
| `tg:184365913` | Customer ownership/manual confirmation boundary | `manual_review`, no draft | `project-base`, `project-shared`, `project-im`, `project-event`, `manual-review-handoff`, `project-task` | No side effects |
| `tg:184365914` | Approval boundary | `manual_review`, no draft | `project-base`, `project-shared`, `project-im`, `project-event`, `manual-review-handoff` | No side effects |
| `tg:184365915` | Future monthly workflow | `manual_review`, fallback `future_scope`, no draft | `project-base`, `project-shared`, `project-im`, `project-event`, `manual-review-handoff`, `project-daily-operations-workflow` | No side effects |

This re-acceptance did not perform a real Telegram send. It intentionally kept `TELEGRAM_SEND_MODE=dry_run` to validate inbound routing, real LLM skill evidence and side-effect safety after the skills extension.

## 5. Remaining Risks

| Risk | Status / next action |
| --- | --- |
| Hotfix artifact hygiene | Resolved for the staging hotfix: commit `b5812f8` preserved the ServiceRecord/ExecutionLog hotfix, and commit `558493b2` was deployed to staging as the current reviewed artifact. |
| Online PostgreSQL smoke skips | 17 online smoke tests remain skipped because `STAGE02_ONLINE_DATABASE_URL` is not configured. This does not block Stage05 functional staging acceptance, but should be run separately if disposable online DB certification is required. |
| Staging test data | Staging contains controlled evidence rows and must not be treated as production data. |
| Reporting/balance query | Real traces `tg:184365909` and `tg:184365912` showed spend/balance reporting is still non-executing in Stage05. The skills layer now logs `spend-query` and `project-tabular-analysis`, but the workflow still falls back to manual review. Treat executable reporting/balance support as Stage06+ work. |

## 6. Close Decision

Stage05 can be closed for the agreed functional/staging acceptance scope after this report and linked audit/checklist documents are updated and verification commands are rerun.

Recommended next stage:

1. Keep Stage05 staging safety-closed unless a new explicitly approved rehearsal window is opened.
2. Start Stage06 planning for production hardening or for the next business capability, with reporting/balance query support as one candidate.
