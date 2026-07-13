Exit code: 0
Wall time: 0.4 seconds
Output:
# Stage07 S5.3 Team Bot Knowledge Entry Implementation Plan

> **For agentic workers:** Required skills already applied: `writing-plans`, `executing-plans`, `test-driven-development`, and `verification-before-completion`. Implement each task with a RED test, the smallest GREEN change, a focused regression command, and a focused commit.

**Goal:** Deliver TD011 as a separate Home `Team Bot` workbench. It lets an eligible member select an existing active, summary-capable digital employee and one permitted saved view, then request a one-shot, permission-filtered knowledge summary. The result is safe text, opaque record citations, a truncation flag and an opaque audit reference. It does not create a new employee type, persistent chat/memory, direct record write, record picker or general knowledge base.

**Approved boundary (2026-07-14):** The user approved TD011 Option A+B and then instructed implementation. The server owns all employee/view/record authorization; the client only renders safe DTOs and rereads its selected context immediately before a summary. The existing Stage06 LangGraph/OpenRouter runtime is reused through a server-only bounded-record override. This is an internal adapter extension, not a client-supplied context API.

**Architecture:** Retain the product chain `workspace -> base -> saved view -> permission-filtered records -> configured digital employee -> audit`. A narrow Team Bot service resolves contact eligibility and its permitted saved-view knowledge contexts. It loads `101` visible records, passes at most the first `100` to the live Stage06 runtime, derives `truncated` solely from the 101st record, and reprojects citations against the same visible window. It reuses the current TD010 member eligibility, current `digital_employee.invoke` action, Stage06 employee action validation, Stage06 idempotency pattern, audit service and the Mini App strict-parser/protected-query conventions.

**Tech stack:** Existing FastAPI, SQLAlchemy 2.x, PostgreSQL JSONB view projections, LangGraph/OpenRouter-compatible structured runtime, React, Vite, TypeScript, TanStack Query and Vitest. No schema migration, new index, new RBAC action, provider replacement or frontend framework is introduced.

**Current Progress (2026-07-14):** Tasks 1--5 are implemented locally in commits `2b173fc`, `11c229e`, `0c1e900` and `d36f002`. Task 6 proportional verification is complete: focused backend `23 passed`; disposable local PostgreSQL `1 passed`; full Mini App `60 files / 221 tests`; production build passed. User-controlled visual review, real OpenRouter/Telegram, staging/production and the untested BDD matrix rows remain open.

## Global Constraints

- A contact must be `active`, member-eligible, authorized for `digital_employee.invoke`, and configured for `summarize`; it is not enough to be merely readable.
- Team Bot accepts one Base and one currently permitted saved view. It never accepts browser-provided records, fields, provider settings, policy JSON, trace data, record contents or an arbitrary prompt.
- `instruction` is optional and at most 600 characters. The output is one-shot only; no messages, thread, personal memory, shared persistent memory, upload, bot routing or provider configuration UI exists.
- The server loads exactly enough for the bounded window: first 100 may enter the runtime; record 101 only sets `truncated=True`; later records never enter response, audit or runtime state.
- The summary operation requires `Idempotency-Key`. Same key and same normalized request returns the stored safe receipt; a changed request conflicts and must not make a second provider call.
- Empty visible context returns `kind=empty_context`, writes a redacted audit event and does not call the provider.
- Safe citations contain opaque `record_id` only and must be present in the summary request's visible window. Raw field values, employee policy/runtime configuration, prompt/provider request, error internals and audit state never cross the Team Bot contract.
- `draft_update` stays on TD006's current Canvas record bridge. Team Bot is summary-only and its Home entry always offers an explicit Base handoff instead of record mutation controls.
- This plan intentionally makes no database model, migration or index change. PostgreSQL validation exercises the existing record/view/permission path only.
- Browser control is out of scope by user instruction. Manual visual validation remains explicitly open unless a user-performed check is later reported.

## Task 1: Define strict team DTOs and prove the contract fails closed

**Files:**

- Create `backend/app/schemas/stage07_team_bot_knowledge.py`.
- Create `backend/tests/unit/test_stage07_team_bot_knowledge_api.py`.
- Modify `project-docs/08-implementation/STAGE_07_TECHNICAL_DECISION_011_TEAM_BOT_KNOWLEDGE_ENTRY.md`, `project-docs/08-implementation/STAGE_07_TEAM_BOT_KNOWLEDGE_ENTRY_SDD.md`, and `project-docs/08-implementation/STAGE_07_SUBSTAGE_DELIVERY_ROADMAP.md` to record approved-for-implementation status before route code starts.

**Interfaces produced:**

