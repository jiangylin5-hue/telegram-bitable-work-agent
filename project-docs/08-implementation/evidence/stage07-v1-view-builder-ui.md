# Stage07 V1 Saved View Builder Browser Evidence

## Status

- Evidence status: partial local Browser acceptance; it does not accept V1 or Stage07 as a whole
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

## Deliberately Unaccepted Browser Cases

The following required V1 checks were **not** re-run as Browser actions in this evidence session and therefore remain automated/contract evidence only:

1. switching the rendered client between owner, editor and viewer identities, including Base/Table/Field intersection and denial screens;
2. thirteenth-filter, unsupported-operator, relation/lookup-group and stale-version interactions in the rendered Browser;
3. F2 relation candidate, numeric lookup and Record Detail relation-edit regressions inside the V1 fixture;
4. direct Browser network payload inspection against a real backend service;
5. Escape-key/live-region coverage beyond the observed focus return.

Those gaps keep V1-A02, V1-A03, V1-A05, V1-A07, V1-A08 and V1-A10 at `partial-local`. They do not invalidate the focused API, PostgreSQL or client automated results recorded in the companion verification evidence.

## Cleanup

- Stopped the local fixture process; port `4174` had no listening socket in the post-run check.
- Deleted the fixture script and temporary `.out.log` / `.err.log` files.
- No screenshots, test records, secrets, external writes or running Browser session were retained.
