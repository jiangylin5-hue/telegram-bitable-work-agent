# Stage 05 Skills Extension Implementation Plan

## Status

- Document status: active implementation plan
- Scope: Static skill registry, sidecar candidate logging and local verification for Stage05 Skills Extension.
- Current Progress: 2026-07-09 Implemented and locally verified. Static registry, sidecar matching, AgentRun evidence, fixtures, OpenRouter smoke and backend regression are complete; no staging deployment is included in this extension.

## 1. Implementation Sequence

### Task 1: Preserve current audit

Status: completed before this plan.

- Commit the existing 27-skill reference audit separately.
- Keep that commit as the durable artifact for larksuite source analysis.

### Task 2: Add documentation package

Status: completed.

Deliverables:

- `STAGE_05_SKILLS_EXTENSION_SOURCE_OF_TRUTH.md`
- `STAGE_05_SKILLS_EXTENSION_IMPLEMENTATION_PLAN.md`
- `STAGE_05_SKILLS_MANIFEST_DESIGN.md`
- `STAGE_05_SKILLS_ACCEPTANCE_CHECKLIST.md`
- `modules/STAGE_05_LARKSUITE_SKILLS_OFFICIAL_SUMMARY.md`

Acceptance:

- Docs state that this is post-Stage05 extension work.
- Docs state sidecar logging does not change current business decisions.
- Docs state reporting is future scope.

### Task 3: Implement static registry

Status: completed.

Expected files:

- `backend/app/agents/stage05_skills.py`

Rules:

- Use static Python objects.
- Do not create dynamic plugin loading.
- Do not create Codex skills.
- Include P0/P1 adapter skills and approved business skills.
- Exclude `report-draft`.

Acceptance:

- Unit tests prove registry ids, layers, source references, endpoints and forbidden actions.

### Task 4: Implement skill matching evidence

Status: completed.

Expected files:

- `backend/app/agents/stage05_skill_matching.py`

Rules:

- Input: Router result + redacted source text.
- Output: JSON-serializable evidence.
- Include candidate, selected, rejected/future/manual-review evidence.
- Do not mutate service drafts, accounts, sends or providers.

Acceptance:

- Fixture-driven tests prove expected selected skills.
- Spend and report cases do not execute business actions.

### Task 5: Attach evidence to AgentRun

Status: completed.

Expected files:

- `backend/app/services/agent_workflows.py`

Rules:

- Enrich router `AgentRun.output_summary` with `skill_evidence`.
- Preserve existing `redacted_summary`, intents and created entity behavior.
- Do not change `select_child_agents` business decision behavior.

Acceptance:

- Existing Stage05 workflow tests still pass.
- New test proves `agent_runs.output_summary.skill_evidence` exists.

### Task 6: Add fixtures and tests

Status: completed.

Expected files:

- `backend/tests/fixtures/stage05_skill_cases.json`
- `backend/tests/unit/test_stage05_skill_registry.py`
- `backend/tests/unit/test_stage05_skill_matching.py`
- targeted integration assertions in Stage05 workflow tests

Acceptance:

- Fixtures are formal regression assets, not temporary fake data.
- Cases cover recharge+reply, BM invite, spend query/table, card binding, account exception and future reporting.

### Task 7: Add local OpenRouter smoke

Status: completed.

Expected files:

- `backend/scripts/stage05_skill_openrouter_smoke.py`

Rules:

- Use five redacted cases.
- Call real OpenRouter locally.
- Output only redacted skill evidence summary.
- Do not send Telegram.
- Do not call provider.
- Do not write secrets or raw responses.

Acceptance:

- Script exits 0 only when real OpenRouter returns valid JSON and skill evidence is built for all five cases.

### Task 8: Verification and cleanup

Status: completed with one local cleanup note.

Commands:

```powershell
cd backend
pytest tests/unit/test_stage05_skill_registry.py tests/unit/test_stage05_skill_matching.py -q
pytest tests -k stage05 -q
pytest tests -q
python scripts/stage05_skill_openrouter_smoke.py
cd ..
git diff --check
```

Additional checks:

- Secret scan for high-risk tokens.
- Temporary file/interface/test data cleanup.
- Acceptance checklist update with real command results.

Actual results:

- Targeted skill tests: `10 passed in 0.06s`.
- Stage05 focused tests: `98 passed, 190 deselected in 3.11s`.
- Full backend tests: `271 passed, 17 skipped in 4.84s`; skipped tests require `STAGE02_ONLINE_DATABASE_URL`.
- Real OpenRouter smoke: `ok: true`, 5/5 redacted cases, provider disabled, Telegram dry-run.
- `git diff --check`: line-ending warnings only.
- Temporary cleanup: no `__pycache__` remained; `.pytest_cache` deletion was attempted but Windows ACL denied access.

## 2. Rollback Boundary

If skill matching causes existing business workflow outputs to change, revert the runtime integration and keep only registry/matching tests until the behavior difference is explicitly approved.
