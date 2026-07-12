# Stage07 Governance Readback Design

## Status And Scope

- Status: proposed design; no implementation approval yet
- Package: coherent Package 3 read-only governance workbench
- Purpose: let authorised workspace managers inspect current membership and Base-level audit history without leaking policies, traces, raw state or identity data beyond the approved safe model

## Product Boundary

The workbench is an operational inspection surface, not a permission editor. It proves that management decisions are server-backed and auditable before the product adds high-risk role/policy writes.

Included:

1. capability-hinted entry from the existing App Shell;
2. workspace member directory with cursor pagination;
3. Base-selected audit timeline with cursor pagination;
4. loading, empty, denied, missing, malformed, retryable and scope-change states;
5. protected-state cleanup, fixed event labels and responsive desktop/mobile layouts.

Excluded:

- create/invite/deactivate member;
- change role or view/field policy;
- inspect policy snapshots, trace IDs, raw audit state, record values or actor IDs;
- audit search/export/filtering, cross-Base aggregation, retention/deletion controls;
- Bot administration, digital employee lifecycle, knowledge/memory, draft detail/confirm/reject and Telegram deep links.

## Design Direction

Desktop opens a two-pane governance workbench: member list at workspace level, then a Base audit timeline after the operator explicitly chooses an already-authorised Base. Mobile uses one labelled full-screen sheet per surface, preserving the same command path. Neither layout replaces the existing Base Canvas.

```text
server-derived management hint
  -> Governance entry
  -> protected member page
  -> authorised Base selector (safe Base summaries already loaded)
  -> protected Base audit page
```

## Alternatives

The full decision and recommendation are in [Technical Decision 003](../../project-docs/08-implementation/STAGE_07_TECHNICAL_DECISION_003_GOVERNANCE_SAFE_READ_MODEL.md). The selected design is Option C: dedicated Mini App safe projections. It is the only option that avoids browser receipt of the raw generic audit model while preserving existing Stage06 route compatibility.

## Components

| Component | Responsibility | Cannot do |
| --- | --- | --- |
| `GovernanceWorkbench` | panel state, safe tab selection, scoped retry/focus return | infer authority or mutate a member/policy |
| `MemberDirectory` | render safe member cards/table and cursor continuation | paginate from local role list or expose member metadata not in DTO |
| `AuditTimeline` | render fixed event labels and cursor continuation for a selected Base | render audit state, trace, actor ID, entity ID or source error detail |
| `governance-types` / `api` | closed parsers and safe request methods | pass through unknown keys or generic audit route responses |
| protected-query helpers | exact cancellation/removal for workspace/Base scope | persist governance data across session/workspace changes |

## State Model

| Surface | States | Terminal rule |
| --- | --- | --- |
| entry | hidden, visible, opening | hidden without capability; visible remains a non-authoritative hint |
| members | loading, ready, empty, page-loading, page-error, denied, malformed, cancelled | only a server page may add rows |
| Base selection | none, selected, replaced, denied | previous audit state is removed before a new Base read |
| audit | idle, loading, ready, empty, page-loading, page-error, denied, missing, malformed, cancelled | never show an event from an earlier Base/workspace generation |
| retry | enabled, pending, cancelled | retry repeats only the failed GET, never a mutation |

## Error Rules

| Response | UI | Cache effect |
| --- | --- | --- |
| `200` | parse exact DTO; render allowed rows only | retain exact current scope page |
| `401` | existing expired-session boundary | cancel/remove all Stage07 protected queries |
| `403` | generic denied boundary | remove active workspace governance state |
| `404` audit Base | generic missing/denied-safe boundary | remove only exact Base audit page |
| `422` cursor | fixed retryable pagination message; no server text | retain first authorised page; discard failed cursor page |
| malformed / network / `5xx` | fixed retryable message | no raw body, no stale cross-scope result |

## Acceptance Direction

The code may begin only after the user approves Technical Decision 003 and this design package. Acceptance requires closed API parser tests, server authorization/redaction/pagination tests, protected-cache tests, a disposable PostgreSQL readback path and focused Browser checks. Four-width polish and role/policy writes remain separate work.
