# Stage09：历史 Stage03 Docker 下线与原生公网入口设计

## Status

- Document status: approved design
- Approved at: 2026-07-23
- Scope: 将服务器上遗留的 `telegram-bitable-stage03` Docker 栈下线；由现有原生 Stage09 服务接管唯一仍需保留的 Mini App 公网入口。
- Current Progress: 已完成只读盘点和仓库内下线脚本安全修复；repository-only fake Docker/pg_restore 与完整 Stage09 shell suite 已通过。尚未 SSH、停止容器、变更 Nginx、申请新证书或删除任何真实数据。

## 1. 背景与已验证事实

当前 Stage09 不是 Docker 部署：应用以 `stage09-p1-api`、`stage09-p1-worker`、`stage09-p1-outbox-bridge` 和 `stage09-p1-redis` 四个原生 systemd 服务运行；PostgreSQL 只监听 `127.0.0.1:5432`，`stage09_p1` 数据库已启用 `vector` 扩展，Redis 使用 `/run/stage09-p1/redis.sock`。2026-07-23 的回环和公网 `stage07.jiangtest1.online` health 均返回 HTTP 200。

服务器仍运行完整历史 Stage03 Docker 栈：旧 API、worker、outbox bridge、PostgreSQL、Redis 和 Caddy。它们不再是 Stage09 的依赖，但 Caddy 仍占用公网 `80/443`，并在运行时把 `stage07.jiangtest1.online` 转发给原生 Stage09。

另发现一项必须消除的配置漂移：容器内落盘 Caddyfile 仍含 `stage07-web:80` 和 `stage07-api:8000` 的过期上游，而当前公网 200 依赖 Caddy 的运行时配置。这意味着一旦旧 Caddy 重启，入口可能恢复为 502。下线 Docker 并以单一原生 Nginx 配置接管入口可消除该风险。

## 2. 目标、边界与非目标

### 目标

1. 保持 `https://stage07.jiangtest1.online` 作为 Telegram Mini App 的兼容地址，静态页面和 API 均由 Stage09 原生服务提供。
2. 将 HTTPS、静态站点和反向代理固化为原生 Nginx 配置；不再依赖 Docker Caddy 的运行时内存配置。
3. 对历史 Stage03 PostgreSQL、Redis、compose/Caddy 配置和 Caddy 运行时 JSON 做 root-only 归档、校验并记录 manifest。
4. 在原生入口真实通过后，删除历史 Stage03 容器、镜像、网络与数据卷。
5. 清理未引用的 Stage09 release/venv/static 目录，只保留当前 `r22` 和已验证的前一回滚版本 `r19`。

### 强制边界

- PostgreSQL 和 Redis 继续只对本机开放；本任务不得打开 5432、6379 或 Redis Unix socket 的公网访问。
- 不读取、打印、提交或传输 runtime env、Bot token、数据库密码、业务行、Telegram 原文或归档内容。
- 仓库内的 `deploy/stage03/`、Stage03 文档和历史 Git 提交保留为历史证据；删除范围仅限目标服务器上已归档的运行时 Docker 资源。
- 不变更 Stage09 的数据库 schema、权限模型、业务 API 或 Telegram 业务逻辑。

## 3. 方案选择

| 方案 | 结论 | 原因 |
| --- | --- | --- |
| 保留 Docker Caddy，仅删除旧 PostgreSQL/Redis | 不采用 | 80/443 和运行时配置漂移仍依赖 Docker，不能满足原生服务器部署目标。 |
| 原生 Caddy 接管 80/443 | 不采用 | 虽可自动管理证书，但会引入第二套反向代理配置；现有原生 Nginx 已服务静态文件和 API。 |
| 原生 Nginx + Let’s Encrypt/Certbot 接管 80/443 | 采用 | 复用现有 Nginx，配置和证书续期可由 systemd 管理，入口边界最小且不再依赖 Docker。 |

## 4. 目标架构

```text
Internet
  -> stage07.jiangtest1.online:443
  -> native Nginx (TLS, static Mini App, /api proxy)
  -> 127.0.0.1:18080 native Uvicorn API
  -> native PostgreSQL + pgvector (127.0.0.1 only)
  -> native Redis (/run/stage09-p1/redis.sock only)

Telegram Mini App button -> same HTTPS origin
```

Nginx 只为确切 hostname 提供服务：

- `:80` 仅提供 ACME challenge，并把其余请求重定向到 HTTPS；
- `:443 ssl http2` 提供 `/`、`/index.html`、`/assets/` 静态文件，其他路径反向代理到 `127.0.0.1:18080`；
- 显式传递 `Host`、`X-Real-IP`、`X-Forwarded-For` 与 `X-Forwarded-Proto=https`；
- 证书目录由 root 管理，Nginx 仅读取证书；certbot systemd timer 负责续期并在成功后 reload Nginx。

## 5. 可恢复下线流程

### 5.1 前置检查

