# Stage 07 Test Plan

## Status

- Document status: planned verification matrix
- Scope: unit, integration, contract, visual and manual Mini App evidence

## 1. Test Layers

| Layer | Focus | Evidence |
| --- | --- | --- |
| unit | view-model mapping, field formatting, state reducers, diff rendering | deterministic component tests |
| integration | route bootstrap, queue destinations, view changes, draft lifecycle | mocked authorized/denied API responses |
| contract | request shape, cursor/version/idempotency handling, proposed endpoint gates | backend/API tests and typed client contract tests |
| security | hidden fields, workspace boundaries, revoked membership, chat/Bot scope | negative tests plus cache-clear assertions |
| visual | selected white design system, desktop/mobile layout and state screens | reviewed screenshots at target viewports |
| manual | Telegram entry/deep link and approved real identity path | sanitized run note only |

## 2. Required Matrices

- desktop widths: 1280px and 1440px; mobile widths: 390px and 430px;
- roles: owner/admin/builder/operator/viewer plus inactive member;
- views: Grid/Kanban/Calendar/Form;
- states: loading/empty/denied/error/conflict/expired/success;
- Bot classes: team contact and personal assistant;
- write outcomes: confirm/reject/replay/conflict/expired.

## 3. Completion Rule

No visual pass substitutes for authorization/contract tests. No mocked UI pass substitutes for the approved Telegram deep-link smoke. Test artifacts must not contain raw hidden fields, prompts, memory or Telegram text.