```python
class TeamBotSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_id: UUID
    view_id: UUID
    instruction: str | None = Field(default=None, max_length=600)

class TeamBotSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["summary", "empty_context"]
    employee_id: UUID
    base_id: UUID
    view_id: UUID
    answer: str
    citations: list[SafeCitationResponse]
    truncated: bool
    audit_id: UUID
```

`TeamBotContactResponse` and `TeamBotKnowledgeContextResponse` are separate from the personal-assistant DTOs. Their roots contain only IDs, names/descriptions, Base/view presentation metadata and documented intent labels; they omit policy, raw records, record values, runtime, provider, trace, grants and employee configuration.

**RED test:** add route-contract tests that assert exact documented roots, `extra="forbid"`, UUID/non-empty validation, 600-character instruction boundary, no `draft_update` or generic query intent, and no safe response key can expose `records`, `fields`, `runtime`, `provider`, `trace`, `policy` or audit state. The test initially fails because schemas/routes do not exist.

**GREEN implementation:** add only strict Pydantic DTOs and approval-status documentation update. Do not add a persistence model or migration. Run:

```powershell
python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_api.py
```

Commit: `docs(stage07): approve team bot knowledge implementation` after the doc-only boundary change, then continue code in later commits.

## Task 2: Add a server-only bounded runtime input path

**Files:**

- Modify `backend/app/services/stage06_digital_employees.py`.
- Create `backend/tests/unit/test_stage07_team_bot_knowledge_service.py`.
- Reuse existing Stage06 live employee tests for regression.

**Interfaces produced:**

```python
def invoke_digital_employee(
    ...,
    view_records_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ...
```

The optional value is internal service input only. It is accepted only by the live `summarize` branch after the ordinary employee action and configured-view checks. `_invoke_live_digital_employee` uses the override as already permission-filtered `{id, fields}` records; when omitted, all existing callers retain their current `list_view_records` behavior. `draft_update`, deterministic mode and every browser DTO remain unchanged.

**RED test:** use a fake structured LLM and 101 generated visible records. Assert the live runtime receives exactly 100 records with their opaque IDs/field payload, `record_count==100`, and no 101st record value appears in the captured provider input or response. Also assert a caller cannot use the override for `draft_update`, a view outside employee scope still fails, and legacy S5 summary behavior remains unchanged when no override is supplied.

**GREEN implementation:** add the narrow optional parameter and validation. Keep the current Stage06 action/service/audit machinery; do not invent a second LLM gateway or alter provider configurations. Run:

```powershell
python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_service.py tests/unit/test_stage06_digital_employees.py
```

Commit: `feat(stage07): bound team bot runtime context`.

## Task 3: Implement Team Bot context resolution, audit and idempotent APIs

**Files:**

- Create `backend/app/services/stage07_team_bot_knowledge.py`.
- Create `backend/app/api/routes/stage07_team_bot_knowledge.py`.
- Modify `backend/app/main.py` only if the current Stage07 router layout requires a new router registration.
- Modify `backend/tests/unit/test_stage07_team_bot_knowledge_api.py`.
- Create `backend/tests/integration/test_stage07_team_bot_knowledge_postgres.py`.

**Service responsibilities:**

| Function | Required behavior |
| --- | --- |
| `list_team_bot_contacts` | Require workspace `digital_employee.invoke`; return only `active`, TD010 member-eligible employees configured with `summarize`. |
| `list_team_bot_knowledge_contexts` | Resolve one eligible employee and caller; require its configured Base; return only configured, permitted saved views with current safe presentation. |
| `resolve_team_bot_knowledge_view` | Revalidate contact, Base and view at command time; call `list_view_records(..., limit=101)`; retain first 100 for runtime/citation guard and compute `truncated` from row 101. |
| `summarize_team_bot_knowledge` | Reject changed idempotency payloads; return stored safe receipt for replay; return audited empty receipt without provider call if no visible records; otherwise call the Stage06 live runtime with the 100-record internal override, sanitize/reproject citations, and write a redacted Team Bot audit receipt. |

**Routes:**

```text
GET  /mini-app/workspaces/{workspace_id}/team-bot-contacts
GET  /mini-app/team-bots/{employee_id}/knowledge-contexts
GET  /mini-app/team-bots/{employee_id}/knowledge-contexts/{view_id}
POST /mini-app/team-bots/{employee_id}/summaries
```

The POST receives `Idempotency-Key`, body `base_id`, `view_id`, optional `instruction`, and has no `record_id`, `intent`, `records` or arbitrary action field. The response exposes the Team Bot safe receipt only. The audit event contains IDs/counts/truncation/outcome and safe summary metadata, never record values, prompt, response text, provider details or raw runtime output. Its `audit_id` becomes the opaque receipt reference.

