# Stage09 原生公网入口切换与 r22 紧急恢复证据

## Status

- Status: `native-https-recovered-r22-active`
- Date: `2026-07-23`
- Active release: `stage09-p1-20260723-r22`
- Candidate release: `stage09-p1-20260723-r23`，仍未激活。
- Scope: 归档历史入口运行时；将一个既有公网 hostname 的 HTTP/HTTPS 入口切至原生 Nginx；为该 hostname 获取真实 ACME 证书；恢复 r22 的公开访问。
- Out of scope and not performed: r23 三个 `current` symlink 切换、历史 Docker 资源 retirement、任何容器/卷/镜像/release 删除、发布文件清理、数据库或 Redis 写入、Telegram/LLM/Provider 调用。

本文只保存阶段、聚合计数、布尔结果和 HTTP 状态码；不保存 hostname、服务器地址、绝对路径、内部端口、环境变量、证书内容、旧入口资源名、业务记录或消息内容。

## 1. 入口归档与回滚可用性

| Check | Result |
| --- | --- |
| 归档前 r22 三个 `current` target | `true` |
| 原生 API/worker/outbox/Redis/Nginx 服务 | `active` |
| 回环 health | `200` |
| 公网 HTTPS health（归档前） | `200` |
| 历史入口实例运行 | `true` |
| root-only archive | `ready` |
| archived container count | `6` |
| archived network count | `1` |
| archived volume count | `4` |
| archived custom image count | `4` |
| archived custom image bytes before | `0` |
| archive manifest、PostgreSQL dump、Redis RDB 非空 | `true` |
| archive owner/mode 校验 | `true` |

归档之后，先以归档内的 runtime JSON 对仍运行的历史入口做同配置回载。第一次回载因缺少 JSON 内容类型而收到 `400`，未改变路由；补齐正确内容类型后，回载成功，实例仍运行且公网 HTTPS health 为 `200`。这证明 archive runtime JSON 是可被该入口 Admin API 接受的恢复输入。

## 2. 初次切换失败与失效回退的真实记录

初次写入 HTTP-only 原生 Nginx 配置后，`nginx -t` 成功。停止历史入口并尝试原生 HTTP 接管时，ACME probe 被以仅 root 可读权限创建；Nginx worker 无法读取该 probe，外部 ACME 路径返回 `403`。该失败发生在签发证书和 r23 激活之前。

自动回退已先恢复原 Nginx 配置，但历史入口实例在重新启动后进入 `restarting`。只读日志分类结果为：未命中端口占用、文件系统权限或 Caddyfile 解析错误；命中证书签发和上游网络错误。其短暂存活窗口不足以再次装载 archive runtime JSON，因此该入口不能作为可靠的即时回退路径。此处没有删除、重建或替换历史入口资源。

## 3. 紧急原生 HTTPS 恢复

在用户授权下，恢复策略改为保持 r22 不变，并由原生 Nginx 接管 HTTP/TLS：

| Check | Result |
| --- | --- |
| 历史入口实例保持停止 | `true` |
| HTTP renderer config syntax | `true` |
| 原生 Nginx HTTP listener | `true` |
| 外部 HTTP root redirect | `308` |
| 将固定、非敏感 ACME probe 调整为 worker 可读后，外部 ACME path | `200` |
| Certbot webroot 真实证书签发 | `true` |
| HTTPS renderer config syntax | `true` |
| 原生 Nginx TLS listener | `true` |
| 公网 HTTPS health | `200` |
| 公网 HTTPS root | `200` |
| 公网 HTTPS static asset | `200` |
| r22 source/venv/static 三个 `current` target | `true` |
| 原生 API/worker/outbox/Redis/Nginx 服务 | `active` |
| PostgreSQL/Redis 未公网监听 | `true` |
| 历史资源删除计数 | `0` |

证书由真实 ACME webroot 流程签发；HTTPS 检查未使用跳过证书校验的客户端选项。

## 4. 脱敏操作账本

| Order | Action | Result | Exit code / HTTP status |
| --- | --- | --- | --- |
| 01 | r22、服务、公开 health 与历史入口预检 | pass | `0` / `200` |
| 02 | root-only archive 与内容完整性校验 | pass | `0` |
| 03 | archive runtime JSON 同配置回载预检 | pass（第二次带 JSON 内容类型） | `0` / `200` |
| 04 | 初次 HTTP-only 接管 | failed：ACME probe worker 不可读 | HTTP `403` |
| 05 | 自动旧入口回退 | failed：历史入口 restart 后证书/上游网络类启动错误 | nonzero / HTTPS `000` |
| 06 | 原生 HTTP 恢复、probe 权限修正 | pass | `0` / `308` / `200` |
| 07 | Certbot webroot certificate issuance | pass | `0` |
| 08 | 原生 HTTPS 接管与 r22 公网回归 | pass | `0` / `200` |

## 5. 边界与后续门禁

| Boundary | Count / Status |
| --- | --- |
| r23 `current` symlink switch | `0`，not performed |
| r22 `current` symlink retained | `true` |
| Stage09 service definition write | `0` |
| Stage09 API/worker/outbox restart for r23 | `0` |
| Legacy resource delete | `0` |
| Release/venv/static cleanup | `0` |
| Database/Redis write | `0` |
| Telegram/LLM/Provider call | `0` |

下一步必须由用户在 Telegram 中关闭现有 Mini App 后重新点击“打开工作区”，确认工作区可见且关系导航可用。该人工验收成功后，才可单独决定是否激活 r23；旧资源 retirement 和任何回收仍需要后续独立步骤，不能由本次 HTTPS 恢复自动触发。
