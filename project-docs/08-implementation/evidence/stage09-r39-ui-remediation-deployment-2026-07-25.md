# Stage09 r39 UI 功能修复原生部署证据（2026-07-25）

## Scope

- Artifact: `stage09-p1-20260725-r39`
- Source revision: `4f9096a`（包含已推送的 UI 功能修复与部署前文档）
- Purpose: 发布 Stage09 UI 功能完整性修复；不变更 Telegram webhook、BotFather、Stage03 Docker、80/443 所有权、数据库结构或既有业务记录。
- Deployment model: 原生 PostgreSQL / Redis / systemd / Nginx；不使用 Docker。

## 发布前验证

| Check | Result |
| --- | --- |
| 后端导入边界 | `40 passed in 9.88s` |
| Mini App 串行隔离回归 | `76 files / 353 tests passed in 228.18s` |
| Mini App production build | passed |
| `git diff --check 07af702..HEAD` | passed |
| GitHub branch | `codex/stage07-mini-app-ui` 已推送到 `4f9096a` |
| Sealed source archive SHA-256 | `57721d8b2c488a3b58f481734003a03095a548dab1710169640c205c3b403add` |
| Static archive SHA-256 | `c9a1624d5339646aa9902814c7ca4dfc1cada03a8efa6dac6813582fce433084` |

源码包仅来自已提交的 `backend`、`mini-app` 与 `deploy/stage09-native` 路径；`mini-app/dist/browser-handoff.html` 单独加入 sealed source，以满足 release layout 约束。静态包仅来自已成功构建的 `mini-app/dist`。上传后在服务器重新校验两份 SHA-256。

## 服务器密封预检

| Check | Result |
| --- | --- |
| Sealed release layout | pass |
| Release assets | pass |
| Native service assets | pass |
| Native data assets | pass |
| Runtime contract | pass |
| Deterministic release manifest | pass，SHA-256 `4ddc354e08cfc449f1240042c5d54ef8a9e6d55e2bb799f418990ab68c0b6ff7` |
| Fixed Alembic offline migration (`20260723_0033`) | pass |

新 venv 从已验证的 r37 运行时依赖副本创建；systemd 的 `WorkingDirectory` 与离线迁移的 `PYTHONPATH` 均指向 r39 release 中的 `backend`，因此实际运行代码来自新 release，而非旧版本 site-packages。

## 切换与回退处理

首次候选切换在启动前置隔离校验处失败。原因是发布过程把 `/etc/stage09-p1/runtime.env` 设成 `0600`，而 `stage09-p1` 服务账号需要读取该文件来执行隔离校验；这不是 UI 代码或数据库迁移失败。

失败后，自动回退将 source、venv、static 三个 `current` 指针还原到 r37。随后将运行时文件固定为 `root:stage09-p1`、权限 `0640`，确认服务账号可通过 `verify-native-isolation.sh`，并重新执行完整密封预检和原子切换。最终 r39 成功激活；r37 作为 `current.previous` 保留。

## 最终运行时验收

| Item | Result |
| --- | --- |
| Source / venv / static current | 全部指向 `stage09-p1-20260725-r39` |
| Runtime file owner/mode | `root:stage09-p1` / `0640` |
| API / worker / outbox / Redis / Nginx | 全部 `active` |
| API loopback `/health` | HTTP 200 |
| Public `https://stage07.jiangtest1.online/health` | HTTP 200 |
| Public `https://stage07.jiangtest1.online/` | HTTP 200 |
| Sealed readiness gate | pass |

上传临时目录已在成功切换后清理。未发送 Telegram 消息，未执行真实业务记录导入/创建，未读取既有业务记录，也未运行真实浏览器点击验收。

## Remaining Evidence

本次证明“修复代码已被部署、服务与公网入口可用”，但不替代人工产品验收。仍需在用户已授权的真实浏览器会话中执行：打开工作台、进入 Base、试用右键/更多菜单、选取非敏感 CSV/XLSX 并完成 Preview → Commit → 打开新 Base 的闭环；该操作会产生新的业务对象，需另行记录实际写入证据。