**RED tests:**

- Contacts hide paused/draft, non-member, read-only, and non-summary-capable employees; direct routes return a generic safe denial rather than assignment/policy details.
- Context discovery respects employee Base/table/view scope and current caller visibility; a stale/removed view fails on the reread.
- Exactly 101 visible records cause `truncated=True`, exactly 100 causes `False`, and only 100 reach the LLM. Citations for non-window/non-visible records are suppressed.
- Empty context returns `empty_context`, `truncated=False`, citation `[]`, has an audit reference and invokes no fake client.
- Same idempotency key replays result without a second fake client invocation; changed normalized request returns conflict.
- 401/403/404/409/422 transport behavior, malformed provider output and runtime error use fixed safe response/error handling without raw data leaks.

**GREEN implementation:** compose existing `authorize_workspace_action`, `is_member_eligible_for_employee`, employee action/view helpers, `get_view_presentation`, `list_view_records`, Stage06 idempotency helpers, `record_audit_event` and safe citation projection. Keep this in a dedicated service/route rather than expanding the personal TD006 route. No direct database access or raw SQL is allowed.

**Verification:**

```powershell
python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_service.py tests/unit/test_stage07_team_bot_knowledge_api.py tests/unit/test_stage07_draft_employee_hub_api.py tests/unit/test_stage07_assistant_context_api.py
python -m pytest -q tests/integration/test_stage07_team_bot_knowledge_postgres.py -m postgres
```

The PostgreSQL test proves real saved-view selection/permission filtering and 101/100 slicing against local PostgreSQL when it is available. It must not be reported as staging or production evidence. Commit: `feat(stage07): add safe team bot knowledge api`.

## Task 4: Build strict Team Bot Mini App transport and isolated cache state

**Files:**

- Create `mini-app/src/app/team-bot-knowledge-types.ts`.
- Modify `mini-app/src/app/api.ts`.
- Modify `mini-app/src/app/protectedQuery.ts`.
- Create `mini-app/src/test/team-bot-api.test.ts`.
- Create `mini-app/src/test/team-bot-query.test.ts`.

**Interfaces produced:**

```ts
api.listTeamBotContacts(workspaceId, cursor?, init?)
api.listTeamBotKnowledgeContexts(employeeId, init?)
api.getTeamBotKnowledgeContextView(employeeId, viewId, init?)
api.summarizeTeamBot(employeeId, request, idempotencyKey, init?)

teamBotKeys.contacts(userId, workspaceId)
teamBotKeys.contexts(userId, workspaceId, employeeId)
teamBotKeys.selectedView(userId, workspaceId, employeeId, viewId)
clearTeamBotQueries(queryClient, userId, workspaceId?)
```

**RED tests:** parser accepts only exact safe roots, `kind` literal, opaque UUID citations/audit ID, boolean truncation and no extra raw root. It rejects `records`, `fields`, `runtime`, `provider`, `trace`, policy/configuration and unknown intent/action. Cache cleanup for one Workspace/user subtree must not remove a personal-assistant subtree or another Workspace's Team Bot data. Tests initially fail because types/parsers/keys do not exist.

**GREEN implementation:** parse DTOs with the existing strict parser style; keep instruction client length at 600; send only documented snake-case body and an `Idempotency-Key`; key all Team Bot queries under a unique `team-bot` subtree. Run:

```powershell
npm.cmd test -- --run src/test/team-bot-api.test.ts src/test/team-bot-query.test.ts src/test/draft-employee-api.test.ts src/test/assistant-context-api.test.ts
```

Commit: `feat(stage07): add protected team bot transport`.

## Task 5: Deliver a visibly separate Home Team Bot workbench and authoritative command flow

**Files:**

- Create `mini-app/src/app/TeamBotWorkbench.tsx`.
- Modify `mini-app/src/app/WorkspaceHome.tsx`.
- Modify `mini-app/src/app/App.tsx`.
- Modify `mini-app/src/styles.css`.
- Create `mini-app/src/test/team-bot-workbench.test.tsx`.
- Create `mini-app/src/test/team-bot-app-flow.test.tsx`.
- Modify the relevant existing Workspace Home test if one asserts its action set.

**UI behavior:**

1. Home exposes a distinct `鍥㈤槦 Bot` entry beside, but not merged into, `涓汉鍔╃悊`.
2. The workbench says that it summarizes the current team's permitted saved-view knowledge and does not retain personal chat memory.
3. The user chooses only a safe team contact, a safe saved view and optional <=600 character instruction; display the selected view metadata but never record values.
4. On submit, `App` rereads the exact server-side selected context, creates an idempotency key, submits one summary, and renders only safe answer/citation IDs/truncation/audit receipt.
5. It has an explicit `鎵撳紑 Base` handoff. It has no record picker, edit control, draft action, generic prompt input, message history, raw error payload, model/provider/prompt configuration or direct write.
6. A close, Workspace/Base/session switch, selected-contact/view replacement, or 401/403/404 invalidates Team Bot generations and exact Team Bot query keys. Delayed results cannot overwrite the replacement context.

