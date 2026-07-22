# Stage09 P0：服务器只读盘点记录

## Status

- Result：`complete — read-only inventory with deployment gaps identified`
- Scope：只读 SSH、运行时、容器、磁盘、仓库与端口映射盘点；没有服务器写入、env 读取或业务操作。
- Date：2026-07-22

## 已执行的安全尝试

1. 首次按项目 SSH alias 连接时，本机默认 OpenSSH 没有加载项目专用 config，alias 仅在本地解析失败。
2. 显式加载项目 config 后，OpenSSH 在本地拒绝使用历史私钥：其 ACL 包含额外受限账户读取权限，因而被判为权限过宽。认证请求没有发起。
3. 尝试已有 Stage07 专用私钥作为只读替代；其本地权限正常，但服务器拒绝 public key。没有成功登录。

前三次尝试均未建立远端 shell；随后用户通过其已认证终端为 Stage07 专用公钥授权 `ubuntu`，第四次尝试成功。整个 P0 没有读取服务器 env、日志、数据库业务内容、webhook 配置或任何密钥；没有服务器写入、部署、Telegram 或 Provider 调用。

## 成功的 P0 盘点结果

| 项目 | 只读结果 |
| --- | --- |
| 登录身份 | `ubuntu`，可通过 `sudo -n` 执行只读 Docker 查询 |
| OS/runtime | Linux 6.8；Docker 29.6.1；Docker Compose 5.3.0 |
| 磁盘 `/` | 59G 总量、约 45G 可用（21% 已用） |
| 远端仓库 | `/home/ubuntu/telegram-bitable-work-agent` 存在、工作树 clean、head `fa645d9` |
| 运行服务 | 历史 Stage03 API、worker、outbox bridge、Caddy、Redis、PostgreSQL/pgvector 均运行；Redis/PostgreSQL healthcheck healthy |
| API container | running，无 Docker healthcheck；无宿主机端口映射 |
| 对外入口 | 仅 Caddy 映射 80/443；API 是内部网络服务 |
| Docker 存储 | images 约 1.9GB、volumes 约 67MB、build cache 约 2.9GB |
| 现网 Alembic head | `20260707_0016`；属于历史 Stage03，不能作为 Stage08/Stage09 migration 基线 |
| 现网 `vector` extension | `false`；容器镜像具备 pgvector，但现网 Stage03 数据库未启用扩展 |
| Redis / Caddy | `PONG`；现网 Caddyfile 校验通过 |
| Stage07/Stage09 隔离资产 | 远端历史仓库中均不存在；独立运行目录、runtime env 和 Compose 项目尚未创建 |

## P0 结论

服务器具备 Docker、Compose、Redis 与 pgvector 基础条件，但远端仓库仍是历史 Stage03 commit，当前容器也均属于该旧 Compose 项目。**不得原地覆盖或替换现有 Stage03 服务。** P1 必须使用平行、隔离的 Stage09 Compose 项目、独立 runtime directory/volumes、明确 Caddy host 路由和可回滚 image。不得把现网 `20260707_0016` 或未启用 `vector` 的 Stage03 PostgreSQL 当作 Stage08/Stage09 的迁移或检索库；P1 需从新卷的空数据库创建 extension 并迁移到固定 Stage08 head。

## 恢复条件

P0 已恢复并完成。进入 P1 前仍需要：

1. 固定部署版本/commit 与并行隔离目录；
2. 独立 server-side runtime env 的 key-presence checklist、备份与 rollback 点；
3. 可用的独立 HTTPS hostname/Caddy 路由，不能复用或覆盖 Stage03；
4. Stage07 Browser/UI 验收与 P1 变更窗口的明确执行记录。

在这些条件具备前，不部署、不迁移、不改 webhook、不发送 Telegram。

## P0a：原生部署前复核（2026-07-22，read-only）

这次复核遵循用户确认的原生部署决定，只读取软件可用性、端口占用、磁盘和
非交互 sudo 能力；不读取 env、业务数据、日志或密钥，也没有服务器写入。

| 项目 | 结果 |
| --- | --- |
| 系统与权限 | Ubuntu 24.04；`sudo -n` 可用；根盘约 44 GiB 可用 |
| 原生前置 | Python、Nginx、systemd、`ss` 存在；Nginx 当前未启用、未运行 |
| 需安装组件 | PostgreSQL 16、`postgresql-16-pgvector`、Redis Server 当前均未安装；APT 候选包可用 |
| 80/443 | 两端口仍被 `docker-proxy` 占用 |
| 历史入口复核 | Docker CLI 可用，但当前运行与全部容器计数均为 0；这与早期 P0 的历史 Caddy 容器证据不一致，不能假定现有 Caddy 可用于新 hostname |

### P0a 结论

原生 PostgreSQL + pgvector、Redis、systemd 服务可以在隔离目录中开始部署；
但新 HTTPS 入口仍被两个条件阻塞：80/443 的残留 `docker-proxy` 占用需要由
历史入口所有者处置，且必须提供独立 hostname。P1 可以先保持 API loopback、
Redis Unix socket 和 PostgreSQL 本地连接，不触碰这两个遗留端口或 Stage03/Docker。