1. 确认当前 `r22` source、venv 和 static symlink 均一致，四个 Stage09 服务 active，`/health` 回环与公网均为 200。
2. 确认 DNS 仍将 hostname 指向当前服务器，安全组允许 80/443，且磁盘空间足以容纳归档和两个 release。
3. 验证 Nginx candidate 配置和 Certbot 可用性；候选配置在切换前必须先通过 `nginx -t`。
4. 对正在运行的 Caddy Admin API 只读导出 runtime JSON，作为精确 rollback 证据；不得把它作为新入口配置。

### 5.2 归档

归档存放在 root-only 目录 `/var/backups/stage09-p1/legacy-stage03/<UTC>/`，目录 `0700`、文件 `0600`。内容为：

- compose 文件和 Caddyfile 的副本；
- Caddy runtime JSON；
- 旧 PostgreSQL 的一致性逻辑 dump；
- Redis RDB snapshot；
- 容器、镜像、网络、volume 名称与 SHA-256 manifest（只记录名称、大小、摘要和时间，不记录数据正文）；
- 原生 Nginx 旧配置备份和当前 Stage09 symlink 目标。

归档成功条件：每项存在、非空、其 SHA-256 位于 manifest；PostgreSQL dump 可列出目录、Redis RDB 可通过本地工具读取 header。归档失败时不停止任何 Docker 容器。

归档必须在旧 Caddy 仍运行时完成。全部 artifact 和校验通过后，先原子发布归档目录，再原子写入唯一 ready marker；未写入 marker、存在多个候选 marker、artifact 不完整或校验失败时，该归档不得进入删除阶段。后续 `retire` 只读取并重新严格验证这个既有 ready archive，不重新调用容器生成归档，也不依赖已停止的 Caddy。

### 5.3 入口切换与证书

1. 生成 HTTP-only Nginx candidate，并保存当前 `/etc/nginx/sites-available/stage09-p1.conf` 备份。
2. 停止旧 Caddy 容器以释放 80/443；旧 API、worker、outbox、PostgreSQL、Redis 暂不删除，保留为短时回滚资源。
3. 启用 HTTP-only Nginx，使用 ACME webroot 为 hostname 申请或续期证书；若证书获取失败，立即恢复 Caddy runtime JSON 和容器，停止原生公网 server block。
4. 启用最终 TLS Nginx 配置并 reload；以服务器回环、外部 HTTPS `/health`、首页及一个静态 asset 实测 HTTP 200。
5. 由用户重新打开 Telegram Mini App，确认工作区可见、页面可操作。该人工 UI 证据是入口切换后的最终验收，不以服务 health 替代。

### 5.4 删除与 release 回收

只有第 5.3 的自动检查和 Telegram 人工检查均成功后才执行：

1. 停止并删除所有 `telegram-bitable-stage03-*` 容器；
2. 删除其专属 network、image 与 volume；
3. 保留 Docker daemon 本身，不影响服务器其他可能的 Docker 用户；
4. 删除未被 `current`、`current-venv`、`current.previous` 或 systemd 引用的 Stage09 source/venv/static release，只保留 `stage09-p1-20260723-r22` 与 `stage09-p1-20260723-r19`；
5. 写入脱敏操作 receipt：仅记录 ready manifest 状态、各类资源实际完成的删除计数和删除前 custom image 字节数 `custom_image_bytes_before`；不得把删除前镜像大小误称为已释放字节数。若部分删除失败，receipt 为 `status=partial` 并以非零状态退出。

## 6. 回滚

在 Docker 资源删除前，若任何 HTTP、HTTPS、Nginx、证书或 Telegram 验收失败：

1. 恢复 Nginx 配置备份并 reload；
2. 停止 native 80/443 server block；
3. 启动 Caddy 容器并将归档的 Caddy runtime JSON load 到 Admin API；
4. 对原入口的 `/health` 与首页实际验证；
5. 旧 Stage03 容器、卷和镜像继续保留，标记迁移失败，不执行删除。

容器与数据卷删除后，回滚改为从 root-only 归档恢复到隔离临时 Docker project；不得覆盖 Stage09 原生 PostgreSQL、Redis、release 或 runtime env。

## 7. 验收标准

| 类别 | 必须证据 |
| --- | --- |
| 原生数据面 | PostgreSQL 仅本机监听、`vector` extension 存在、Redis socket 存在，Stage09 services active。 |
| 原生入口 | Nginx `-t` 成功；80 仅重定向/ACME；443 使用有效证书；公网 `/health`、首页、静态 asset 均为 200。 |
| Telegram | 用户以真实 Bot 按钮重新打开 Mini App，看到可访问工作区并能操作关系索引页面。 |
| 清理 | Stage03 容器、镜像、network、volume 均为 0；根归档与 manifest 存在；未引用 Stage09 artifact 已删除，r22/r19 仍在。 |
| 回归 | API、worker、outbox、Redis、Nginx 均 active；journal 最近窗口无 warning/error；不公开数据库或 Redis 端口。 |

## 8. 已知风险

- TLS 签发依赖公网 DNS 与 ACME；失败时按本设计恢复旧入口，不删除 Docker。
- Telegram Desktop 的 Mini App 宽度仍由 Telegram 客户端控制；`WebApp.expand()` 只能请求最大可用高度，不能强制桌面端侧栏宽度。
- 归档包含历史业务数据，因此必须保留在服务器 root-only 目录，不上传 Git、聊天或第三方存储。
