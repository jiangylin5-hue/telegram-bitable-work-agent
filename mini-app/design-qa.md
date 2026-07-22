# F1 Field Builder Visual QA

## Result

passed (F1 visual scope)

## Scope and reference

- Scope: the F1 Base Canvas field-creation path only, not the complete Stage07 product.
- Reference: `../project-docs/08-implementation/assets/stage07/workspace-ledger-reference.png`.
- Comparison: the reference and rendered F1 desktop state were emitted together for review at 1440px. The test then exercised 1280px, 430px and 390px with a disposable local fixture.

## Passed F1 visual checks

- The Canvas keeps the selected reference grammar where F1 owns it: white surface, cool gray separators, restrained azure action color, compact 6-8px controls and a dense table toolbar.
- Desktop field creation uses a right-side drawer; 430px and 390px use a full-width sheet with a visible close control, labelled inputs and an anchored action row.
- The corrected 390px nonempty-table toolbar keeps both `添加字段` and `新建记录` reachable. This was verified by opening the drawer from the actual mobile trigger, rather than resizing an already-open drawer.
- Blank-name validation, retryable 503 feedback, locked 409 feedback and generic 403 denial were observed. The final fixture console check reported no warnings or errors.
- The corrected direct-edit fixture changed `客户阶段` from `新建` to `跟进中`, removed `续费关注` from the selected tags and rendered version `2` in both Grid and Record Detail. The retained sanitized evidence is `../project-docs/08-implementation/artifacts/stage07/f1-direct-edit-success-1440.png`; the final console check was empty.
- The duplicate-name fixture was exercised at 1440px, 1280px, 430px and 390px. At every width it preserved `客户阶段`, showed only `字段名称已存在，请使用其他名称。` and omitted `field_name`; the final console check was empty. The companion pending fixture kept the dialog visible and disabled create, close and cancel at each of the four widths.

## Blocking evidence gaps

- The source reference includes a populated Workspace Ledger plus assistant rail, which belongs to wider Package 2/4 work and is intentionally not claimed as F1 parity.
- The delayed workspace/view replacement remains an application-level scope-isolation test because the modal correctly blocks the impossible background interaction. It is covered by the delayed-receipt application test, rather than by a forced browser interaction that the UI correctly makes impossible.
- The three F1 real-PostgreSQL proof cases ran and passed on 2026-07-11 against an authorised disposable local database. This supports F1's implementation evidence; it does not extend this visual-QA result to wider Stage07 scope.

## Stage07 Visual Rebaseline QA — 2026-07-16

### Result

passed (local rendered visual-rebaseline scope only)

### Boundary

- Compared against the approved `Work Queue Atlas`, `Workspace Ledger`, `Conversation Desk`, and `Digital Employee Workbench` references in `../project-docs/08-implementation/assets/stage07/`.
- The rendered data came from a disposable loopback-only fixture on `127.0.0.1`. It contained synthetic workspace, Base, employee, draft, record and Team Bot data only; it made no database, provider, Telegram, webhook, deployment, or user-browser write.
- This observation is not Telegram Mini App, PostgreSQL, provider, staging, production, or wider Stage07 acceptance evidence.

### Rendered coverage

| Width | Observed visual states | Result |
| --- | --- | --- |
| 1440px | Home queue, Base Grid, Team Bot three-pane summary, Draft confirmation three-pane review, Digital Employee directory/configuration/audit rail | passed |
| 1280px | Home three-rail responsive desktop layout | passed |
| 430px | Home/Base mobile translation and full-screen Digital Employee workbench | passed |
| 390px | Home, dense Grid with intentional internal table scrolling, full-screen Draft confirmation, and full-screen Digital Employee workbench | passed |

### Resolved visual mismatches

- Mobile Home toolbar no longer squeezes the title into a two-line fragment.
- Mobile Base actions use a horizontally reachable action band and put the `新建记录` primary action first; the data grid retains intentional internal horizontal scrolling.
- Mobile Draft confirmation now occupies the full viewport rather than a desktop-width centered card.
- Mobile Digital Employee audit information collapses to a readable single column.
- Modal heading focus remains programmatically available without a browser-default yellow outline becoming a visual artifact.

### Quality checks

- Page-level `documentElement.scrollWidth` matched the mobile viewport at 390px and 430px; the 390px Grid’s horizontal scroll is confined to the data grid.
- The local browser console’s `error` and `warn` lists were both empty after the rendered interactions.
- `npm.cmd test -- --run`: `64` files / `233` tests passed. One earlier aggregate retry missed a governance-flow control under suite load; the isolated four-case regression passed three consecutive times and the fresh complete retry passed without source changes.
- `npm.cmd run build`: passed.
- `git diff --check`: passed (only existing Windows line-ending warnings were emitted).

## Stage07 Reference Acceptance — 2026-07-16

### Result

blocked (reference-fidelity acceptance)

The earlier rebaseline render check proves the current components can render safely; it does not constitute approval against the four selected visual references. The current 1440 × 900 comparison and retained evidence are in `../project-docs/08-implementation/evidence/stage07-visual-acceptance-2026-07-16.md`.

The blocking deltas are intentional scope gaps rather than a claim of missing safe workflow behavior: Home/Base remain materially sparser than the Work Queue Atlas and Workspace Ledger; Team Bot/Draft remain modal overlays rather than the Conversation Desk; and Digital Employee Management remains a sparse modal instead of the selected full-page workbench. The report records the required redesign scope before visual approval.
