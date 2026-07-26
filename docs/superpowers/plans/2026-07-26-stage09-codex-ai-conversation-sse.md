# Stage09 Codex-style AI Conversation SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Codex-style continuous AI conversation workbench backed by a permission-safe `POST /api/stage08/assistant/query-stream` SSE compatibility path.

**Architecture:** Extract the existing synchronous assistant route into one shared application execution boundary so sync and stream preserve identical authorization, scope, idempotency, replay, audit and draft behavior. Stream only allowlisted lifecycle events and chunks derived from the final validated `AssistantQuerySafeView`. The Mini App consumes the POST response with `fetch()` and a strict incremental SSE parser, then renders a reducer-driven timeline and fixed Composer.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2.x, React, TypeScript, Vite, Vitest, Testing Library, Nginx.

## Global Constraints

- Preserve `POST /api/stage08/assistant/query` as the compatibility route.
- Do not add a migration, persistent chat-history store, permission rule, external send, raw model-token stream or hidden-reasoning projection.
- Reuse `authorize_workspace_action`, `_require_current_query_scope`, existing `_OPERATION`, `run_stage08_collaboration`, `validate_assistant_query_safe_view`, audit and idempotency replay.
- Only the final validated answer may produce `answer_delta` events.
- `request_id` is server-generated and distinct from `idempotency_key`.
- A client abort means “stopped viewing”; it does not claim server cancellation.
- A `draft_update` request is never automatically resubmitted with a new idempotency key.
- Use TDD for every behavior change and keep the old worktree’s dirty files untouched.
- Do not deploy or perform a real write in this implementation pass.
- From the user instruction issued during Task 2 onward, do not create per-task commits. Keep reviewed work in the isolated worktree until all Stage09 tasks, acceptance commands, documentation audit, code review and cleanup pass.
- The local checkpoint commits created before that instruction are not pushed. At final closeout, squash the complete Stage09 branch delta from the approved `b57b152` base into one final commit. Do not rewrite the branch earlier because the checkpoints remain useful recovery points while implementation is incomplete.

---

### Task 1: Restore the Stage08 API test baseline

**Files:**
- Modify: `backend/tests/api/test_stage08_collaboration_api.py`

**Interfaces:**
- Consumes: `run_stage08_collaboration(uow, command, actor, *, deps, now, runtime_control)`.
- Produces: a route test double that accepts the current production signature and still asserts the server-derived command and actor.

- [ ] **Step 1: Re-run the failing baseline test**

Run:

```powershell
python -m pytest -q backend/tests/api/test_stage08_collaboration_api.py::test_assistant_query_derives_command_server_side_and_returns_only_safe_view
```

Expected: `1 failed`; HTTP response is `500` because the test double rejects `deps` and `runtime_control`.

- [ ] **Step 2: Update only the stale test double**

```python
def run(uow, command, actor, *, deps, now, runtime_control):
    del uow, deps, now, runtime_control
    captured["command"] = _command_snapshot(command)
    captured["actor"] = actor
    return AssistantQuerySafeView(
        status="completed",
        answer="执行已分析",
        citations=(AssistantQuerySafeCitation(ordinal=1, label="general_advice"),),
        degradation_codes=(),
        draft_id=None,
    )
```

- [ ] **Step 3: Verify the focused API baseline**

Run:

```powershell
python -m pytest -q backend/tests/api/test_stage08_collaboration_api.py
```

Expected: every test in the module passes.

- [x] **Step 4: Record the historical baseline checkpoint**

This checkpoint was committed before the single-commit instruction and will be included in the final Stage09 squash. Do not create a new commit here.

### Task 2: Add strict SSE event contracts and shared execution

**Files:**
- Modify: `backend/app/schemas/stage08_collaboration.py`
- Modify: `backend/app/api/routes/stage08_collaboration.py`
- Modify: `backend/tests/api/test_stage08_collaboration_api.py`
- Modify: `backend/tests/unit/test_stage08_collaboration_contracts.py`

