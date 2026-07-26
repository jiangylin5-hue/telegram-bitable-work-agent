# Stage09 LLM Skill Launcher Implementation Plan

> **Execution rule:** Use `superpowers:subagent-driven-development`, strict TDD and task-scoped review. Do not create task-level commits. Keep all changes unstaged until the complete Stage09 acceptance/audit package is ready for one final squash commit.

**Goal:** Replace prompt-only frontend skill tags with a backend-curated, permission-filtered and auditable skill launcher that materially constrains Stage08 context eligibility, OpenRouter actions, idempotency and safe results.

**Design authority:** `project-docs/08-implementation/STAGE_09_LLM_SKILL_LAUNCHER_DESIGN.md`

## Global Constraints

- Reuse `backend/app/agents/stage06_skills.py` and the Stage06 matcher as the single source of truth for the earlier `larksuite/cli`-derived capability organization; do not introduce or copy a second general skill framework.
- Public skills are exactly `platform-base`, `platform-tabular-analysis`, `platform-task` and `platform-telegram-im`.
- `platform-shared-policy` is always server-attached; `platform-approval` is attached only for write-like drafts.
- No database model, Alembic migration, dynamic import, plugin installation, arbitrary `SKILL.md` loading or client-provided prompt/tool/policy data.
- Existing sync `/query` and SSE `/query-stream` share one resolver, command, runtime, validation, replay and audit path.
- Missing/ambiguous/revoked employee, resource, record, field or Telegram scope fails closed before provider invocation.
- Existing clients may omit `skill_id`; omitted/null means deterministic server auto mode.
- No real external writes, Telegram sends, deployment or production mutations.
- Write tests first, run them and observe the expected failure before production edits.
- Preserve all unrelated dirty-worktree changes; do not stage or commit.

### Task 1: Add the curated skill catalog and permission resolver

**Files:**

- Create `backend/app/services/stage09_skill_launcher.py`
- Modify `backend/app/schemas/stage08_collaboration.py`
- Modify `backend/app/api/routes/stage08_collaboration.py`
- Add `backend/tests/unit/test_stage09_skill_launcher.py`
- Extend `backend/tests/api/test_stage08_collaboration_api.py`

**Required public contract:**

```http
GET /api/stage08/assistant/skills
    ?workspace_id={uuid}
    &employee_id={uuid}
    &target_record_id={uuid?}
```

Response:

```json
{
  "manifest_version": "stage06-larksuite-skills-v1",
  "default_selection": "auto",
  "skills": [
    {
      "skill_id": "platform-tabular-analysis",
      "label": "汇总分析",
      "description": "基于已授权表格与视图整理结论",
      "enabled": true,
      "disabled_reason": null,
      "supported_intents": ["business_fact", "mixed"],
      "supported_actions": ["read_only"],
      "confirmation_policy": "read_only"
    }
  ]
}
```

Allowed `disabled_reason` values:

```text
context_required
read_scope_unavailable
write_scope_unavailable
chat_scope_unavailable
runtime_unsupported
```

**TDD sequence:**

1. RED: catalog returns the four public skills in stable order and never returns internal/inactive skills.
2. RED: inactive workspace/employee/base, ineligible member or malformed scope is rejected through the existing redacted API error boundary.
3. RED: read skills require current employee table/view scope.
4. RED: Telegram skill requires one current binding and one current business-context mapping; ambiguity disables it.
5. RED: draft actions are absent unless the target record is active/visible, belongs to an employee table, employee allows `draft_update`, and actor/employee field-policy intersection has at least one writable field.
6. GREEN: implement immutable presentation definitions and a resolver using Stage06 manifests plus existing authorization/permission services.
7. GREEN: expose the read-only endpoint and strict response schemas.
8. Run focused resolver/API tests and relevant Stage06 permission tests.

**Important implementation details:**

- The catalog is a capability snapshot, never an execution ticket.
- Do not trust client chat/base/table/view/field IDs beyond the three declared query parameters.
- Do not expose manifest triggers, forbidden-action internals, prompts, tool names, raw field policies or scope IDs.
- `platform-base` and `platform-task` may advertise both `read_only` and `draft_update` only when strict draft proof exists.
- `platform-tabular-analysis` and `platform-telegram-im` are read-only in this release.

