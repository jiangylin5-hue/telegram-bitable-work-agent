# Stage 05 Skills Extension Acceptance Checklist

## Status

- Document status: active acceptance checklist
- Scope: Requirement-by-requirement acceptance for Stage05 Skills Extension.
- Current Progress: 2026-07-09 Updated after implementation, local verification and Tencent Cloud staging re-acceptance. Static registry, sidecar matching, AgentRun evidence, local tests, real OpenRouter smoke and six real Telegram staging messages passed under a safety window. Staging was safety-closed after validation.

## 1. Documentation Acceptance

| Item | Expected Evidence | Status |
| --- | --- | --- |
| Existing 27-skill audit committed separately | Commit `docs(stage05): audit larksuite skills reference` | Passed |
| Source of truth exists | `STAGE_05_SKILLS_EXTENSION_SOURCE_OF_TRUTH.md` | Passed |
| Implementation plan exists | `STAGE_05_SKILLS_EXTENSION_IMPLEMENTATION_PLAN.md` | Passed |
| Manifest design exists | `STAGE_05_SKILLS_MANIFEST_DESIGN.md` | Passed |
| Official skill summary exists | `modules/STAGE_05_LARKSUITE_SKILLS_OFFICIAL_SUMMARY.md` | Passed |
| Index links exist | README/module index link extension docs | Passed |

## 2. Registry Acceptance

| Item | Expected Evidence | Status |
| --- | --- | --- |
| Static registry exists | `backend/app/agents/stage05_skills.py` | Passed |
| P0/P1 platform adapters registered | Unit test asserts expected ids | Passed |
| Business skills registered | Unit test asserts expected ids | Passed |
| `report-draft` not registered | Unit test asserts absence | Passed |
| Every skill has layer/owner/endpoint | Unit test validates all manifests | Passed |
| No dynamic marketplace | Scope guard and source inspection | Passed |

## 3. Matching Acceptance

| Item | Expected Evidence | Status |
| --- | --- | --- |
| Sidecar matcher exists | `backend/app/agents/stage05_skill_matching.py` | Passed |
| Recharge + reply case selected | Fixture/unit test | Passed |
| BM invite case selected | Fixture/unit test | Passed |
| Spend/balance case selected but not executed | Fixture/unit test | Passed |
| Card binding case selected | Fixture/unit test | Passed |
| Account exception case selected | Fixture/unit test | Passed |
| Report/future case routes to future/manual review | Fixture/unit test | Passed |

## 4. AgentRun Evidence Acceptance

| Item | Expected Evidence | Status |
| --- | --- | --- |
| `skill_evidence` stored in AgentRun output | Integration test on Stage05 workflow | Passed |
| Existing business outputs unchanged | Existing Stage05 workflow tests still pass | Passed |
| No migration unless needed | Schema/model inspection | Passed |
| No new API | Route file inspection | Passed |

## 5. Real OpenRouter Acceptance

| Item | Expected Evidence | Status |
| --- | --- | --- |
| Smoke script exists | `backend/scripts/stage05_skill_openrouter_smoke.py` | Passed |
| Real OpenRouter run succeeds | Command output from local smoke | Passed |
| Five cases executed | Smoke output shows 5/5 cases | Passed |
| No raw prompt/response persisted | Source and git diff inspection | Passed |

## 6. Full Verification

| Command | Expected Result | Actual Result |
| --- | --- | --- |
| `pytest tests/unit/test_stage05_skill_registry.py tests/unit/test_stage05_skill_matching.py -q` | pass | `10 passed in 0.06s` |
| `pytest tests -k stage05 -q` | pass | `98 passed, 190 deselected in 3.11s` |
| `pytest tests -q` | pass or documented skipped external tests only | `271 passed, 17 skipped in 4.84s`; skipped tests require `STAGE02_ONLINE_DATABASE_URL` |
| `python scripts/stage05_skill_openrouter_smoke.py` | pass | Passed real OpenRouter smoke, 5/5 redacted cases, provider disabled, Telegram dry-run |
| `git diff --check` | no whitespace errors | Passed with line-ending warnings only |
| secret scan | no high-risk secrets | Passed; high-risk token/private-key scan returned no matches outside ignored local/doc paths |