**Interfaces:**
- Consumes: existing `AssistantQueryRequest`, `AssistantQuerySafeView` and route dependencies.
- Produces:
  - `AssistantStreamPhase`
  - `AssistantStreamEvent`
  - `prepare_assistant_query(request, identity, uow) -> PreparedAssistantQuery`
  - `complete_assistant_query(prepared, uow) -> AssistantQuerySafeView`
  - `execute_assistant_query(request, identity, uow) -> AssistantQuerySafeView`
  - `iter_assistant_stream_events(safe_view, request_id) -> Iterator[AssistantStreamEvent]`
  - `POST /api/stage08/assistant/query-stream`

- [ ] **Step 1: Write failing contract tests**

Add literal assertions that reject extra fields, invalid phases, blank delta text and non-positive sequence numbers:

```python
def test_stream_event_contract_rejects_unknown_or_unbounded_payload() -> None:
    with pytest.raises(ValidationError):
        AssistantStreamEvent(
            event="answer_delta",
            sequence=1,
            request_id="req-1",
            text="",
            raw_provider="forbidden",
        )
```

- [ ] **Step 2: Run the contract RED**

Run:

```powershell
python -m pytest -q backend/tests/unit/test_stage08_collaboration_contracts.py -k stream
```

Expected: collection/import failure because the stream contract does not exist.

- [ ] **Step 3: Implement the strict Pydantic event contract**

Use a discriminated union with `extra="forbid"` and bounded strings:

```python
AssistantStreamPhase = Literal[
    "authorizing",
    "planning_context",
    "analysing",
    "creating_draft",
    "completed",
]

class AssistantStreamAnswerDelta(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event: Literal["answer_delta"]
    sequence: StrictInt = Field(ge=1)
    request_id: StrictStr = Field(min_length=1, max_length=64)
    text: StrictStr = Field(min_length=1, max_length=512)
```

Define equally strict `status`, `result`, `error` and `done` models, then expose `AssistantStreamEvent` as their discriminated union.

- [ ] **Step 4: Write failing route tests**

Cover:

```python
def test_assistant_query_stream_emits_monotonic_safe_events(client) -> None:
    response = client.post(STREAM_PATH, json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_test_sse(response.text)
    assert [event["event"] for event in events] == [
        "status", "status", "status", "answer_delta", "result", "status", "done"
    ]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert "".join(
        event["text"] for event in events if event["event"] == "answer_delta"
    ) == events[-3]["safe_view"]["answer"]
```

Also assert:

- same idempotency key replays one safe result and does not create a second draft;
- denied scope becomes a redacted terminal SSE `error` after the stream has emitted `authorizing`;
- provider/internal text never appears in the body;
- synchronous `/query` still returns the same `SafeView`.

- [ ] **Step 5: Run the route RED**

Run:

```powershell
python -m pytest -q backend/tests/api/test_stage08_collaboration_api.py -k "stream or derives_command or replay"
```

Expected: stream route tests fail with `404`.

- [ ] **Step 6: Extract shared prepare and complete functions**

Split the body of `query_assistant` into:

```python
def prepare_assistant_query(
    request: AssistantQueryRequest,
    identity: Stage06RequestIdentity,
    uow: Stage06PlatformUnitOfWork,
) -> PreparedAssistantQuery:
    ...

def complete_assistant_query(
    prepared: PreparedAssistantQuery,
    uow: Stage06PlatformUnitOfWork,
) -> AssistantQuerySafeView:
    ...

def execute_assistant_query(request, identity, uow):
    return complete_assistant_query(
        prepare_assistant_query(request, identity, uow),
        uow,
    )
```

Keep `_OPERATION = "stage08.assistant.query"` for both routes. `query_assistant` becomes a thin call to the shared function.

- [ ] **Step 7: Implement safe event generation and the stream route**

```python
@router.post("/query-stream")
def query_assistant_stream(...):
    request_id = uuid4().hex
    return StreamingResponse(
        encode_sse_events(
            iter_assistant_stream_events(request, identity, uow, request_id)
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
)
```

The generator emits only states that the current service boundaries can prove:

- fresh request: `authorizing`, then `prepare_assistant_query`, then `analysing` immediately before `complete_assistant_query` enters the controlled runtime;
- replay: `authorizing`, then the validated replay result, with no `analysing` because the runtime is not called;
- do not emit `planning_context`, `retrieving_knowledge`, or `creating_draft` in the first release because the monolithic runtime exposes no independent callback for those phases; the final `safe_view` is the only truth for draft/degraded/denied outcomes.

