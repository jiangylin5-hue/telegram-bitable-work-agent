# Stage07 Technical Decision 010: Digital Employee Management And Work Scope

## Status

- Decision status: proposed for one-time user review on 2026-07-13.
- Scope: one coherent management plane for the existing base-bound `DigitalEmployee` runtime.
- Code status: no implementation, migration, endpoint, UI, test fixture, dependency or external action is authorized by this document.

## Product Problem

TD005/TD006 and TD009 make an existing active digital employee safely callable, but a workspace user cannot safely create, configure, pause, assign or inspect that employee through the Mini App. The generic Stage06 runtime routes are intentionally unsuitable for a browser management UI because they return general runtime/configuration shapes.

The next product increment must turn the existing runtime object into a controlled workspace resource without inventing a new agent framework, changing table authority, widening a caller's data access or treating Telegram identity as employee authority.

## Reusable Foundation

| Existing asset | Reuse | Not exposed in the management UI |
| --- | --- | --- |
| `DigitalEmployee` | existing workspace/Base binding, table/view scopes, allowed actions, field/confirmation policies and runtime | raw policies, response style, provider/runtime data, trace or generic invoke response |
| Stage06 create/update services | scope validation, audit convention and Base ownership | generic Stage06 response/patch contract |
| S4 governance command pattern | expected-version, row lock, idempotency, audit and exact query cleanup | a second RBAC engine |
| TD006/TD009 safe adapter | fixed `summarize` and Canvas-only `draft_update`; contact and context read paths | generic model/action chooser |
| Feishu Base / Lark capability grammar | workspace resource, scoped management and explicit member assignment | Feishu API compatibility or dependency |

## Options

| Option | Product result | Schema/API impact | Decision |
| --- | --- | --- | --- |
| A — base-bound managed employee with explicit member grants **(recommended)** | Managers create a draft employee for one Base, set table/view scope and fixed intents, assign members, then activate/pause it. | one employee version, one access-mode field, one grant table, safe Mini App management adapter and reuse of existing authorization actions. | Recommended: completes the current product loop with smallest durable model. |
| B — workspace-wide multi-Base employee first | One employee can own several Base scopes and member assignments. | new scope table, cross-Base policy, context selector, migration/index and conflict rules. | Rejected now: combines several independent authority problems before the one-Base management loop is proven. |
| C — UI over generic Stage06 routes | Expose current create/update/read routes directly in the browser. | no migration. | Rejected: generic DTO/configuration/runtime surface is not browser-safe and has no versioned management contract. |

## Recommended Decision: Option A

### Product Contract

```text
authorized manager
-> select one Base
-> create employee in draft
-> set safe table/view scopes and fixed intents
-> select workspace members when access_mode = assigned
-> activate after server validation
-> members use existing safe contact/context/invocation flows
-> manager can pause, revise while paused, then reactivate
```

- An employee remains permanently bound to one existing Base in this package. Changing `base_id`, multi-Base scope, delete/archive, clone and import/export are excluded.
- Browser-configurable actions are a closed enum: `summarize` and `draft_update`. `draft_update` remains current-Canvas-record-only under TD006; Home remains summary-only under TD009.
- Browser-configurable fields are name, description, optional alias, table scope, view scope, fixed intents, access mode and member assignment. Field policy, confirmation policy, response style, raw prompt/tool/runtime/provider settings remain server-owned and cannot be configured here.
- Lifecycle is `draft -> active -> paused -> active`. A draft or paused employee may be edited; an active employee must be paused before scope/action/member configuration changes. There is no archive/delete transition in this package.

### Access Assignment

`access_mode` is one of:

| Value | Meaning | Compatibility rule |
| --- | --- | --- |
| `workspace` | any active workspace member independently authorized for existing `digital_employee.invoke` may discover/use the active employee, still subject to Base/view/field scope. | all pre-existing employees are migrated to this mode, preserving current behavior. |
| `assigned` | an active workspace member must also have a `DigitalEmployeeMemberGrant` for the employee before safe contact/context/invocation reads succeed. | new employees default to this mode; activation requires at least one grant. |

