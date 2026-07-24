# Stage09 工作台可靠性修复：生产发布与验收证据（2026-07-24）

## Status

- Status: `partial-production-accepted`
- Scope: Stage09 工作台可靠性修复包；不是 Stage07、Stage08 或整个产品的全量验收声明。
- Release: 后端 `stage09-p1-20260724-r28`；静态前端 `stage09-p1-20260724-r30`
- Deployment model: 原生 systemd、PostgreSQL 16 + pgvector、Redis、Nginx；未使用 Docker。
- Source branch: `codex/stage07-mini-app-ui`
- Source commits included: `263b533`、`8b8738d`、`8ba5af3`、`d80935a`、`b8be2f9`、`2879aca`、`cf4e542`、`021b124`、`79594a9`、`35462b5`。

## 已授权的生产数据修复

用户授权后，只对 Base `6a99b4be-10fc-43ee-86e2-315ab7fa350d` 中失败导入留下的目标表 `42a1cfbf-09ae-42d3-bb35-097fa8df89b4` 执行精确清理。

执行前复核：目标表有 `0` 条 record、`2` 个 field。随后在一个事务内删除该表及其两个 field；未删除 import job、Base 内其他表、记录或其他业务对象。执行后复核 table、field、record 均为 `0`。

## 发布输入与封存校验

| 项目 | 结果 |
| --- | --- |
| r27 源码候选 | 被 sealed release 校验拒绝，原因是归档误含历史运行时 `.env.stage07-acceptance.example`；从未激活。 |
| r28 源码包 SHA-256 | `d482a7136cef5c1b17e55a6be1b7b4ad9c1fe3388f794936a349e7f202502c09` |
| r28 静态包 SHA-256 | `a5f4063c05f650b8fc1df1431a1b7c01391295f380cb9c4a0bee5b19b4f2f04e` |
| r28 release manifest SHA-256 | `da7688ea7f1d9042f4292d0f371ed72b652b369af5b37d3269d2fc08eedd8dcf` |
| Candidate preflight | `release-layout`、`release-assets`、`native-service-assets`、`native-data-assets`、`release-manifest`、migration offline check 均通过。 |
| Alembic target | `20260723_0033` |

## 实际生产切换与回归

首次切换时，健康检查早于 Uvicorn 正常启动完成而触发自动回退；没有把未健康版本留在 current。随后把初始等待调整为 6 秒并追加 10 次健康重试，第二次原子切换成功。

最终服务器状态：

| 检查 | 结果 |
| --- | --- |
| `/opt/stage09-p1/current` | 指向 `stage09-p1-20260724-r28` |
| `/var/www/stage09-p1/current` | 指向 `stage09-p1-20260724-r28` |
| 静态 previous | 保留 `stage09-p1-20260724-r26` 作为回退点 |
| `stage09-p1-api`、`stage09-p1-worker`、`stage09-p1-outbox-bridge`、`stage09-p1-redis`、`nginx` | 均为 `active` |
| `stage09-p1-migrate` | 成功退出，`ExecMainStatus=0` |
| `127.0.0.1:18080/health` | HTTP 200 |
| `https://stage09.jiangtest1.online/health` | HTTP 200 |
| `https://stage07.jiangtest1.online/health` | HTTP 200 |
| r28 JS/CSS 静态资源 | 两域名均返回 HTTP 200 |
| `/browser-handoff.html` | `Cache-Control: no-store`、`Referrer-Policy: no-referrer` |

## 浏览器会话过期恢复：r29 静态前端发布

2026-07-24 19:28（Asia/Shanghai）受控统计确认：服务器中已有的浏览器会话均已超过既定的 8 小时 TTL；没有工作区、Base、记录或授权被删除。此前前端把会话过期与真正的授权拒绝显示为同一句“当前身份没有可访问的工作区”，导致用户无法判断恢复方式。

本次仅发布前端静态资源，未重启 API、worker、Redis 或 Nginx，未修改数据库和 browser handoff 的安全约定。发布前后校验如下：

| 检查 | 结果 |
| --- | --- |
| Commit | `79594a9 fix(workspace): explain expired browser sessions`，已推送到 `origin/codex/stage07-mini-app-ui` |
| RED | `browser-session-recovery.test.tsx` 在旧文案下失败，证明能复现问题 |
| 前端自动化 | `74 files / 306 passed` |
| 生产构建 | `tsc -b && vite build` 成功 |
| r29 静态包 SHA-256 | `c0ff7e45c995ac3bf2d8d0c53e152599da48d93f75c9643c109ffacbf9029b97` |
| r29 JavaScript SHA-256 | `44b627ca9af0f95d1d0b3d97c9bc64993cda7220a808ae44c322a6bc44890cba` |
| 远端静态目录 | `/var/www/stage09-p1/current` 原子切换到 `stage09-p1-20260724-r29`；`current.previous` 保留 r28 |
| 公网内容回读 | 首页与新 JavaScript 文件分别按 SHA-256 回读一致；`https://stage09.jiangtest1.online/health` 返回 HTTP 200 |

