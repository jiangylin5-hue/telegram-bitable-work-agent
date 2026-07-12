# Stage07 V1 Saved View Builder Browser Evidence

## Status

- Evidence status: expanded partial local Browser acceptance; it does not accept V1 or Stage07 as a whole
- Date: 2026-07-12
- Scope: approved V1 saved-view UI only
- Environment: disposable local fixture serving the built Mini App at `127.0.0.1:4174`; fixed safe fixture responses only
- Exclusions: no Telegram identity, real backend service, real user/member data, staging, production, public sharing, import/template, delete/default reassignment or Bot path

## Fixture And Safety Boundary

The temporary `mini-app/scripts/stage07-v1-browser-fixture.mjs` served the built client and only the small, allowlisted safe response shapes needed by the V1 client. It did not connect to PostgreSQL, use credentials, proxy a backend, expose raw `config`/`permission_policy`, hidden fields, or real member information. The fixture was used only to exercise the actual rendered client and its typed local transport boundary.

The fixture was modified once to return a deliberately unsafe-detail-bearing `409` for the view name `Conflict browser view`; the canonical reread then returned `Canonical browser view`. This is a redaction test of the rendered client, not a claim that the fixture is an authorization server.

## Executed Matrix

| Viewport | Executed user-visible flow | Observation | Result |
| --- | --- | --- | --- |
| 1440 x 900 | Created private Grid `Grid browser view`; configured one `Status` filter, one sort and one `Status` group; opened owner access panel and granted `Fixture editor -> editor`. | Canvas selected the new tab and displayed the server-authored summary `服务端已应用 1 条筛选、1 条排序、按 Status 分组`; no client-side predicate/sort control was presented as authoritative. | observed |
| 1280 x 800 | Created private Kanban. | Safe `Status` grouping produced visible `todo` and `doing` columns with returned records. | observed |
| 430 x 844 | Reached `新建视图`, created private Calendar and opened the access sheet. | `新建视图` remained reachable; Canvas showed `服务端已应用 日期：Due date`; the date renderer and mobile access controls/sticky footer were visible. | observed |
| 390 x 844 | Reached `新建视图`, created private Form, then closed the Builder. | The safe Form fields rendered; focus returned to the originating `BUTTON` whose text was `新建视图`. | observed |
| 390 x 844 | Attempted to save `Conflict browser view` and received fixture `409` with unsafe server detail. | Selected tab and input became `Canonical browser view`; local alert was exactly `视图已被更新，请重新加载后再试。`; the unsafe fixture detail was absent from the DOM snapshot. | observed |

## Console And Visual Inspection

- Browser console query for `error`, `warn` and `warning` returned `[]` after the completed matrix.
- The 1440px Grid and 430px access-sheet renders were visually inspected in the in-app Browser. No persistent screenshot artifact was retained: the Browser output was inspected in-session and the temporary fixture was deleted.
- The in-app Browser session was finalized after evidence capture. No further Browser actions were issued in that session.

## V1-13: Role And Negative Browser Follow-up

A second disposable fixture ran on `127.0.0.1:4175`. It served the already built Mini App, used a server-set fixture role cookie only to select **owner**, **editor** or **viewer** responses, and returned the same safe typed shapes used by the client. It did not inspect browser cookies, call a real backend, connect to PostgreSQL or expose a real member identity.

| Actor / flow | Actual Browser observation | Boundary proved locally |
| --- | --- | --- |
| owner | `配置视图` and `新建视图` were visible. In the Builder, `添加筛选条件` was disabled at 12 conditions, `添加排序` was disabled at 3 rules, the group selector contained only `不分组` and `Status`, and only the owner saw `管理访问权限`. | The rendered UI enforces the approved bounded controls and does not offer relation/lookup grouping. |
| owner / F2 relation filter | Changing filter 1 to `Linked record` rendered the existing F2 `Relation picker`; it displayed `Permitted linked record` and no opaque target ID `r2` appeared in the DOM. | The Builder reuses the safe candidate label projection rather than exposing raw target state. |
| editor | The editor could open Builder and save `Editor saved view`; `管理访问权限` had count 0 while `保存视图` was enabled. | Editor presentation mutation is usable, but owner-only member administration is absent from actual UI. |
| viewer | The viewer saw the restricted saved-view tab and visible safe record, but `配置视图` and `新建视图` both had count 0. | A read-only grant does not surface configuration or creation controls. |
| editor / stale save | Saving `Trigger stale conflict` received fixture `409`; the visible alert was exactly `视图已被更新，请重新加载后再试。`, Builder name reread as `Editor saved view`, and `fixture-only raw detail` was absent from the DOM. | Conflict feedback is fixed-text and canonical-reread; raw server detail is not rendered. |

- Page-level console query for `error`, `warn` and `warning` returned `[]` after the follow-up. A browser-bridge telemetry timeout appeared outside the page console and is not recorded as an application warning/error.
- DOM snapshots and actual click/fill/select interactions were used for the visual/interaction review. `Page.captureScreenshot` timed out in the Browser bridge, so no screenshot is retained and no screenshot claim is made.

## Deliberately Unaccepted Browser Cases

The following required V1 checks were **not** re-run as Browser actions in this evidence session and therefore remain automated/contract evidence only:

1. a real backend Browser request/response trace, or a real underlying Base/Table/Field denial screen after a valid grant;
2. a server-produced unsupported-operator payload, numeric lookup filter mutation and Record Detail relation-edit regression in this V1 fixture;
3. every Kanban/Calendar/Form invalid configuration state at Browser level;
4. Escape-key/live-region coverage beyond the observed focus return.

Those gaps keep V1-A02, V1-A05, V1-A07, V1-A08 and V1-A10 at `partial-local`. V1-A03 now has local service/API, component and actual role-UI evidence. They do not invalidate the focused API, PostgreSQL or client automated results recorded in the companion verification evidence.

## Cleanup

- Stopped both local fixture processes; ports `4174` and `4175` had no listening socket in their post-run checks.
- Deleted both fixture scripts and all temporary `.out.log` / `.err.log` files.
- No screenshots, test records, secrets, external writes or running Browser session were retained.