Assignment grants only grant discovery/use eligibility. They never grant workspace, Base, view, field, record, management, confirmation or external-send authority. Effective authority remains:

```text
employee active status and configured scope
-> assigned-member eligibility when selected
-> caller existing workspace action
-> caller current Base/view/field/record permission
```

### Proposed Durable Model

| Object | Proposed fields/change | Purpose |
| --- | --- | --- |
| `digital_employees` | additive `version: int >= 1`, `access_mode: workspace|assigned` | optimistic concurrency and backward-compatible use eligibility |
| `digital_employee_member_grants` | `id`, `employee_id`, `workspace_member_id`, timestamps; unique `(employee_id, workspace_member_id)` | explicit assigned-member eligibility only |
| existing status | service-validated `draft|active|paused` | lifecycle without a new generic agent table |

Existing rows receive `version=1` and `access_mode=workspace`; no existing employee is silently paused or loses current contact eligibility. Existing arbitrary status values are not normalized by a blind migration: only `active` is usable; any non-active legacy row is unavailable until an authorized manager explicitly reads and repairs it through a later compatibility procedure.

### Proposed Safe Mini App Contract

| Route | Authority | Safe response/command |
| --- | --- | --- |
| `GET /mini-app/bases/{base_id}/digital-employee-management-context` | `digital_employee.create` or `digital_employee.update` plus Base access | Base label; caller-readable tables/views; assignable active member labels/roles only |
| `GET /mini-app/bases/{base_id}/digital-employees/management` | `digital_employee.update` plus Base access | paged manager list: safe identity, status, access mode, scope/grant counts and version |
| `POST /mini-app/bases/{base_id}/digital-employees/management` | existing `digital_employee.create` | idempotent creation of a `draft` employee; safe receipt/detail |
| `GET /mini-app/digital-employees/{employee_id}/management` | existing `digital_employee.update`; Base access | browser-safe editable projection only |
| `PATCH /mini-app/digital-employees/{employee_id}/management` | existing `digital_employee.update`; row lock/version | editable draft/paused configuration with exact reread receipt |
| `PUT /mini-app/digital-employees/{employee_id}/member-grants` | existing `digital_employee.update`; row lock/version | replace exact assigned-member set; no per-row direct grant API |
| `POST /mini-app/digital-employees/{employee_id}/activate` / `pause` | existing `digital_employee.update`; idempotency and row lock/version | terminal lifecycle receipt `{id,status,version,audit_event_id}` |

No management route returns raw scope policies, hidden table/view names, field/record values, provider settings, traces, prompt history, generic Stage06 `DigitalEmployeeResponse`, runtime output or raw error body.

### Activation Invariants

Activation succeeds only when all are true:

1. Employee is `draft` or `paused`, expected version is current and row lock is held.
2. Bound Base still belongs to employee workspace and caller retains Base access.
3. Every selected table belongs to the Base; every selected view belongs to the Base and its table belongs to selected table scope.
4. At least one selected view and the `summarize` intent exist; allowed actions are only the approved closed enum.
5. `access_mode=assigned` has at least one active member grant, and every grant is in the same workspace and active.
6. Alias satisfies existing active-alias uniqueness after transition.
7. Server records a redacted audit event and increments employee version atomically.

Pause immediately removes the employee from TD009 contacts/context and rejects safe invocation as a generic unavailable resource. It does not cancel existing drafts or modify records.

## Explicit Non-Goals

- Multi-Base scopes, Base reassignment, clone/import/export, archive/delete or agent marketplace.
- General chat, threads, durable memory, knowledge sources, embeddings, retrieval, primary-record labels or record picker.
- Custom action DSL, raw SQL/tool selection, generic runtime/provider model selection, automatic writes, self-confirmation or external send.
- Telegram member/group/contact routing, Bot publication, notifications, deployment or production rollout.
- New general permission engine or a grant that bypasses workspace/Base/view/field/record authority.

## Approval Requested

Approval of Option A would authorize a detailed implementation plan only. It does **not** authorize code until the plan is separately reviewed. It would require a migration, safe API contract and member-assignment permission behavior; these are the exact technical/permission changes awaiting user approval.