新的安全提示为“当前浏览器工作台会话已失效或无访问权限，请返回 Telegram 重新打开工作区。”它不暴露用户身份、ticket、cookie 或会话时间。用户从 Telegram 的“打开工作区”重新进入后，现有机制会创建新的单次 handoff 与新的 8 小时浏览器会话；该步骤仍然是用户主动登录，不是自动续会或绕过权限。

## 浏览器入口身份恢复：r30 静态前端发布

用户在 Telegram Mini App 内点击“在浏览器打开完整工作台”后，生产访问日志记录到三次 `POST /mini-app/browser-handoffs` 返回 HTTP 401。受控无身份探针返回同一安全代码 `stage06_verified_identity_required`，且 handoff/session 表计数没有新增，证明请求没有携带身份头；这不是浏览器窗口、Base 权限或 ticket 交换错误。

根因是前端曾只依赖模块级 `telegramInitData`。该内存值被生命周期清理后，页面仍持有当前 Mini App launch 的内存引用并可显示已加载的首页，但浏览器 handoff 请求失去了 `X-Telegram-Init-Data`，后端因而正确拒绝。

`35462b5 fix(mini-app): restore browser handoff identity` 的修复在每次 handoff 点击前，从当前 `TelegramMiniAppLaunch` 的内存引用恢复请求身份；原始 initData 不会进入 URL、localStorage、sessionStorage、日志或页面正文。没有调整 Telegram 校验时长、browser session TTL、cookie、数据表或权限模型。对不支持全屏的 Telegram host，界面不再显示不可用的全屏按钮。

| 检查 | 结果 |
| --- | --- |
| RED | `browser-handoff-recovery.test.tsx` 在模块级身份被清空时，旧代码断言收到 `null` 身份头而失败 |
| 前端完整回归 | `75 files / 308 passed` |
| 针对性前端回归 | `3 files / 40 passed` |
| 后端交接安全回归 | `16 passed`：`test_stage09_browser_handoffs.py`、`test_stage07_mini_app_api.py` |
| 生产构建 | `tsc -b && vite build` 成功 |
| r30 静态包 SHA-256 | `428a0f03a80eef2dbd208077a9843e3f01ab60a3dd61d5fc092a1e6912dedf86` |
| r30 JavaScript SHA-256 | `7187b3fb37f872931d06331bf33ced82ce802e3d3a19684765e3c9470e17b243` |
| 远端切换 | 静态 `current` 原子切换为 r30，`current.previous` 为 r29；后端服务保持 r28 且未重启 |
| 公网回读 | `stage07.jiangtest1.online`、`stage09.jiangtest1.online` 的 health 都为 HTTP 200，r30 JavaScript 哈希一致 |

仍需一次真实 Telegram 人工验收：从重新打开的 Mini App 点击浏览器入口，预期 `POST /mini-app/browser-handoffs` 从 HTTP 401 变为 HTTP 201，然后静态交接页完成 ticket exchange 并进入工作台。该证据在取得前不把浏览器 handoff 写成“端到端已验收”。

未改动 Docker、Stage03、80/443 的所有权、Nginx host 结构、Telegram webhook、BotFather 配置，也没有发送 Telegram 消息或调用真实 LLM。

发布后已经清理服务器上的 r27 无效候选静态目录和上传包；后端 release/venv 保持 r28，静态 current 为 r30、静态 previous 为 r29，r26 保留在历史发布目录；运行时备份与发布证据保留。桌面临时打包文件因本机文件删除策略被工具拦截，未以不安全方式绕过；它们不在 Git 工作区、不影响运行时或服务器版本。

## 自动化验证

在当前提交上实际运行：

```text
python -m pytest backend/tests/unit/test_stage06_template_import.py backend/tests/unit/test_stage06_template_import_api.py -q
18 passed in 7.18s

npm.cmd test -- --run
73 files / 305 passed

npm.cmd run build
success

git diff --check 33c8163..HEAD
success
```

变更已推送到远端分支 `codex/stage07-mini-app-ui`。工作区中 `.superpowers/sdd/` 与 `evidence/screenshots/` 的既有未提交用户文件未被纳入本次提交或覆盖。

## 真实浏览器验收边界

已实际验证未携带 Telegram 身份的公开 Stage09 页面会正确显示“无工作区访问权限”，不会伪造一个有权限的工作区。现有 Chrome 用户会话中可见历史 `https://stage07.jiangtest1.online/` “工作台”标签；尝试接管该标签时浏览器扩展控制超时并重置，因而没有执行任何有副作用的点击、导入或写入。

因此，下列事实已经成立：部署版本、域名、TLS 可达性、健康检查、静态资源和未认证拒绝分支已实际验证。下列事实尚不能宣称通过：携带真实 Telegram `initData` 的身份链路、Home/Bases/Home 与 Team Bot 返回的完整交互、导入向导的前端取消与 409 恢复、以及任何新建/导入写入。需要用户在 Telegram 中重新打开“打开工作区”或在浏览器交接页打开后，由已登录身份完成这一轮无写入点击验收；若涉及新建 Base 或提交导入，将在提交动作前再次征得确认。

## 未完成能力

生命周期能力仍不是本修复包的一部分：Base/Table/Field/View/Record 的复制、删除、归档、批量编辑、导出及恢复语义尚无对应的已验收 UI/API，不应显示为可用按钮。它们保留为后续阶段的有界扩展，而不是以假入口代替实现。