### Task 2: Bind the resolved skill profile to query, LLM, replay and audit

**Files:**

- Modify `backend/app/schemas/stage08_collaboration.py`
- Modify `backend/app/api/routes/stage08_collaboration.py`
- Modify `backend/app/runtime/stage08_collaboration_contracts.py`
- Modify `backend/app/services/stage08_collaboration.py`
- Modify `backend/app/services/stage08_openrouter_analysis_provider.py`
- Extend `backend/tests/api/test_stage08_collaboration_api.py`
- Extend `backend/tests/unit/test_stage08_collaboration_service.py`
- Extend `backend/tests/unit/test_stage08_openrouter_analysis_provider.py`
- Add or extend audit/replay tests in the nearest existing Stage08 suites

**Request extension:**

```python
skill_id: StrictStr | None = Field(default=None, min_length=1, max_length=120)
```

**Safe result extension:**

```json
{
  "skill": {
    "skill_id": "platform-tabular-analysis",
    "label": "汇总分析",
    "manifest_version": "stage06-larksuite-skills-v1",
    "selection_mode": "explicit"
  }
}
```

**TDD sequence:**

1. RED: explicit public skill resolves; unknown/internal/inactive skill fails before provider invocation.
2. RED: explicit skill rejects incompatible intent/action combinations.
3. RED: null skill uses deterministic auto selection restricted to public runtime-supported skills.
4. RED: command snapshot carries a server-issued profile sourced from the Stage06 manifest, including internal `source_skill`; client mappings cannot forge supporting skills, source mapping or allowed actions.
5. RED: `_query_fingerprint` differs by resolved primary skill, selection mode and manifest version.
6. RED: sync, SSE result and replay return identical safe skill summaries.
7. RED: provider prompt receives only the safe profile projection and rejects an action outside `allowed_provider_actions`.
8. RED: `platform-telegram-im` cannot fall back to ordinary table context when chat proof is absent.
9. RED: AgentRun input/output summary and terminal audit contain manifest version, primary ID, selection mode and supporting IDs without query/evidence text.
10. GREEN: extend private command/profile contracts and shared prepare/runtime path.
11. GREEN: extend provider prompt/action validation.
12. GREEN: extend SafeView, replay projection, terminal run and audit summaries.
13. Run Stage06 matcher tests, Stage08 API/service/provider/audit focused suites.

**Compatibility matrix:**

| skill | allowed intents | allowed actions |
| --- | --- | --- |
| `platform-base` | `business_fact`, `mixed` | `read_only`, conditional `draft_update` |
| `platform-tabular-analysis` | `business_fact`, `mixed` | `read_only` |
| `platform-task` | `business_fact`, `mixed` | `read_only`, conditional `draft_update` |
| `platform-telegram-im` | `mixed` | `read_only` |

Auto mode keeps the existing four intents and existing action vocabulary, but its resolved primary skill must still be public, active, runtime-supported and permission-allowed.

### Task 3: Replace static frontend tags with the server skill catalog

**Files:**

- Modify `mini-app/src/app/stage08-collaboration-types.ts`
- Modify `mini-app/src/app/api.ts`
- Modify `mini-app/src/app/CollaborationWorkbench.tsx`
- Modify `mini-app/src/app/App.tsx` only where request/context wiring requires it
- Extend `mini-app/src/test/stage08-collaboration-api.test.ts`
- Extend `mini-app/src/test/collaboration-workbench.test.tsx`
- Extend app-flow tests only for observable integration behavior

**TDD sequence:**

