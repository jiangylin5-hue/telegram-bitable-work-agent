# Stage09 工作台可靠性修复：生产发布与验收证据（2026-07-24）

## Status

- Status: `partial-production-accepted`
- Scope: Stage09 工作台可靠性修复包；不是 Stage07、Stage08 或整个产品的全量验收声明。
- Release: `stage09-p1-20260724-r28`
- Deployment model: 原生 systemd、PostgreSQL 16 + pgvector、Redis、Nginx；未使用 Docker。
- Source branch: `codex/stage07-mini-app-ui`
- Source commits included: `263b533`、`8b8738d`、`8ba5af3`、`d80935a`、`b8be2f9`、`2879aca`、`cf4e542`、`021b124`。

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

未改动 Docker、Stage03、80/443 的所有权、Nginx host 结构、Telegram webhook、BotFather 配置，也没有发送 Telegram 消息或调用真实 LLM。

发布后已经清理服务器上的 r27 无效候选静态目录和上传包；r28 当前 release/venv/static、r26 静态回退点、运行时备份与发布证据保留。桌面临时打包文件因本机文件删除策略被工具拦截，未以不安全方式绕过；它们不在 Git 工作区、不影响运行时或服务器版本。

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
