# Stage09 Conversational Entry and Context Routing

## Status

- Status: approved corrective implementation scope
- Trigger: 2026-07-27 authenticated r58 observation. The user entered `你好` in Ledgerline with no selected Base, view or record, and the UI rendered a raw `analysis_unavailable` degradation view.
- Product clarification: Ledgerline must support a natural, continuous LLM-style conversation. It is not a “select Base first or cannot speak” form. Table context enriches and constrains business answers; it does not block normal conversation.
- Scope: Mini App request routing and result presentation; the existing Stage08 general-advice contract is reused.
- Non-goals: database schema, public API shape, permission model, skill catalog, draft policy, direct write authority or raw internal reasoning.

## Product Behavior

```text
ordinary conversation, no selected Base
  -> client sends mixed in automatic mode
  -> server recognizes only a bounded pure greeting/capability question
  -> effective command intent becomes general_advice
  -> normal LLM conversational answer
  -> no business fact claim, citation, draft or write
  -> timeline renders a natural answer, never analysis_unavailable

business question with authorized Base/view/record
  -> client keeps auto/explicit table skill routing
  -> Stage08 retrieves permission-filtered context
  -> answer carries citations, or safely reports unavailable evidence

draft request with selected writable record and draft-capable skill
  -> existing draft-confirmation path unchanged
```

The critical distinction is **answer authority**, not whether the user may start a conversation. A normal chat answer can help the user formulate a task, explain available skills or suggest what to inspect; it cannot invent customer status, hidden fields, table results or completed writes. A business fact still requires authorized evidence.

## Architecture

### 1. Server-side bounded conversational routing

The workbench already has four Stage08 intents: `business_fact`, `memory_lookup`, `mixed` and `general_advice`. Automatic mode always submits `mixed`; the backend is the single routing authority. Before skill resolution and command creation, the backend may normalize `mixed` to `general_advice` only when all of the following are true:

- no explicit `skill_id` was selected;
- `requested_action=read_only`;
- the normalized full query matches a small allowlist of pure greetings or capability questions such as `你好`、`您好`、`hello`、`你能做什么`；
- the full query contains no additional text. Therefore `你好，明日璀璨现在什么阶段` does not match and remains `mixed`.

The helper is deterministic, Unicode-aware and full-string matched. It does not use an LLM, keyword scores or table contents and cannot widen authority. The effective request is then used consistently by skill resolution, idempotency fingerprinting, initial command creation and distributed-worker resume so that synchronous Stage08 and Stage10 produce the same route.

Explicit skills always win. A user who selects `查表问答`, `汇总分析` or a draft skill keeps its declared intent/action. A draft still requires its existing record/write checks.

### 2. Provider contract

The existing Stage08 `general_advice` branch is purpose-built for this route:

- retrieval is skipped;
- citations are required to be empty;
- action is only `general_advice` or `deny`;
- no draft can be attached;
- no business data is supplied to the Provider.

The r58 Chinese language guard remains in force. A Chinese conversational request receives an explicit Simplified Chinese instruction; a provider language refusal is replaced only with safe Chinese conversational guidance.

### 3. Presentation contract

`analysis_unavailable` is meaningful for a failed evidence-backed analysis, but it is not a valid visible response to ordinary conversation. The UI preserves the familiar chat experience: user prompt → short natural answer. It may retain small, non-intrusive provenance text such as `通用对话 · 不读取业务数据`; it must not expose internal degradation codes as the answer.

## Implementation Steps

1. Keep the composer’s automatic route at `mixed` regardless of whether a Base/record is currently open; preserve the user’s exact query.
2. Add a backend pure-conversation normalizer and use its effective request before skill resolution, fingerprinting and command creation in both prepare and resume paths.
3. Preserve explicit skill/draft rules and prove that a greeting followed by any business text remains `mixed`.
4. Make the empty workbench describe conversational capability and table-aware boundaries rather than instructing the user to choose an object before speaking.
5. Add component tests for `你好` without scope: exactly one stream call, `intent=general_advice`, `skillId=null`, and a rendered Chinese conversational answer. Add regression tests that a Base-scoped query remains `mixed` and an explicit table skill remains authoritative.
6. Run focused frontend/backend tests, production build and deployment candidate gates. Then deploy one matching source/venv/static candidate and capture a redacted authenticated browser conversation.

## Acceptance Criteria

- An automatic `你好` produces one ordinary conversation turn, never `analysis_unavailable`.
- `你好，明日璀璨客户现在是什么阶段？` remains evidence-backed `mixed` retrieval and is never downgraded to general advice.
- The conversational answer contains no business assertion, citation, draft or write claim.
- Selecting a Base enriches factual tasks through the existing authorized retrieval path.
- Explicit skills and draft confirmation remain stronger than automatic conversational routing.
- Chinese provider refusal cannot surface as English or an internal failure card for `general_advice`.

## Current Progress

- 2026-07-27: added the pure client routing helper and a RED-to-GREEN workbench regression for an unscoped `你好`. The stream payload is now `intent=general_advice`, `requested_action=read_only`, no skill and no target record; its rendered answer is conversational rather than an `analysis_unavailable` card.
- 2026-07-27: updated the two app-level contextless-flow fixtures to enforce the same contract: no mock business citation is permitted when no Base or record is selected. Base-scoped auto-routing and explicit-skill precedence retain their separate regressions.
- 2026-07-27: refreshed the Chinese provider-refusal fallback to a normal greeting that invites a direct question and explains that a Base adds authorized data context. It remains citation-free and cannot create a draft.
- 2026-07-28: authenticated r65 UI acceptance proved that the former client-wide contextless downgrade caused business queries to skip retrieval; changing all automatic requests to `mixed` repaired business retrieval but exposed `你好` as `analysis_unavailable`. The routing owner is therefore moved to the backend with the bounded full-query rule above. This supersedes the 2026-07-27 client-side classification wording.
- Verification: frontend focused flow/workbench suite `27 passed, 2 skipped`; full Mini App suite `77 files passed, 403 passed, 2 skipped`; provider and evaluator unit suites `82 passed`; production build passed. Matching source/venv/static release `stage09-p1-20260727-r59-conversational-entry-routing` passed sealed candidate gates and bounded readiness before activation; API/worker/outbox/Redis/Nginx are active and public health is HTTP `200`. An authenticated live browser replay of `你好` remains pending evidence.