## 7. Temporary Cleanup

Before final submission:

- Remove any temporary scripts not intended as durable tools.
- Remove temporary outputs from OpenRouter smoke.
- Do not commit raw model responses, secrets, chat ids, allowlists, customer names or provider credentials.
- Keep formal fixtures and scripts only if they are durable regression assets.

Result:

- No OpenRouter smoke output file was written.
- Formal fixture `backend/tests/fixtures/stage05_skill_cases.json` is kept as a durable regression asset.
- No `__pycache__` directories remained under `backend/app`, `backend/tests` or `backend/scripts` during cleanup check.
- `.pytest_cache` was attempted for deletion, but Windows denied ACL read/delete access even after a scoped takeown/icacls attempt. It remains ignored by git and is not a source artifact.

## 8. Tencent Cloud Staging Re-Acceptance

| Item | Evidence | Status |
| --- | --- | --- |
| Reviewed commit deployed | Staging repo HEAD `558493b2fb95a58ba3a457f68312f824b6a71704` | Passed |
| Migration head | `alembic current`: `20260707_0016 (head)` | Passed |
| Runtime window | API/worker summary showed `llm_enabled=true`, `agent_workflow_mode=real_openrouter`, OpenRouter key present, `telegram_send_mode=dry_run`, `provider_mode=disabled`, prompt/response raw storage disabled | Passed |
| Health | `GET https://api.jiangtest1.online/health`: `{"status":"ok"}` | Passed |
| Recharge skill | Trace `tg:184365910`; OpenRouter AgentRun `4fc1e067-2a14-464c-b59a-620d9e0c2738`; selected `recharge-draft`; created pending `recharge` draft `e16bf18d-0c6b-44b3-86da-7aa24b91a7db` | Passed |
| BM invite skill | Trace `tg:184365911`; AgentRun `485a4796-07c3-49cd-b94e-a8a84a32f389`; selected `bm-invite-draft` and `project-contact`; created pending `bm_invite` draft `85badebb-515e-4ff0-aade-082c3d54a9b7` | Passed |
| Spend query boundary | Trace `tg:184365912`; AgentRun `f74a572b-f8e3-49f0-95b4-9a5ec5a4af39`; selected `spend-query`, `project-tabular-analysis`, `manual-review-handoff`; fallback `manual_review`; no draft | Passed |
| Manual review task boundary | Trace `tg:184365913`; selected `project-task` and `manual-review-handoff`; no draft/send/execution side effects | Passed |
| Approval boundary | Trace `tg:184365914`; selected `manual-review-handoff`; no draft/send/execution side effects | Passed |
| Future workflow boundary | Trace `tg:184365915`; selected `project-daily-operations-workflow`; fallback `future_scope`; no draft/send/execution side effects | Passed |
| Side effects blocked | For traces `tg:184365910` through `tg:184365915`: `telegram_send_requests=0`, `service_records=0`, `execution_tickets=0`, `execution_logs=0` | Passed |
| Safety close | API/worker summary after close showed `llm_enabled=false`, `agent_workflow_mode=fake`, `telegram_send_mode=dry_run`, allowlist absent, `provider_mode=disabled`; pending/sendable Telegram requests `0`; execution tickets `0` | Passed |

Not covered in this re-acceptance:

- `card-binding-draft` and `account-exception-marking` were covered by local real OpenRouter smoke and previous Stage05 account-exception staging evidence, but not re-sent in this six-message staging pass.
- No real Telegram send was performed in this re-acceptance; Telegram remained `dry_run`.
- No provider, funds, card, Meta/BM execution, account production or automatic replacement was performed.
