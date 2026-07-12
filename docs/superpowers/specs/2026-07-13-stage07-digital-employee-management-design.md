# Stage07 Digital Employee Management Design

## Status

- Status: proposed TD010 Option A design for one-time review.
- Code precondition: user approval of TD010 and then a detailed implementation plan.
- Scope: base-bound employee management, assignment and `draft|active|paused` lifecycle only.

## User Outcome

A manager can open a Base-level digital employee directory, create a draft employee, select only readable tables/views and the fixed summary/draft intents, optionally restrict use to selected members, activate it, later pause it and safely revise it. A regular member can discover/use only an active employee that is both assigned (when required) and already within their own permission scope.

## Interaction States

| State | Visible content | Permitted action | Must never imply |
| --- | --- | --- | --- |
| `directory-loading` | fixed loading state | close/retry | old employee rows remain valid |
| `directory-empty` | no managed employee for Base | create when authorized | generic workspace-wide search |
| `draft-new` | empty safe configuration | choose tables/views/intents/mode/members | active ability before validation |
| `draft-invalid` | local field/invariant feedback | correct configuration | server write occurred |
| `draft-ready` | complete safe configuration | idempotent create | automatic activation |
| `configuration-loading` | safe detail reread | close only | cached policy/field data |
| `paused-editing` | current safe configuration and version | save or replace grants | member assignment widens Base permissions |
| `active-readonly` | status, safe scope counts and grant count | pause | live scope mutation |
| `activation-pending` / `pause-pending` | disabled duplicate command | wait/close | optimistic active/paused state |
| `conflict` | fixed reread instruction | reread | local state won server race |
| `denied` / `missing` | existing generic boundary or fixed local notice | leave/re-enter | existence, hidden names or raw error |

## Surface Layout

The desktop Base canvas obtains an “数字员工” management entry only from server-derived existing management capability. The workbench follows current Governance/Builder dialog conventions:

```text
left: safe employee directory and explicit create
right: identity + lifecycle + Base scope + use eligibility
footer: versioned save / replace assignments / activate or pause
```

On mobile it becomes the existing full-height sheet convention. The mobile and desktop contract is identical; only layout changes. No new visual system, generated image, dark dashboard, chat transcript or browser URL route is introduced.

## Management Steps

1. Manager selects the Base that already owns the employee scope; Base binding is not editable.
2. Context fetch provides only currently readable tables/views and assignable active members.
3. Manager creates a `draft` with basic identity and closed intent choices.
4. Manager configures scopes while the employee is draft or paused. View selection is constrained by selected table scope.
5. If access mode is `assigned`, manager replaces the exact member set. The UI shows only member display labels and role, never e-mail, Telegram identity or private policy.
6. Manager explicitly activates. The server rereads and validates the entire Base/table/view/member intersection under a row lock.
7. Active state is read-only in the editor. Pause is explicit; only after authoritative paused receipt may configuration change.

## Error And Safety Design

- `401` uses existing whole protected-session cleanup; `403` removes the current workspace boundary; `404` removes the exact employee/context subtree and never exposes resource existence.
- `409` returns fixed reread copy. The UI discards unsafe server-derived configuration and retains only unsaved typed basic values until the user explicitly rereads.
- `422`, malformed or `5xx` show fixed retry copy without raw error/provider/policy data.
- Close, Base change, workspace change, employee selection change and lifecycle/configuration completion cancel exact protected queries and invalidate late results.
- Member assignment is an additional eligibility gate, never a permission grant. The UI does not display field policies, record values, prompts, provider settings, runtime traces or audit payloads.

## Alternatives Rejected In Design

- A workspace-wide/multi-Base editor is deferred because it cannot safely reuse the current Base-bound runtime scope.
- A generic “Agent Builder” is deferred because it would create a new policy/action/tool framework instead of using fixed existing actions.
- A direct wrapper over Stage06 generic runtime endpoints is forbidden because those DTOs are not browser-safe.

## Acceptance Shape

The first implementation must prove safe manager/caller separation, strict scope/member validation, row-lock/version/idempotency behavior, no contact eligibility regression for legacy `workspace` mode, active alias uniqueness, query cleanup and responsive UI. It must not claim Telegram, provider, deployment, production or full Stage07 acceptance.
