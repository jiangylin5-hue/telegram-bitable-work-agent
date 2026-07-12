# Stage07 Template And Import Work Surface

## Status

- Document status: functional-module specification awaiting review
- Scope: one coherent Templates & Imports management surface and its existing-contract entry points
- Implementation status: not started

## 1. Entry Map

```text
Workspace Home (authorized management entry)
  -> Templates & Imports Hub
     -> Template shelf -> Install -> refreshed Base
     -> Import new Base -> Preview -> Commit -> refreshed Base

Authorized Base Canvas (More actions)
  -> Save as template -> safe draft receipt
  -> Import into this Base -> Preview -> Commit -> refreshed current Base/new table
```

No generic Base picker, template manifest page, import history page or direct URL recovery page exists in this scope.

## 2. Functional Modules

| Module | What it does | Data it may show | What it must never do |
| --- | --- | --- | --- |
| Hub | routes between template shelf and import intake; presents loading/empty/denied/retry | selected workspace name and safe template summaries | infer permissions, list hidden Bases or retain file data |
| Template shelf | groups safe template summaries by returned category | name, description, version, status | render manifest, template creator or raw resource map |
| Install action | starts one installation and navigates only after reread | template name and pending/safe error state | optimistically add a Base or retry 409 automatically |
| Save template panel | submits name/category/description for current authorized Base | form values and safe template response | expose/edit manifest, publish/share/delete/version template |
| File intake | reads one local CSV/XLSX in memory and creates preview | filename, selected format and fixed local validation copy | parse XLSX/CSV into a browser-side authority model or upload elsewhere |
| Preview | presents server-inferred fields and first returned rows | safe schema, bounded rows, job status | claim commit, render raw error summary or full stored file |
| Mapping editor | maps scalar inferred columns | source key/name/type and local target controls | create complex fields/options/relations/lookups or infer server acceptance |
| Commit action | submits explicit final command then refreshes resources | Base/table names/key, safe progress/copy | add records/table to Canvas optimistically |

## 3. User-visible States

| Module | Normal | Empty | Pending | Failure | Terminal result |
| --- | --- | --- | --- | --- | --- |
| shelf | categorized templates | no templates available | loading list/installing card | denied/retryable | none; remains shelf |
| save template | editable form | n/a | saving | validation/denied/retryable | safe draft metadata shown |
| intake | selected file | no file selected | reading/creating preview | local-invalid/server-invalid/denied | preview ready only |
| preview | 20-or-fewer server rows | no rows is a server error | refreshing job | missing/denied/retryable | commit eligible only |
| mapping | server default/edited | n/a | commit pending | local-invalid/server-invalid/conflict | safe committed reread |
| navigation | refreshed Home/Base | resource absent from safe list | rereading | denied/missing | opened authoritative Base/table |

## 4. Information Hierarchy

Desktop order is: workspace context → route title → selected template/file identity → bounded server preview → mapping → irreversible commit copy → primary action. Mobile uses the same order in one full-screen sheet. The commit action says `提交导入` and stays visually distinct from preview creation; preview says `生成预览` and never uses success styling.

## 5. Accessibility Requirements

- Every trigger has a stable accessible name: `模板与导入`, `安装模板`, `保存为模板`, `导入到新 Base`, `导入到当前 Base`, `生成预览`, `提交导入`.
- Preview table has headers from safe schema and an accessible row-count/status summary.
- Async progress is `role=status`; fixed failures use `role=alert`.
- Focus starts at panel heading, remains inside modal/sheet while open, and returns to the exact opener on close/cancel/error boundary.
- Native file input is labelled; no drag-only workflow.

## 6. Acceptance Boundary

The module is accepted only when its BDD IDs TI-A01 through TI-A08 have real evidence. It remains outside governance management, Bot, Telegram, public template marketplace, production upload/storage and Stage07 final acceptance.
