# Stage06 Skill Hit Rate Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable Stage06 skill-matching benchmark so routing hit rate can be verified instead of inferred from smoke tests.

**Architecture:** Keep the existing deterministic Stage06 matcher as the system under test. Add a generic work-scenario fixture corpus and a small evaluator script that reports top-1, top-3, high-risk, hidden-field and missing-context gates without calling external services.

**Tech Stack:** Python 3.12, pytest, JSON fixtures, existing Stage06 skill manifest and matcher.

## Global Constraints

- Do not change Stage06 product direction, schema, API contract or permission model.
- Do not introduce Feishu/Lark API runtime calls.
- Do not reintroduce advertising-agency skills or prompts as Stage06 defaults.
- Keep the benchmark deterministic and local; real OpenRouter multi-prompt smoke remains a separate verification lane.
- Use TDD: add failing tests before adding the evaluator and corpus.

---

### Task 1: Benchmark Contract Tests

**Files:**
- Create: `backend/tests/unit/test_stage06_skill_hit_rate_benchmark.py`
- Create later: `backend/tests/fixtures/stage06_skill_matching_cases.json`
- Create later: `backend/scripts/stage06_skill_hit_rate_eval.py`

**Interfaces:**
- Consumes: `app.agents.stage06_skill_matching.build_stage06_skill_evidence`
- Produces: `load_cases(path)`, `evaluate_cases(cases)`, `DEFAULT_GATES`

- [x] **Step 1: Write failing tests**

```python
def test_stage06_skill_hit_rate_fixture_meets_minimum_shape() -> None:
    cases = load_cases(FIXTURE_PATH)
    assert len(cases) >= 108
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stage06_skill_hit_rate_benchmark.py -q`

Expected: FAIL because `stage06_skill_hit_rate_eval.py` and fixture do not exist.

- [x] **Step 3: Add the fixture and evaluator**

Add a JSON fixture with positive, negative, ambiguous, high-risk, permission and missing-context cases. Add an evaluator that calls `build_stage06_skill_evidence` and computes gates.

- [x] **Step 4: Run the focused benchmark tests**

Run: `pytest tests/unit/test_stage06_skill_hit_rate_benchmark.py -q`

Expected: PASS.

### Task 2: Documentation And Regression

**Files:**
- Modify: `project-docs/08-implementation/STAGE_06_LARKSUITE_SKILLS_INTEGRATION_DESIGN.md`
- Modify: `project-docs/08-implementation/STAGE_06_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_06_REMAINING_RISKS_AND_NEXT_CASES.md`

**Interfaces:**
- Consumes: Task 1 benchmark result.
- Produces: Updated Stage06 status wording distinguishing smoke prompts, deterministic hit-rate benchmark and full backend tool coverage.

- [x] **Step 1: Update docs after tests pass**

Record benchmark gates and actual command output. Keep remaining risks explicit for live LLM rerank and all-27 backend tools.

- [x] **Step 2: Run verification**

Run:

```powershell
pytest tests/unit/test_stage06_skill_hit_rate_benchmark.py tests/unit/test_stage06_skill_matching.py tests/unit/test_stage06_skill_registry.py -q
python scripts/stage06_skill_hit_rate_eval.py
pytest -q
git diff --check
```

Expected: all tests pass except existing documented external skips in the full suite; whitespace check has no whitespace errors.
