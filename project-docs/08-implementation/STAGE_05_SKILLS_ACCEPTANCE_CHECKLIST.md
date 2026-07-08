# Stage 05 Skills Extension Acceptance Checklist

## Status

- Document status: active acceptance checklist
- Scope: Requirement-by-requirement acceptance for Stage05 Skills Extension.
- Current Progress: 2026-07-09 Updated after implementation and verification. Static registry, sidecar matching, AgentRun evidence, local tests and real OpenRouter smoke passed. One local `.pytest_cache` cleanup attempt was blocked by Windows ACL and is documented below.

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