After `prepare_assistant_query` succeeds, the generator owns any incomplete idempotency reservation until `complete_assistant_query` commits it. Wrap all yields in `try/finally`: on close or `GeneratorExit` before completion, roll back the SQLAlchemy session and discard an InMemory reservation. Do not translate `GeneratorExit` into a synthetic SSE `error`, and do not clean up an already committed/replayed result.

Split answer text on paragraph/sentence boundaries into chunks of at most 512 characters. Serialize each event as UTF-8 JSON with `ensure_ascii=False`; never serialize the request, command, provider response or exception.

- [ ] **Step 8: Verify backend GREEN**

Run:

```powershell
python -m pytest -q backend/tests/unit/test_stage08_collaboration_contracts.py backend/tests/api/test_stage08_collaboration_api.py
```

Expected: all selected tests pass.

Independent review correction before Task 2 can be accepted:

- add a RED/GREEN test that directly closes the generator after `prepare` and proves no InMemory `in_progress` reservation remains; assert SQLAlchemy rollback is invoked on the equivalent unfinished path;
- add a RED/GREEN test proving a `draft_update` request that ends degraded or without a draft never emits `creating_draft`;
- assert the fresh and replay phase sequences match the truthful subset above.

- [x] **Step 9: Record the reviewed backend checkpoint**

The initial backend checkpoint and its review fix were committed before the single-commit instruction. They remain local recovery points and will be included in the final Stage09 squash. Do not create another Task 2 commit.

### Task 3: Add the incremental frontend SSE client

**Files:**
- Create: `mini-app/src/app/stage08-collaboration-stream.ts`
- Create: `mini-app/src/test/stage08-collaboration-stream.test.ts`
- Modify: `mini-app/src/app/stage08-collaboration-types.ts`
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/test/stage08-collaboration-api.test.ts`

**Interfaces:**
- Consumes: `Stage08AssistantQuery`, `Stage08AssistantSafeView`, existing request identity headers and `Idempotency-Key`.
- Produces:

```typescript
export type Stage08AssistantStreamEvent =
  | { event: 'status'; sequence: number; requestId: string; phase: Stage08AssistantStreamPhase }
  | { event: 'answer_delta'; sequence: number; requestId: string; text: string }
  | { event: 'result'; sequence: number; requestId: string; safeView: Stage08AssistantSafeView }
  | { event: 'error'; sequence: number; requestId: string; code: string; message: string }
  | { event: 'done'; sequence: number; requestId: string }

