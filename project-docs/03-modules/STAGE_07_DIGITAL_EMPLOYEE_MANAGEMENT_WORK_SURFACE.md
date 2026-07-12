# Stage07 Digital Employee Management Work Surface

## Status

- Status: `implemented-local` for the approved TD010 Option A module boundary.
- Scope: one Base-bound management plane for existing DigitalEmployee runtime objects.
- Acceptance limit: automatic/local database evidence exists; user-controlled browser visual review and all external environment evidence remain open.

## Functional Modules

| Module | Reused foundation | Responsibility | Explicit boundary |
| --- | --- | --- | --- |
| Management entry | Base Canvas/AppShell capability conventions | shows one Base-scoped management entry only when server authority permits | no global Agent marketplace or client-only role inference |
| Directory | current DigitalEmployee + cursor/page pattern | safe Base-local employee list, status and counts | no runtime/config/policy/record data |
| Context selector | existing Base/table/view/member reads | offers only caller-readable tables/views/assignable members | no hidden resource or Telegram identity |
| Draft editor | Stage06 service + S4 version command pattern | name, description, alias, scopes, fixed intents and access mode | no custom actions, policies, prompt or provider choice |
| Grant replacement | workspace members + employee row lock | replaces exact assigned use-eligibility set | no member/Base/view/field permission grant |
| Lifecycle command | existing audit/idempotency pattern | draft activation and active pause with authoritative reread | no delete/archive/automatic resume |
| Safe consumer integration | TD005/TD006/TD009 adapters | filters contacts/context/invocations using active status/access mode/grant | no Home draft path or generic invoke expansion |

## State Ownership

| State | Owner | Lifetime | Clear trigger |
| --- | --- | --- | --- |
| employee version/status/access mode | server `DigitalEmployee` | durable | versioned command only |
| member grants | server grant table | durable | versioned set replacement only |
| management directory/context/detail | protected QueryClient | current user/workspace/Base | close, replacement, mutation, denial or exact missing resource |
| unsaved editor values | local workbench state | open panel | close, selected employee/Base/workspace replacement; conflict retains typed values only |
| contact eligibility | server adapter | per request | status/grant/workspace/Base/view change |

## Supported User Actions

| Action | Preconditions | Server effect | Durable result |
| --- | --- | --- | --- |
| create draft | create action + Base access | idempotent draft creation | employee `draft@v1` plus redacted audit |
| save configuration | `draft|paused`, update action, current version | validates exact scope/action set | same state and incremented version |
| replace assignments | `draft|paused`, current version | validates/replaces exact eligible member set | grant set and incremented employee version |
| activate | complete safe configuration | locked authoritative checklist | `active` receipt/audit |
| pause | current active employee/version | locked lifecycle command | `paused` receipt/audit; contact unavailable |
| invoke | active + caller eligible + existing scope | existing S5/TD006/TD009 flow | summary or current Canvas draft only |

## Explicitly Excluded Work

- Multiple Bases, changing Base, archive/delete, clone, import/export and generic employee templates.
- New permission engine, custom role/action model, member management or member identity data.
- Field-policy/confirmation-policy/response-style editor, prompt/template/tool/provider editor or raw runtime inspection.
- General chat/thread, memory, knowledge/indexing, record picker/search and direct write/send.
- Telegram routing/publication/binding, notifications, deployment and production operations.

## Acceptance Status

1. **Completed:** TD010 Option A user approval of the durable schema/API/member-eligibility boundary.
2. **Completed:** detailed implementation plan approval before code.
3. **Completed locally:** disposable PostgreSQL migration shape, downgrade/upgrade replay and legacy-compatibility evidence.
4. **Completed locally:** focused TD005/TD006/TD009 contact/context/invocation regression runs remain green with `workspace` and `assigned` modes.
5. **Open:** user-controlled browser visual review and real Telegram/provider/staging/production evidence; none is substituted by the automatic suite.

## Implementation Reconciliation

The delivered workbench contains only the listed management entry, directory, scoped selector, draft editor, grant replacement and lifecycle controls. The entry is capability-gated by server bootstrap data; every route independently rechecks existing authorization. Member labels remain opaque, active configuration is read-only until pause, and successful mutation causes authoritative reread rather than an optimistic configuration/lifecycle state. No excluded module was introduced.