1. RED: strict catalog parser accepts the complete real response and rejects malformed/unknown fields and unsafe disabled reasons.
2. RED: API sends workspace/employee/optional record and preserves identity headers.
3. RED: workbench renders `auto` plus server catalog entries; no hard-coded capability fallback exists.
4. RED: disabled skills are not selectable and show the returned safe reason.
5. RED: explicit selection submits `skill_id`; auto submits `null`.
6. RED: employee/record change clears selection and prevents a stale enabled state from carrying across scopes.
7. RED: result skill summary must match an explicit request before the turn can complete.
8. RED: draft mode is available only when the catalog explicitly lists `draft_update`; `recordId` or employee intent alone is insufficient.
9. GREEN: add types/parser/API method and protected query key.
10. GREEN: wire server catalog into `SkillStrip` and request reducer.
11. Remove the six-item static `SkillDefinition` capability source.
12. Ensure the local Vite acceptance proxy forwards the Stage08 `/api` namespace to FastAPI. Otherwise a real catalog request is answered by the Vite fallback and is silently rendered as an empty catalog, which invalidates browser acceptance even though the backend endpoint is correct.
13. Run frontend API/stream/workbench/app-flow and Vite-proxy focused tests, TypeScript and build.

### Task 4: Close the Ledgerline review findings after skill integration

**Files:**

- Modify `mini-app/src/app/CollaborationWorkbench.tsx`
- Modify `mini-app/src/app/App.tsx`
- Modify `mini-app/src/styles.css`
- Extend `mini-app/src/test/collaboration-workbench.test.tsx`
- Extend `mini-app/src/test/assistant-context-app-flow.test.tsx`
- Extend `mini-app/src/test/collaboration-app-flow.test.tsx`

**TDD sequence:**

1. RED: `result` stores SafeView and enters `finalizing`; only parser-validated `done + EOF` resolves to `completed`.
2. RED: missing/invalid `done` after result ends in `failed`.
3. RED: reducer locks the first server request ID and strict sequence.
4. RED: wide Base entry uses the Ledgerline dialog, not the legacy `520px` side panel.
5. RED: opening focuses Composer; Tab/Shift+Tab trap focus; background is isolated; Escape closes; trigger focus is restored.
6. RED: timeline auto-follows only while near the bottom.
7. GREEN: implement the minimal reducer/dialog/focus/scroll corrections.
8. RED: at the compact breakpoint, an open full-screen record detail exposes a current-record collaboration entry; it must be absent while a human edit is in progress.
9. GREEN: reuse the existing collaboration opener from that entry without closing the record detail or changing the record/permission contract; make the portal backdrop a fixed layer above the full-screen record detail.
10. Re-run Task 3 and Task 4 focused frontend suites, TypeScript and build.

### Task 5: Nginx, whole-stage verification, review and one final commit

**Files:**

- Modify the existing Stage09 Nginx templates and render tests named in the main Stage09 SSE plan.
- Update current Stage09 progress/handoff/design/implementation/evidence documents.
- Create only retained, sanitized acceptance evidence.

**Execution:**

1. TDD the rendered Nginx SSE location: buffering/cache off, `X-Accel-Buffering: no`, existing upstream/header shape preserved, read timeout not shorter than runtime budget.
2. Run backend skill/Stage08 focused tests.
3. Run the complete backend test suite and record pass/skip/fail counts.
4. Run frontend focused tests, full serial suite, TypeScript and production build.
5. Run deployment asset render/verification tests without deploying.
6. Run Product Design browser QA at desktop and compact breakpoints; compare the selected Ledgerline reference and implementation using the same viewport/state.
7. Run security review for scope revocation, prompt/profile forgery, error redaction, replay and draft confirmation.
8. Audit docs, generated artifacts, untracked files, ignored SDD files, other worktrees and `git diff --check`.
9. Request a whole-branch code review and address all Critical/Important findings.
10. Do not deploy, push or perform real writes.
11. After every acceptance and audit item is green, squash all local Stage09 checkpoint commits and unstaged work from base `b57b152` into one final commit, then emit the commit directive.

## Acceptance

- Four curated skills and auto mode are server-driven and permission-safe.
- Explicit skill selection materially changes command/profile/provider validation/audit, not only UI copy.
- No internal/inactive skill or stale scope can reach the provider.
- Sync, SSE and replay stay equivalent.
- Draft remains proposal-only and requires current field-level proof plus confirmation.
- Ledgerline interaction review findings are closed.
- Full automated, visual, security and documentation evidence is complete.
- Exactly one final Stage09 commit exists above `b57b152`; nothing is pushed or deployed.
