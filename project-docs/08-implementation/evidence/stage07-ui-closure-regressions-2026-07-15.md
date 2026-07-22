# Stage07 UI Closure Regression Evidence — 2026-07-15

## Status

- Evidence status: local implementation and regression evidence only.
- Scope: previously uncovered Mini App failure-closed behavior in template installation/import cleanup and TD010 digital-employee activation.
- Not a Stage07 acceptance claim: this note does not replace the remaining Browser or external-system evidence required by the owning BDDs.

## Corrected Behaviors

| Owning requirement | Reproduced gap | Implemented boundary | Regression result |
| --- | --- | --- | --- |
| `TI-03` | A `409` template-installation response returned the card to an actionable state, allowing another local click before the user closed the workbench. | `TemplateImportHub` recognises status `409`, renders only fixed conflict copy, and keeps that exact card disabled until the panel unmounts. Raw response detail never enters the DOM. | Component test proves one call, disabled card and redacted fixed text. |
| `TI-11` | Closing the template/import surface removed the template list key but could retain same-workspace persisted preview-job query entries. | `clearTemplateImportQueries` clears the full same-user/workspace import prefix when no exact job is supplied; `App.closeTemplateImport` invokes that cleanup before late work can re-enter the surface. | Query-client test proves two local job entries are removed while another workspace remains intact. |
| `DEM-A07` / `DEM-A10` | The workbench could enable `Activate` from browser-local table/view/member selections that had not yet passed the server-owned save/grant commands. | `DigitalEmployeeManagementWorkbench` compares its local selection to the last server-read detail, shows a fixed save-first hint, and requires an authoritative matching reread before it enables `Activate`. | Component test proves local selection stays disabled with the hint and only matching persisted detail enables activation. |

## TDD Record

The following regression assertions were added first and were observed failing against the pre-change client:

1. a `409` template install must lock the affected card and hide raw detail;
2. closing the import workbench must clear all current-scope import job queries;
3. digital employee activation must remain disabled while scope/member changes exist only locally.

Minimal client fixes were then applied. A TypeScript build caught an invalid test fixture that put detail-only fields into a directory summary; the fixture was corrected to the actual safe DTO shape before rerunning verification.

## Verification

```text
mini-app: npm.cmd run test:run -- src/test/template-install-flow.test.tsx src/test/template-import-query.test.ts src/test/digital-employee-management-workbench.test.tsx
result: 3 files / 9 tests passed

mini-app: npm.cmd run build
result: passed (tsc -b and Vite production build)
```

## Remaining Evidence Limits

- No Browser file-selection/upload was performed here; `TI-A04`, `TI-A06` and `TI-A08` keep their owning BDD's Browser evidence limit.
- No Telegram, OpenRouter, staging, production or user Chrome action was used.
- No claim is made that this isolated regression record completes V1, template/import, TD010 or Stage07.
