# Stage09 r34 语义导入部署证据（2026-07-24）

## Scope

- Artifact: `stage09-p1-20260724-r34`
- Source commit: `41b56e4 feat(import): preserve semantic business fields`
- Scope: 将已存在的后端字段能力接入真实 CSV/XLSX 导入 UI；不迁移 schema、不改权限、不读取或改写既有客户数据。

## Delivered behavior

- `状态` / `status` / `stage` / `progress` 等常见业务列由服务端推断为 `status`。
- `优先级` / `priority`、类型、分类、来源、渠道等常见业务列由服务端推断为 `single_select`。
- Mini App 的字段映射选择器现在允许：文本、数字、日期、复选框、状态、单选、多选、链接、邮箱、电话。
- `linked_record`、`lookup`、`formula` 仍不从文件头猜测；它们必须在已存在的 Base schema 中显式配置。
- 固定验收 fixture：`stage09-ui-acceptance-sample.csv`。它仅用于新建独立 `Stage09 UI 验收样例` Base。

## Local verification

| Check | Evidence |
| --- | --- |
| Backend import/service and API regression | `pytest backend/tests/unit/test_stage06_template_import.py backend/tests/unit/test_stage06_template_import_api.py -q` → `20 passed` |
| Mini App import/API/grid regression | `npm.cmd test -- --run src/test/import-wizard.test.tsx src/test/api.test.ts src/test/view-renderers.test.tsx` → `3 files / 31 tests passed` |
| Production bundle | `npm.cmd run build` passed; JS asset `index-DCOm3ANM.js` |
| Release preflight | `release-layout: pass`、`release-assets: pass`、offline migration `20260723_0033` pass、manifest `a03fe814390cfb3dea3aaa7188be4386a31d8fd6d7ed46a0f624be1ef9a13dfc` |

## Native deployment observation

- r34 source, virtualenv and static symlinks were atomically switched to `stage09-p1-20260724-r34`.
- API、worker、outbox bridge、Redis、Nginx were observed `active`.
- Loopback `/health`、public HTTPS `/health` and public root were each `200`; HTTP root was `308`.
- Initial readiness command was intentionally treated as failed because the ACME probe path had no file (`404`). A non-sensitive, fixed read-only probe was then installed at `/.well-known/acme-challenge/stage09-readiness` and returned `200`.
- A second failure was investigated rather than ignored: `sudo -u stage09-p1` clears the two readiness environment variables and cannot see listener owners through `ss -ltnp`. The sealed readiness verifier therefore has to run as root with the two environment values injected **after** `sudo`. That invocation returned `readiness-gate: pass`.

## Real browser/Telegram acceptance status

- A fresh authorized Chrome page loaded the actual Home data after r34 (`GET /mini-app/bootstrap` and authorized workspace Home both returned `200`).
- The browser-control bridge timed out immediately after attempting the actual `从 Excel/CSV 导入` button, and server logs showed no `POST /imports`; therefore no fixture was uploaded and no Base/record was created. This is recorded as an automation-bridge limitation, not as a claimed product import failure or success.
- Remaining required evidence: real authorized UI upload → preview mapping shows `状态` / `单选` → commit the separate acceptance Base → open its grid and confirm colored tags.
