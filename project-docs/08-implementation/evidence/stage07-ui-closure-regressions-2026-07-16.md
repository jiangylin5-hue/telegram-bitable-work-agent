# Stage07 UI Visual Rebaseline Closure Record

## Status

- Evidence status: local synthetic rendering evidence
- Scope: visual-rebaseline implementation only
- Date: 2026-07-16
- Result: passed for the stated visual scope; no Stage07 acceptance status changes

## What was observed

An in-app Browser rendered the built Mini App through a disposable loopback-only fixture. The fixture used synthetic workspace, Base, record, employee, Team Bot and draft DTOs. No Telegram call, provider call, database write, webhook change, deployment, Chrome access, user data, or remote system action occurred.

| Surface | Reference family | Desktop observation |
| --- | --- | --- |
| Workspace Home | Work Queue Atlas | Queue-first central column, recent-Base rail and assistant rail at 1440px. |
| Base Canvas | Workspace Ledger | Compact tab/tool bands and dense Grid at 1440px. |
| Team Bot | Conversation Desk | Assistant directory, authorized view and summary/audit rail at 1440px. |
| Draft Hub | Conversation Desk | Employee directory, current context and explicit confirm/reject rail at 1440px. |
| Employee management | Digital Employee Workbench | Base-bound employee directory, scope configuration and status/audit rail at 1440px. |

Responsive local observations covered `1280`, `430`, and `390` widths. At 390px the page itself did not horizontally overflow. The Grid continues to use deliberate internal horizontal scrolling so table semantics are preserved. The final local browser log scan returned no warnings or errors.

## Corrections made during QA

1. Kept Home’s mobile heading single-line while retaining directly reachable queue actions.
2. Reworked the mobile Base action band so controls do not wrap into clipped multiline buttons and `新建记录` is first.
3. Made the Draft Hub a genuine full-screen mobile sheet.
4. Collapsed the Digital Employee review/audit rail to one readable mobile column.
5. Removed the browser-default visual focus outline from programmatically focused modal headings without removing keyboard focus treatment from interactive controls.

## Mechanical verification

| Command | Result |
| --- | --- |
| `npm.cmd test -- --run` | `64` files / `233` tests passed |
| `npm.cmd run build` | passed |
| `git diff --check` | passed; pre-existing Windows line-ending warnings only |

The first aggregate test attempt saw one transient governance-write flow lookup miss. It passed in three isolated consecutive runs and in the final aggregate retry; no unrelated governance source was changed for this visual work.

## Cleanup and remaining limits

- The temporary Vite process, loopback fixture process and fixture source were stopped and removed after observation.
- The evidence is intentionally not a replacement for real authenticated Mini App, Telegram, provider, PostgreSQL, staging or production acceptance.
- The later group-chat/customer indexed relationship remains deferred: this visual work adds no database model, endpoint, permission grant or cross-table navigation contract.
