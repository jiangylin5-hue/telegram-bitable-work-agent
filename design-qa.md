# Stage09 Ledgerline Design QA

## Scope and comparison

- Reference: `project-docs/08-implementation/assets/stage09/ledgerline-workbench-selected.png` (1487 × 1059).
- Implementation evidence: `project-docs/08-implementation/evidence/stage09-visual-qa/desktop-read-only-complete.png` and `compact-current-record.png`.
- Browser state: local FastAPI plus an isolated PostgreSQL container, one provisioned workspace/base/customer record, one authorized employee, four server-projected skills, and a read-only current-record query. No production record, Telegram action, remote credential, prompt or model response was stored locally.

The reference is a dense risk-and-draft demonstration; the captured implementation is a customer read-only state with no local analysis provider. They share the relevant UI state for this review: an authorized current record, a selected employee, server-projected skills, a continuous timeline and a fixed bottom composer. Draft content is intentionally absent because the local record has no field-level draft proof.

## Fidelity review

| Surface | Result | Evidence |
| --- | --- | --- |
| Table-first grammar | Pass | Desktop keeps the workspace navigation outside a wide Ledgerline workbench; the workbench uses a context strip, continuous ledger, safe-scope rail and bottom composer rather than a generic chat card. |
| Typography, spacing and hierarchy | Pass | The context strip, numbered rail, request heading, event rows and safety rail maintain the restrained Feishu-like information density of the selected reference without copying its fictional business data. |
| Server skill affiliation | Pass | Browser observed `auto`, `platform-base`, `platform-tabular-analysis`, `platform-task` and `platform-telegram-im`; no client-only capability tag is rendered. |
| Modal layering | Pass after fix | The backdrop is `position: fixed`, `z-index: 20`; it covers the viewport rather than relying on portal document flow. This fixed the compact record-detail occlusion. |
| Compact current-record path | Pass after fix | At the compact breakpoint, the record-detail header exposes “在当前记录中打开 AI 对话”; opening it retains the record detail and shows all five skill controls inside the modal. The entry disappears while editing. |
| Safe terminal state | Pass | The local provider-unavailable result is rendered as a completed safe ledger entry with `analysis_unavailable`, not invented model content or a false success. |

## Browser interaction checks

1. Opened the provisioned Base, opened the customer record, and opened Ledgerline from the record-context entry.
2. Verified the catalog request returned and rendered all four backend registry skills plus auto mode.
3. Selected `platform-base`, submitted a read-only question, and observed ordered SSE lifecycle rows ending in a safe terminal state.
4. Verified desktop dialog bounds (1240 × 992 CSS px inside a 1440 × 1024 acceptance viewport), visible safe-scope rail, and fixed composer.
5. Verified compact viewport (375 CSS px effective width): no horizontal page overflow, dialog is above the full-screen record detail, and the skill strip remains horizontally reachable.
6. Browser console contained no Mini App application error. A separate Browser-runtime Statsig registration timeout is external tooling telemetry and does not originate from the local Mini App bundle.

## Findings resolved during this review

- P1: Vite did not proxy `/api`, so the live skills catalog was silently rendered empty. Added the Stage08 `/api` local proxy plus regression test.
- P1: the portal backdrop was static in document flow and was hidden below the compact record-detail panel. Made it a fixed modal layer above the panel.
- P1: a full-screen record detail hid the only Base-level AI entry. Added a compact-only record-context entry that preserves the authoritative current record and is disabled by absence during human editing.

No P0, P1 or P2 visual issue remains in the reviewed desktop or compact state.

final result: passed
