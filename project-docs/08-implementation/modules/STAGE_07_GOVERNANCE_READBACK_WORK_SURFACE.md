# Stage07 Governance Readback Work Surface

## Scope

This module is the first safe, read-only slice of `Governance`: membership visibility and Base audit timeline. It intentionally does not inherit the broader future Governance module's write responsibilities.

## Inputs And Outputs

| Input | Source | Output | Consumer |
| --- | --- | --- | --- |
| verified user/workspace | existing bootstrap | protected query scope | App lifecycle |
| workspace management hint | existing bootstrap capability | visible entry hint only | App Shell |
| safe member page | proposed Mini App member projection | member list/continuation | Governance workbench |
| authorised Base summary | existing Home/Base data | selected Base ID | Audit timeline |
| safe audit page | proposed Mini App audit projection | fixed timeline rows/continuation | Governance workbench |

## Functional Surfaces

### Member Directory

- desktop: compact, sortable-free table with user ID, role and status; no profile card or mutation affordance;
- mobile: labelled list rows retaining role/status and cursor continuation;
- allowed actions: open, load more, retry, close;
- forbidden actions: edit role, invite, deactivate, copy bulk members, export.

### Base Audit Timeline

- Base selection uses authorised Base summaries only; it does not enumerate hidden Bases;
- each row has a stable date/time, fixed actor-type icon, fixed event label and entity-type label;
- no expandable payload, trace, event copy, entity navigation, raw state comparison or filter controls;
- allowed actions: select Base, load more, retry, close.

## State Transitions

```text
closed -> members-loading -> members-ready | members-empty | denied | retryable
members-ready + select-base -> audit-loading -> audit-ready | audit-empty | missing | denied | retryable
audit-ready + replace-base -> cancel/remove old audit -> audit-loading(new base)
any state + workspace/session invalidation -> cancel/remove protected state -> safe boundary
```

## Accessibility And Responsive Requirements

- workbench/dialog has an accessible name and focus trap/return behavior matching existing panels;
- list/table semantics expose loading and continuation status to assistive technology;
- retry and load-more controls remain keyboard reachable at 390px;
- no horizontal scroll is required to identify member role/status or audit event label;
- the UI never relies on color alone for denial, status or event kind.

## Acceptance Ownership

BDD `GR-01`--`GR-07` owns behavior; SDD owns API/cache safety; Complex Index owns difficult cursor/redaction/race cases. This work surface owns only composition and presentation.