export async function queryStage08AssistantStream(
  request: Stage08AssistantQuery,
  idempotencyKey: string,
  onEvent: (event: Stage08AssistantStreamEvent) => void,
  init?: RequestInit,
): Promise<Stage08AssistantSafeView>
```

- [ ] **Step 1: Write parser RED tests**

Use a real `ReadableStream<Uint8Array>` fixture split inside UTF-8 characters and SSE field boundaries. Assert:

- CRLF and LF both parse;
- multi-line `data:` joins with `\n`;
- the fixture matches the real backend and contains only `data: {"event":...}` blocks, with no synthetic SSE `event:` field;
- payload JSON `event` is the authoritative discriminant; an optional SSE `event:` field must match it;
- unknown payload event names are ignored without being published;
- duplicate/gapped/decreasing sequence fails closed;
- duplicate `result`, `done` without `result`, and any event/data/byte after a terminal event reject;
- terminal `done` or `error` is not passed to `onEvent` until EOF and terminal invariants have been validated;
- all delta text concatenates exactly to `result.safe_view.answer`;
- the returned result is the unique final `safe_view`, not an unvalidated delta buffer.

- [ ] **Step 2: Run parser RED**

Run:

```powershell
npm.cmd test -- --run src/test/stage08-collaboration-stream.test.ts --maxWorkers=1
```

Expected: import failure because the stream module does not exist.

- [ ] **Step 3: Implement the strict parser**

Use:

```typescript
const decoder = new TextDecoder('utf-8', { fatal: true })
let buffer = ''
buffer += decoder.decode(chunk, { stream: true })
```

Parse complete blank-line-delimited event blocks from the real backend’s data-only SSE format and discriminate on the JSON payload `event`. If an SSE `event:` field is present, require it to match the JSON field. Validate every known event through explicit guards, enforce exact next sequence and stable request id, cap one event block at 64 KiB and cap the full response at 1 MiB. Maintain one result plus a delta buffer; require the delta concatenation to equal the final safe answer. Continue reading through terminal `done`/`error` until EOF so trailing data cannot be silently ignored, and publish the terminal callback only after terminal invariants pass. Unknown event names are discarded without rendering their data.

- [ ] **Step 4: Write API RED**

Assert `fetch` receives:

```typescript
expect(fetchMock).toHaveBeenCalledWith(
  '/api/stage08/assistant/query-stream',
  expect.objectContaining({
    method: 'POST',
    headers: expect.objectContaining({
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      'Idempotency-Key': 'idem-1',
    }),
  }),
)
```

Also assert that a caller-provided `X-Telegram-Init-Data` survives request construction, reject a non-SSE content type, and ensure `AbortError` becomes the stable stopped-viewing outcome rather than a raw message.

- [ ] **Step 5: Implement the fetch stream API**

Reuse the same input normalization as `queryStage08Assistant`. Pass `credentials` and merge existing identity headers exactly as the current API wrapper does; do not delete caller-provided Telegram or tracing headers. Do not use `EventSource`.

Independent Task 3 review correction before acceptance:

- replace any test helper that emits a synthetic SSE `event:` line with the exact backend data-only wire format and prove one backend-shaped stream succeeds;
- add RED/GREEN coverage that the Telegram identity header survives request construction;
- add RED/GREEN coverage for delta/result mismatch, duplicate result, terminal callback ordering, and trailing event/bytes after `done`;
- re-run the combined parser/API suite and TypeScript build before re-review.

- [ ] **Step 6: Verify frontend stream GREEN**

Run:

```powershell
npm.cmd test -- --run src/test/stage08-collaboration-stream.test.ts src/test/stage08-collaboration-api.test.ts --maxWorkers=1
```

Expected: all selected tests pass.

- [ ] **Step 7: Record the reviewed frontend stream-client checkpoint without committing**

Record exact RED/GREEN evidence in the ignored SDD report and update `Current Progress`. Do not create a Git commit.

### Task 3.5: Bind workbench skills to the backend LLM runtime

**Gate:** Do not implement this task until the user explicitly confirms `project-docs/08-implementation/STAGE_09_LLM_SKILL_LAUNCHER_DESIGN.md`.

**Goal:** Replace prompt-only frontend tags with a server-curated skill catalog and a versioned runtime profile that affects context eligibility, OpenRouter prompting/action validation, replay and audit.

**Files (planned):**

- Modify `backend/app/schemas/stage08_collaboration.py`
- Modify `backend/app/api/routes/stage08_collaboration.py`
- Modify `backend/app/runtime/stage08_collaboration_contracts.py`
- Modify `backend/app/services/stage08_collaboration.py`
- Modify `backend/app/services/stage08_openrouter_analysis_provider.py`
- Reuse `backend/app/agents/stage06_skills.py`
- Reuse or narrowly extend `backend/app/agents/stage06_skill_matching.py`
- Add focused backend API/runtime/provider/audit tests
- Modify `mini-app/src/app/stage08-collaboration-types.ts`
- Modify `mini-app/src/app/api.ts`
- Modify `mini-app/src/app/CollaborationWorkbench.tsx`
- Add focused frontend catalog/selection/scope-reset tests

**TDD order:**

1. RED: curated catalog, internal/inactive rejection, employee/member/resource/chat/write intersections.
2. RED: explicit/auto skill request compatibility, fingerprint separation and sync/SSE/replay safe summary parity.
3. GREEN: server-only `ResolvedAssistantSkillProfile` factory and catalog endpoint.
4. GREEN: command/provider/action-validation/audit integration without a database migration.
5. RED/GREEN: frontend server catalog, explicit/auto selection, disabled reasons, scope reset and result-skill verification.
6. Re-run Stage06 skill matcher, Stage08 collaboration API/service/provider, frontend stream/API/workbench and full suites.

The exact public skills and constraints come from the design document; do not restore the six static legacy tags as a fallback.

### Task 4: Rebuild the collaboration workbench as a continuous timeline

**Files:**
- Create: `mini-app/src/assets/ledger-paper-texture.png`
- Modify: `mini-app/src/app/CollaborationWorkbench.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/styles.css`
- Modify: `mini-app/src/test/collaboration-workbench.test.tsx`
- Modify: `mini-app/src/test/assistant-context-app-flow.test.tsx`

**Interfaces:**
- Consumes: `queryStage08AssistantStream`, current employee contacts, record context and draft opener.
- Visual truth: `project-docs/08-implementation/assets/stage09/ledgerline-workbench-selected.png`.
- Produces: one Ledgerline context strip, timeline index rail, reducer-driven continuous transcript, safe scope aside, server-catalog-driven skill launchers, one fixed Composer and safe stop/retry behavior.
- Visual constraints: warm ledger paper, graphite text, one blue action accent, pending amber only for unconfirmed drafts, raster ledger texture, thin line icons already used by the project, no gradients/glass/glow/chat bubbles/card nesting.

- [ ] **Step 1: Produce and inspect the Ledgerline texture asset**

Generate one `512 x 512` low-contrast, seamless warm paper texture with fine ruled lines, sparse coordinate ticks and subtle fibers. Save it as `mini-app/src/assets/ledger-paper-texture.png`; inspect it directly before use. It must contain no text, logo, icon, gradient glow or decorative illustration, and it must remain readable behind normal 14–16px text at `6%–10%` visual strength.

- [ ] **Step 2: Write workbench RED tests**

Add tests that assert:

```tsx
expect(screen.getByRole('textbox', { name: '协作问题' })).toBeVisible()
fireEvent.keyDown(textbox, { key: 'Enter', shiftKey: false })
expect(onInvokeStream).toHaveBeenCalledTimes(1)
fireEvent.keyDown(textbox, { key: 'Enter', shiftKey: true })
expect(onInvokeStream).toHaveBeenCalledTimes(1)
```

After Task 3.5 is confirmed and implemented, cover `auto` plus every catalog skill, explicit `skill_id` submission, disabled reasons, scope-change reset and result skill verification. Assert no `draft_update` action is offered when the server catalog lacks explicit write proof. Assert status events, deltas, final citations and draft entry append in order. Assert abort copy says“已停止查看结果” and never says the server task was cancelled.

Also cover the selected visual structure without testing pixel values:

- one `ContextStrip`, one timeline and one Composer exist; no legacy three-column form headings remain;
- transcript entries expose sequence/time semantics and `aria-live="polite"`;
- a pending draft includes the literal safety copy `待确认 · 未写入`;
- safe scope aside is available by an accessible toggle at narrow layout semantics;
- Composer remains after long timeline content and every server-enabled skill is keyboard reachable;
- error/stopped states stay inline and do not use `alert()`.

- [ ] **Step 3: Run workbench RED**

Run:

```powershell
npm.cmd test -- --run src/test/collaboration-workbench.test.tsx src/test/assistant-context-app-flow.test.tsx --maxWorkers=1
```

Expected: tests fail because the current component is still a three-column form and has no stream callback or skill tags.

- [ ] **Step 4: Implement a request-scoped reducer**

Represent each timeline turn as:

```typescript
type ConversationTurn = {
  requestId: string
  question: string
  phase: Stage08AssistantStreamPhase | null
  answer: string
  result: Stage08AssistantSafeView | null
  state: 'running' | 'completed' | 'stopped' | 'failed'
}
```

Only `result` may mark completion or expose citations/draft. Keep history in component state only.

Review correction: split safe-result visibility from terminal completion. `result` stores the validated `safe_view` and moves the turn to `finalizing`; only the successful stream Promise resolution after parser-validated `done + physical EOF` dispatches `complete`. A failure after `result` must still move the turn to `failed`. Lock each turn to the first server request id and strict sequence as a UI defense in depth.

- [ ] **Step 5: Implement the selected Ledgerline layout**

Build:

- a single-row safe `ContextStrip` for workspace/Base/view/record/employee, returning to existing selectors rather than duplicating them;
- a `TimelineIndexRail` with sequence, tabular time, blue locator point and a continuous rule;
- a transcript with typographic user/status/answer entries instead of chat bubbles;
- compact `EvidenceRows` using table grammar and one `DraftSheet` with a pending-colored left rule and `待确认 · 未写入`;
- a fixed/sticky `ComposerDock` with Enter/Shift+Enter and a horizontal rectangular `SkillStrip`;
- a desktop `SafeScopeAside` that becomes an accessible, non-blocking drawer on narrow screens;
- an explicit stop-viewing control wired to `AbortController`.

Use the generated raster texture once on the ledger canvas at low strength. Do not recreate it with CSS gradients, inline SVG, div art or repeated borders on every component. Reuse the project’s installed icon set and existing identity/context selectors; do not add an icon or font dependency.

Responsive implementation:

```text
>=1180px  104px index rail + fluid transcript + 248px safe aside
768–1179px compact index rail + fluid transcript; safe aside becomes drawer
<768px    100dvh single-column workbench; horizontal context and skills;
           evidence scrolls internally; Composer reserves safe-area bottom
