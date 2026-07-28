# Stage09 中文回答语言护栏

## Status

- Status: activated on the native server; authorized-browser replay remains pending
- Trigger: 2026-07-27 authenticated r57 browser acceptance. A Chinese greeting (`你好`) reached the real Stage08 OpenRouter analysis path but the rendered answer was `I cannot answer questions in Chinese. Please use English.`
- Scope: Stage08 OpenRouter response language instruction, output validation and safe general-advice fallback.
- Non-goals: changing user identity, authorization, evidence selection, citation policy, skill selection, draft permissions, model/provider choice, database schema, API shape or frontend rendering.

## Problem

The Stage08 provider system prompt is English-only and does not carry an explicit response-language contract. Its strict JSON schema accepts any non-empty string in `answer`, so an English language-refusal is structurally valid and reaches the safe view as a completed answer. The browser can therefore correctly render the Ledgerline interaction while showing a product-invalid answer.

This is not a frontend translation problem. Rewriting text in React would conceal the provider's language failure, break citations/identifiers and leave Telegram/API consumers inconsistent. The contract must be enforced before a provider answer becomes an `AnalysisDecision`.

## Language Contract

```text
Chinese query (contains Han code points)
  -> explicit Simplified-Chinese system instruction
  -> provider answer must contain Chinese prose
  -> identifiers, field keys and stored scalar values may remain canonical
  -> known Chinese/English language-refusal wording is rejected

Other query
  -> existing provider behavior unchanged

Chinese general-advice + explicit language-contract rejection
  -> fixed Chinese, non-factual guidance
  -> action=general_advice, citations=[], draft=null

Chinese evidence-bound/draft request + rejected provider answer
  -> existing unavailable/degraded path
  -> never translate, invent a fact, create a draft or relax citation policy
```

The fallback is intentionally limited to `general_advice`. It uses an ordinary conversational Chinese greeting, invites a direct question, and explains that opening an authorized Base enables data-aware analysis. It does not claim any business fact, citation, update, draft or completed action. A business-fact or draft request must remain fail-closed if a valid Chinese provider answer cannot be obtained.

## Implementation Design

### 1. Derive a private response-language requirement

`stage08_openrouter_analysis_provider.py` derives `zh-Hans` only when the command query contains at least one Han code point. This value is local execution metadata: it is neither persisted in audit payloads nor exposed through the public API.

### 2. Bind the requirement to the provider prompt

Keep the existing evidence/action/JSON constraints. Add an explicit system instruction for `zh-Hans`:

```text
Answer in Simplified Chinese. Do not refuse because the user wrote Chinese.
Keep exact record identifiers, field keys and stored values unchanged where needed.
```

The instruction does not ask the model to translate evidence or emit internal reasoning.

### 3. Validate before accepting `AnalysisDecision`

Extend the existing semantic validation call with the local language requirement. A Chinese query rejects an answer that lacks Han text or matches a known English/Chinese language-refusal pattern. Existing checks for action compatibility, citations, draft shape, write-completion claims and allowed skill actions remain first-class and unchanged.

### 4. Safe general-advice fallback

After the bounded provider attempts are exhausted, construct a fixed Chinese `general_advice` decision only when the command itself is Chinese, its intent is `general_advice`, and at least one response was rejected specifically by the language contract. Citation, action, draft or JSON-shape failures never take this fallback; they keep the current unavailable result. The fallback result uses no citations and cannot carry a draft.

## Test Plan

1. Add a RED provider unit test with a Chinese `general_advice` command and a mock OpenRouter response containing the observed English refusal. It must fail under the old implementation because the English answer is accepted.
2. Assert the outbound system instruction contains the Chinese requirement without exposing private evidence in the test assertion.
3. After implementation, assert the terminal decision is the fixed Chinese general-advice answer with empty citations and no draft.
4. Assert a Chinese evidence-bound query receiving the same invalid answer remains unavailable rather than receiving fabricated Chinese facts.
5. Run the focused provider tests, Stage08 collaboration contract/service tests, full backend unit suite and the existing real-provider evaluator in its safe evaluation mode. The last step must record provider behavior without raw prompts, answers, credentials or customer data.

## Acceptance Criteria

- The exact r57 failure wording cannot be rendered as a completed answer for a Chinese query.
- Chinese greetings receive a Chinese safe response even if the provider refuses the language.
- Non-general-advice Chinese requests never receive a fabricated translation or unsupported draft.
- Existing English response behavior and all permission/citation/draft controls remain covered by regression tests.
- A real authorized browser check repeats `你好` and records only a redacted screenshot and aggregate result.

## Current Progress

- 2026-07-27: implemented the private `zh-Hans` response requirement, provider system instruction, refusal-pattern rejection and narrowly scoped general-advice fallback in `stage08_openrouter_analysis_provider.py`.
- 2026-07-27: added regression coverage for the observed refusal and the evidence-bound fail-closed case; updated existing isolated evaluator fixtures so their Chinese queries return Chinese valid answers rather than relying on an invalid English mock.
- Verification: focused provider/evaluator suite `82 passed`; related runtime/configuration suite `106 passed`. `git diff --check` has no whitespace error (only pre-existing repository line-ending warnings).
- 2026-07-27 deployment: matching source/venv/static candidate `stage09-p1-20260727-r58-chinese-language-guard` passed sealed release-layout, release-manifest, release-assets, static-parity and bounded readiness gates before atomic activation. API, worker, outbox, Redis and Nginx are active; public root and health both return `200`.
- 2026-07-27 browser replay: an existing authorized Chrome Workbench tab was located, but two attempts to claim/read the live DOM exceeded the browser-control deadline. No test message was typed or sent, so this is an automation limitation rather than a passed or failed product response. The required next evidence remains one authenticated `你好` submission through the deployed r58 UI, with a redacted rendered Chinese answer and no write-side effect.
- Integration note: the later conversational-entry decision routes contextless workbench greetings to the existing `general_advice` Provider branch. This document's Chinese-answer guard therefore remains the protection that prevents a language refusal from surfacing in that normal conversational flow, while Base-bound factual queries retain their existing evidence rules.
