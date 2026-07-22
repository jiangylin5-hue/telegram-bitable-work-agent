# Stage09 公网入口就绪审计（2026-07-23）

## Status

- Evidence status: `executed`
- Scope: 对 Stage09 公网 HTTPS 与 Telegram controlled smoke 前置条件的只读审计。
- External write: `none`
- Result: `blocked_by_hostname_and_dns`

## 已验证事实

| 项目 | 只读结论 |
| --- | --- |
| Stage09 内部入口 | 原生 Nginx active，`stage09-p1.conf` 已启用；r5 继续只在 `127.0.0.1:18090` 提供静态与 API 入口。 |
| 80/443 所有者 | 仅有一个 Docker port publisher，占用属于历史 Stage03 范围的 Caddy 容器。宿主机 `caddy.service` inactive，`/etc/caddy/Caddyfile` 不存在。 |
| Stage03 边界 | 该 Caddy 是 Stage03 的公网入口；停止、替换、升级、迁移或删除它都会触碰 Stage03，故本轮未执行。 |
| Caddy 到 Stage09 | Caddy 位于已识别的自定义私网；其当前访问宿主机 `:18090` 被 loopback-only Nginx 拒绝。Caddy 私网来源、宿主机 bridge gateway 与候选 `/32` allowlist 均已读取，现有 Nginx renderer 可成功生成受限 bridge listener 配置；该候选尚未写入。 |
| Stage09 公网配置 | `/etc/stage09-p1/runtime.env` 未找到 `PUBLIC_BASE_URL`、`APP_PUBLIC_BASE_URL`、`STAGE09_PUBLIC_BASE_URL`、`STAGE09_HOSTNAME`、`TELEGRAM_WEBHOOK_URL` 或 `WEBHOOK_URL`。 |
| 本机待部署配置 | ignored `.local` 仅发现 Provider base-url 与 Telegram webhook secret 键；没有 Stage09 hostname/domain/public base-url 键。 |
| 本地上线资产 | 已有受控 host renderer 与 activation script；二者会在执行时发现唯一 Caddy、验证 DNS/内部健康、原子变更受限 Nginx 与单一 host block，并在失败时回滚。这是待发布代码，不是服务器写入证据。 |

## 不能替代的前置条件

1. 一个专属于 Stage09 的 hostname。
2. 该 hostname 的 DNS 已指向目标服务器，并能在公网解析。
3. 在不修改 Stage03 既有 host 的前提下，对历史 Caddy 添加唯一的 Stage09 host block、并将 Stage09 Nginx 仅绑定到已验证 bridge gateway 且只允许 Caddy `/32` 来源的明确授权。

得到上述条件后，后续执行固定为：备份现有 Caddy 配置 → 写入受限 Nginx bridge listener → `nginx -t` / reload 并从 Caddy 容器验证内部健康 → 添加单一 Stage09 host → `caddy validate` → reload → 从公网验证 HTTPS 与 `/health` → 配置 webhook public URL → 在明确测试群内完成一次 Telegram 接收、审计和受控回执 smoke。不得借由停止 80/443 的 Stage03 Caddy 来为 Stage09 腾端口。

本地 assets 的 fixture 验证通过并已被 sealed-release verifier 列为必需项；仍必须在用户提供专属 hostname、该 hostname DNS 已指向目标服务器、且对本次受控 Caddy/Nginx 写入明确授权后，才可在服务器执行。它们不会停止、替换、升级、重建或迁移历史 Caddy 容器。