```

Preserve the existing employee and record selection behavior. Do not add decorative fake tool logs, hidden reasoning, fake percentages, unapproved capability names or metrics.

Independent Task 4 review correction before acceptance:

- replace record-id-derived draft availability with explicit current-record write capability plus employee/current-Base scope proof; default false when the existing frontend context cannot prove either fact;
- remove the desktop `520px` collaboration side-panel entry and use the selected wide Ledgerline dialog, with the same component becoming full-screen at compact breakpoints;
- add initial Composer focus, focus trap/background isolation, Escape close and trigger focus restore tests;
- add RED/GREEN coverage for `result` followed by missing/invalid `done`, reducer request-id/sequence mismatch, and near-bottom-only auto-follow;
- re-run the five Task 4 test files and production build before re-review.

- [ ] **Step 6: Verify workbench GREEN and build**

Run:

```powershell
npm.cmd test -- --run src/test/collaboration-workbench.test.tsx src/test/assistant-context-app-flow.test.tsx src/test/stage08-collaboration-stream.test.ts src/test/stage08-collaboration-api.test.ts --maxWorkers=1
npm.cmd run build
```

Expected: all selected tests pass and Vite production build exits `0`.

- [ ] **Step 7: Capture and compare the selected visual**

Run the existing Mini App locally and use the in-app browser at `1440 x 1024`. Capture the same populated workbench state as the selected reference, then create a side-by-side comparison of the selected mock and implementation. Run Product Design `design-qa`; fix every P0/P1/P2 issue and repeat until project-root `design-qa.md` says `final result: passed`. Also inspect one compact Telegram-width state and the primary send/skill/stop/draft interactions.

- [ ] **Step 8: Record the reviewed workbench checkpoint without committing**

Record interaction, responsive-layout and reducer evidence in the ignored SDD report and update `Current Progress`. Do not create a Git commit.

### Task 5: Configure Nginx SSE transport and close documentation

**Files:**
- Modify: `deploy/stage09-native/nginx/stage09-p1.conf.template`
- Modify: `deploy/stage09-native/nginx/stage09-p1-public-https.conf.template`
- Modify: `deploy/stage09-native/scripts/test-native-service-assets.sh`
- Modify: `deploy/stage09-native/scripts/test-public-ingress-assets.sh`
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`
- Modify: `project-docs/00-governance/HANDOFF_2026-07-26_CODEX_STYLE_AI_CONVERSATION.md`
- Modify: `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_DESIGN.md`
- Modify: `project-docs/08-implementation/STAGE_09_CODEX_STYLE_AI_CONVERSATION_IMPLEMENTATION_PLAN.md`
- Create: `project-docs/08-implementation/evidence/stage09-codex-ai-conversation-sse-2026-07-26.md`

