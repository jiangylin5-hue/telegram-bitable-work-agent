# Stage07 Digital Employee Management Work Surface

## Status

- Status: proposed TD010 Option A module boundary; no implementation exists.
- Scope: one Base-bound management plane for existing DigitalEmployee runtime objects.

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

## Acceptance Dependencies

1. TD010 Option A user approval of the durable schema/API/member-eligibility boundary.
2. Detailed implementation plan approval before code.
3. Disposable PostgreSQL migration/lock/replay/legacy-compatibility evidence before local promotion.
4. Existing S5/TD009 safe contact/context/invocation tests must remain green with `workspace` and `assigned` modes.