**RED tests:**

- Render the labelled Team Bot workbench with explicit shared-knowledge/no-memory copy and no `draft_update`, record picker or chat history.
- It disables submit without contact/view, bounds instruction at 600, displays truncation/citations/audit receipt, and provides Base handoff.
- App flow asserts the command rereads the selected context before POST, sends no raw records, and an old delayed summary is discarded after Workspace/contact/view change or safe authorization failure.
- `empty_context` displays safe fixed copy and no fake LLM/network provider detail.

**GREEN implementation:** follow the existing accessible workbench/backdrop/mobile sheet grammar, but use a separate Team Bot component, state and query subtree. Reuse the personal assistant only for visual primitives, never for its route/types/state. On successful POST, retain the server receipt; do not locally invent citations or mutate any record state. Use fixed local error copy for malformed/network/5xx failures. Run:

```powershell
npm.cmd test -- --run src/test/team-bot-workbench.test.tsx src/test/team-bot-app-flow.test.tsx src/test/team-bot-api.test.ts src/test/team-bot-query.test.ts src/test/assistant-context-workbench.test.tsx src/test/assistant-context-app-flow.test.tsx
```

Commit: `feat(stage07): add team bot knowledge workbench`.

## Task 6: Reconcile evidence and perform proportional Stage07 acceptance

**Files:**

- Modify TD011, its BDD/SDD/work-surface/complex-index documents, and this plan.
- Modify `project-docs/08-implementation/STAGE_07_SOURCE_OF_TRUTH.md`, `STAGE_07_SUBSTAGE_DELIVERY_ROADMAP.md`, `STAGE_07_PROGRESS.md`, `STAGE_07_REQUIREMENT_TRACEABILITY_AUDIT.md`, `STAGE_07_ACCEPTANCE_CHECKLIST.md`, and (if a line exists) the risk register.
- Add/update a factual evidence note under `project-docs/08-implementation/evidence/`.

**Acceptance sequence:**

1. Run focused backend API/service regressions and record actual counts.
2. Run the local PostgreSQL Team Bot integration test only if the configured local service is available; record actual command/result or the concrete skip reason.
3. Run focused Mini App tests, then full Mini App tests and `npm.cmd run build`; record actual counts/output.
4. Run a scoped `git diff --check` and documentation link/forbidden-marker scan.
5. Reconcile every `TBO-A01` through `TBO-A12` (or the actual BDD IDs) separately. Mark only evidenced claims `implemented-local`; leave browser/manual visual, real OpenRouter, Telegram, staging, production and excluded Stage07 scope open.
6. Do not use browser-control tools. State that manual visual validation needs user/local UI action if it cannot be directly observed without violating the user instruction.

**Final verification commands:**

```powershell
python -m pytest -q tests/unit/test_stage07_team_bot_knowledge_service.py tests/unit/test_stage07_team_bot_knowledge_api.py tests/unit/test_stage07_draft_employee_hub_api.py tests/unit/test_stage07_assistant_context_api.py
python -m pytest -q tests/integration/test_stage07_team_bot_knowledge_postgres.py -m postgres
npm.cmd test -- --run src/test/team-bot-api.test.ts src/test/team-bot-query.test.ts src/test/team-bot-workbench.test.tsx src/test/team-bot-app-flow.test.tsx
npm.cmd test -- --run
npm.cmd run build
git diff --check
```

Commit: `docs(stage07): reconcile team bot knowledge evidence`.

## Plan Self-Review

| Approved TD011 requirement | Task |
| --- | --- |
| Separate Home Team Bot, not a new employee type | 1, 3, 5 |
| Active/member/invoke/summarize contact eligibility | 3 |
| Existing Base/view scope and current permission filters | 3 |
| 101 read / 100 runtime / transparent truncation | 2, 3 |
| One-shot, <=600 instruction, no memory/chat/write | 1, 4, 5 |
| Safe opaque citations and audit receipt | 3, 4, 5 |
| Required idempotency and empty-context no-provider path | 3 |
| Strict DTOs/protected cache/stale-result safety | 1, 4, 5 |
| Local PostgreSQL and full frontend evidence, no browser control | 6 |

No task creates a new employee type, database schema/index, generic knowledge base, chat history, persistent memory, record picker, direct record mutation, Telegram routing, provider configuration, deployment or a general agent/permission framework.