**Interfaces:**
- Consumes: internal/public Nginx render scripts and the new exact stream route.
- Produces: non-buffered proxy behavior and a machine-locatable evidence record.

- [x] **Step 1: Write failing rendered-config tests**

Render both templates, then assert the exact stream location has:

```text
proxy_http_version 1.1
proxy_buffering off
proxy_cache off
proxy_read_timeout 90s
X-Accel-Buffering no
```

The tests must execute the render scripts and inspect their output, not just grep the template source.

- [x] **Step 2: Run Nginx asset RED**

Run with Git Bash:

```powershell
& 'C:\Program Files\Git\bin\sh.exe' deploy/stage09-native/scripts/test-native-service-assets.sh
& 'C:\Program Files\Git\bin\sh.exe' deploy/stage09-native/scripts/test-public-ingress-assets.sh
```

Expected: the new SSE assertions fail.

- [x] **Step 3: Add the exact SSE proxy location**

Reuse each template’s current upstream, proxy headers and identity forwarding. Add only the buffering/cache/read-timeout directives needed for `/api/stage08/assistant/query-stream`.

- [x] **Step 4: Verify Nginx asset GREEN**

Run the two commands from Step 2 again.

Expected: both scripts exit `0`.

- [ ] **Step 5: Run final verification**

