# Stage09 P1：原生服务器回环部署证据

## Status

- Current Progress Update (2026-07-23, server local time): 已从已推送提交 `bddf4e6` 封存并激活 `stage09-p1-20260722-r4`。固定 revision `20260720_0032` 的离线 SQL 与实际 `stage09-p1-migrate.service` 均成功；Redis、API、worker、outbox bridge、Nginx 均为 `active`，并以独立脚本实测 `127.0.0.1:18080/health`、`127.0.0.1:18090/health` 和 Nginx 静态根路径。Nginx 只监听 `127.0.0.1:18090`，不绑定 80/443；按用户授权仅移除了 `last30days-api` 的 enabled 链接，未修改其源配置、Docker、Stage03、Caddy、Telegram 或 Provider。未激活的 r3 release/venv/static 与临时上传包已清理。

- Result：`complete — native loopback deployment`
- Date：2026-07-22
- Artifact：`stage09-p1-20260722-r2`
- Fixed Alembic revision：`20260720_0032`
- Scope：原生 PostgreSQL + pgvector、原生 Redis、受限 systemd 应用服务与回环 API；不包含公网 HTTPS ingress。

## 已完成的真实服务器写入

1. 已安装服务器原生 PostgreSQL 16、匹配的 pgvector、Redis、Python venv 与运行依赖；未创建、重启、替换或读取 Stage03 Docker 应用资产。
2. 已创建独立 `stage09_p1` 数据库与运行角色，并在该新库启用 `vector`；真实迁移固定执行到 `20260720_0032`，`alembic_version` 已核验为该 revision。
3. 已创建隔离运行账号、受保护的 runtime env、独立 Redis Unix socket 与不可变 r1/r2 release；r2 在服务器端完成 release-layout 与 manifest 校验。
4. r2 的离线 SQL 先于真实迁移成功生成；随后由 `stage09-p1-migrate.service` 真实迁移成功。
5. `stage09-p1-redis.service`、`stage09-p1-api.service`、`stage09-p1-worker.service`、`stage09-p1-outbox-bridge.service` 均已启用并为 `active`；应用账号经 Unix socket `PING` 成功，`http://127.0.0.1:18080/health` 返回 `{"status":"ok"}`。

## 运行边界

- `TELEGRAM_SEND_MODE=dry_run`、空 allowlist、`LLM_ENABLED=false`、`AGENT_WORKFLOW_MODE=fake`、`PROVIDER_MODE=disabled` 继续有效。
- 未调用 Telegram、OpenRouter/Provider、webhook、业务写入或 draft 确认。
- 未修改 Docker、Stage03 容器、80/443、Nginx、Caddy 或历史 hostname。

## 已处理的发布问题

| 问题 | 原因 | 处理 |
| --- | --- | --- |
| r1 离线迁移校验失败 | 正常 venv Python 软链接被错误地作为逃逸路径执行 | r2 仅以解析路径做 allowlist 校验，仍以 venv 入口执行；独立复核通过。 |
| r2 venv 安装失败 | sealed release 不允许构建元数据写入 | 在受限账号拥有的临时构建目录复制 backend 后安装，完成即清理。 |
| migrate unit `203/EXEC` | 发布权限收紧时将 systemd `ExecStartPre` 脚本一并去除执行位 | 仅恢复 release 内部署脚本的 group execute；迁移随后成功。 |

## 剩余阻塞与下一步

1. 公网 HTTPS 仍未部署：遗留 `docker-proxy` 占用 80/443，且尚未提供 Stage09 专属 hostname/DNS。该项必须由遗留 ingress 所有者处理；本轮没有触碰 Docker。
2. Redis 当前健康可用且 Unix socket `PONG`，但其 `Type=simple` 和 `--supervised systemd` 产生无害 supervision 日志；后续 P1 hardening 应统一为匹配的 systemd 模式。
3. 完成独立 hostname、受控 Nginx/Caddy route 和公网验证后，才可标记 Stage09 P1 的 HTTPS ingress 完成。
