# Stage09 原生入口：Stage07 域名 502 修复记录（2026-07-23）

## Status

- Scope: 修复 `stage07.jiangtest1.online` 到已部署的原生 Stage09 服务的公共 HTTPS 路由。
- Change boundary: 仅替换 Caddy 运行时配置中的 `stage07.jiangtest1.online` 单一路由；不创建 Docker 服务、不停止或重建历史 Stage03 容器、不修改数据库、Telegram、业务数据或应用代码。
- Pre-change reproduction: `https://stage07.jiangtest1.online/` 为 HTTP `502`；`https://stage09.jiangtest1.online/` 为 HTTP `200`。

## 已确认根因

历史公开 Caddy 容器的运行时路由中，`stage07.jiangtest1.online` 仍将静态路径指向 `stage07-web:80`，其余路径指向 `stage07-api:8000`。这两个历史 Stage07 acceptance 容器已不存在，因此 Caddy DNS 解析上游失败并返回 `502`。

相同运行时 Caddy 配置中的 `stage09.jiangtest1.online` 已通过单一 `reverse_proxy` 路由指向原生 Nginx bridge `172.18.0.1:18090`，且线上健康。

## 最小修复与验收

1. 从 Caddy Admin API 获取 `stage07` 路由及其 ETag。
2. 用同一条 Stage09 已验证路由结构，仅将 host 改为 `stage07.jiangtest1.online`，对该路由执行带 `If-Match` 的单次 `PATCH`。
3. 验证 `stage07` 首页与 `/health` 为 HTTP `200`，同时复核 `stage09` 首页与历史 Stage03 API 健康路由仍可达。
4. 记录当前限制：历史 Caddy 使用运行时 API 覆盖；如果未来重建该历史容器，必须重新受控加载 ingress 配置。此次不改变容器生命周期。

## 实施结果

- 已通过带 ETag `If-Match` 的 Caddy Admin API `PATCH` 原子替换 `stage07` 的单一路由；旧的 `stage07-web:80` / `stage07-api:8000` 上游不再存在于该路由中。
- 外部真实验证结果：`stage07` 首页、`stage07/health` 和当前前端 JavaScript 资源均为 HTTP `200`；`stage09` 首页和历史 Stage03 API `/health` 同时保持 HTTP `200`。
- Chrome 对用户相同的 `stage07` HTTPS 地址重新截图后，已从 Caddy `502` 页面进入应用自身的“当前身份没有可访问的工作区。”门禁页面。该状态符合普通浏览器没有 Telegram Mini App 签名身份的预期，不代表四个核心业务页面已验收。
- 未重启、停止、重建或升级历史 Caddy/Stage03 容器；未修改数据库、Telegram、应用业务代码或 Stage09 原生服务。

## 已知运行时限制

历史 Caddy 容器仍以旧的只读 Caddyfile 启动，而当前 Stage09 和本次 Stage07 alias 都由 Caddy Admin API 的活动配置提供。若该历史容器未来被重建或重启，必须重新以受控脚本加载两条原生入口路由；本次不改变该容器生命周期。