Run:

```powershell
python -m pytest -q backend/tests/unit/test_stage08_collaboration_contracts.py backend/tests/unit/test_stage08_collaboration_graph.py backend/tests/unit/test_stage08_collaboration_service.py backend/tests/api/test_stage08_collaboration_api.py
npm.cmd run test:run
npm.cmd run build
git diff --check
git status --short --branch
```

Expected: backend selection passes, all Mini App tests pass, build exits `0`, diff check exits `0`, and status lists only intended files.

- [x] **Step 6: Record exact evidence and remaining limits**

The evidence document must list commands, pass/fail/skip counts, worktree/branch/commit, no-write boundary, skipped browser/deployment operations and the existing `npm audit` dependency warning. Update every `Current Progress` field without claiming deployment or product-level browser acceptance.

- [x] **Step 7: Finish transport and closeout documents without committing**

Leave all implementation and documentation changes in the isolated worktree. Do not commit until the whole-stage review below is complete.

---

### Task 6: Whole-stage acceptance, audit, cleanup and single final commit

**Scope:**
- Review the complete branch delta from `b57b152`, not only the most recent task.
- Re-run backend selection, the full Mini App test suite, production build, deployment-asset tests and `git diff --check`.
- Audit source-of-truth links, `Current Progress`, evidence claims, generated artifacts, untracked files and worktree boundaries.
- Perform one independent whole-branch code review; fix every Critical/Important finding and re-run the affected plus full acceptance commands.
- Confirm no real external write, deployment, schema change or permission expansion occurred.

- [ ] **Step 1: Run final acceptance commands**

Record exact commands, versions, pass/fail/skip counts and elapsed time in the Stage09 acceptance evidence. A command that was not executed must be listed under `Skipped Tests`; it cannot be implied by a nearby test.

- [ ] **Step 2: Audit documentation and repository hygiene**

Verify:

```text
active source-of-truth links resolve
Current Progress matches Git and test evidence
.superpowers remains ignored and untracked
no temporary screenshots/scripts/build output entered Git unintentionally
old dirty worktree remains untouched
only intended Stage09 source/docs/deploy files differ from b57b152
```

- [ ] **Step 3: Run independent whole-branch code review**

The reviewer must inspect architecture compliance, security/redaction, transaction/idempotency, frontend parser/state behavior, accessibility/responsiveness, Nginx transport and test quality. HOLD on any Critical or Important finding.

- [ ] **Step 4: Fix findings and repeat acceptance**

Keep fixes uncommitted. Update the design/implementation/evidence documents before or with the corresponding code change, and repeat the affected tests plus the complete final acceptance set.

- [ ] **Step 5: Squash local checkpoints and create one final commit**

Only after Steps 1–4 pass:

```powershell
git reset --soft b57b152
git status --short
git diff --cached --check
git commit -m "feat(stage09): add safe AI conversation workbench"
```

Before the reset, verify the exact base with `git merge-base` and confirm the branch has not been pushed. After the commit, re-run `git status --short --branch` and inspect `git show --stat --oneline HEAD`. Do not push, merge or deploy without separate authorization.
