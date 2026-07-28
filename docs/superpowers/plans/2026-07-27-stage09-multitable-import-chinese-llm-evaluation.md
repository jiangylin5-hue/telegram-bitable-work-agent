# Stage09 Multi-table Import and Chinese LLM Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import a dedicated three-table fictional Base with service-created links and publish a truthful twenty-case Chinese real-OpenRouter evaluation report.

**Architecture:** Existing CSV import jobs create `projects`, `work_items`, and `risks` in one Base. A post-import relation phase resolves fixture keys to same-Base records and uses `create_field` plus `update_record`, letting `stage06_platform` validate targets and create `record_links`. A bounded child-local evaluator reuses only the visible fixture projection and the existing live employee/OpenRouter path.

**Tech Stack:** Python 3.12, FastAPI domain services, SQLAlchemy/PostgreSQL, OpenRouter-compatible structured client, pytest, CSV fixtures, Markdown/JSON evidence.

## Global Constraints

- Use only fictional non-personal fixture data and existing domain services; never raw SQL for import or links.
- The imported Base is dedicated and retained; existing user records are read-only and out of scope.
- No migration, Telegram, draft confirmation, notification, provider write or runtime-env change.
- Report query/answer retention is limited to the fictional fixture and excludes credentials, request IDs and system prompts.
- Do not commit until import, real evaluation, audit and report are complete.

---

### Task 1: Fixture and import/link contract

**Files:**
- Create: `backend/scripts/stage09_multitable_chinese_eval.py`
- Create: `backend/tests/unit/test_stage09_multitable_chinese_eval.py`
- Modify: `project-docs/08-implementation/STAGE_09_MULTI_TABLE_IMPORT_AND_CHINESE_LLM_EVALUATION.md`

**Interfaces:**
- Produces `build_multitable_fixture(uow, actor) -> MultiTableFixture` with `base_id`, imported tables, stable-key maps and visible evaluation view.
- Produces `verify_multitable_fixture(fixture) -> dict[str, int]` with table/field/record/edge counts.

- [ ] **Step 1: Write failing import/link assertions**

```python
fixture = build_multitable_fixture(InMemoryStage06PlatformUnitOfWork(), owner)
assert verify_multitable_fixture(fixture) == {
    "table_count": 3, "record_count": 32, "relation_field_count": 2, "edge_count": 26,
}
```

- [ ] **Step 2: Run the focused test and observe the missing helper failure**

Run: `python -m pytest backend/tests/unit/test_stage09_multitable_chinese_eval.py -q`

- [ ] **Step 3: Implement imports and links via domain services**

```python
job = create_import_job_from_csv(uow, workspace.id, file_name="projects.csv", content=csv_text, created_by_user_id=actor.actor_id, base_id=base_id)
result = commit_import_job(uow, job.id, base_name="多表关联中文评测样例", table_name="Projects", table_key="projects", field_mapping=None, actor=actor)
create_field(uow, work_items.id, name="Project", key="project_link", field_type="linked_record", options={"target_table_id": str(projects.id)}, actor=actor)
update_record(uow, work_item.id, values={"project_link": [str(project.id)]}, expected_version=work_item.version, actor=actor)
```

- [ ] **Step 4: Run focused tests and verify exact count/edge assertions pass**

Run: `python -m pytest backend/tests/unit/test_stage09_multitable_chinese_eval.py -q`

### Task 2: Chinese case oracle and report shape

**Files:**
- Modify: `backend/scripts/stage09_multitable_chinese_eval.py`
- Modify: `backend/tests/unit/test_stage09_multitable_chinese_eval.py`

**Interfaces:**
- Produces `build_chinese_cases(fixture) -> tuple[RealTableEvalCase, ...]` with exactly 20 cases.
- Produces `render_report(result) -> str` containing per-case query, answer, skills, recall, precision and score.

- [ ] **Step 1: Write a failing twenty-case/oracle test**

```python
cases = build_chinese_cases(fixture)
assert len(cases) == 20
assert sum(any("一" <= char <= "龥" for char in case.prompt) for case in cases) >= 12
assert {case.kind for case in cases} >= {"exact", "filter", "aggregate", "negative", "guard"}
```

- [ ] **Step 2: Implement deterministic truth sets and guard cases**

Use visible `ticket_code`, `project_code`, status and risk fields for truth. The two guard cases name restricted fixture-only keys and must select `platform-shared-policy` without a provider call.

- [ ] **Step 3: Run oracle tests**

Run: `python -m pytest backend/tests/unit/test_stage09_multitable_chinese_eval.py -q`

### Task 3: Real execution and evidence

**Files:**
- Create: `project-docs/08-implementation/evidence/stage09-multitable-chinese-real-llm-report-2026-07-27.md`
- Create: `project-docs/08-implementation/evidence/stage09-multitable-chinese-real-llm-report-2026-07-27.json`

- [ ] **Step 1: Run focused unit tests, related provider tests and Mini App production build**

Run: `python -m pytest backend/tests/unit/test_stage09_multitable_chinese_eval.py backend/tests/unit/test_stage08_openrouter_analysis_provider.py -q` and `npm.cmd run build` in `mini-app`.

- [ ] **Step 2: Deploy matching candidate and verify readiness before import**

Use the existing source/venv/static sealed-release and bounded readiness protocol. Record only artifact ID, gate outcomes, unit states and status codes.

- [ ] **Step 3: Execute the service-account import and bounded live batch once**

Run the maintenance entry point with existing runtime credentials, no printed environment values, bounded per-case child timeouts, and no retry that widens the data projection.

- [ ] **Step 4: Create the report and audit**

The report must retain only fixture query/answer text, selected skills, cited fixture codes and calculated scores. Run `git diff --check`, record skipped tests/risks and keep all changes uncommitted.
