# Stage09 Telegram Desktop 工作台交接 r24 部署证据

## Status

- Status: `r24-active-human-acceptance-pending`
- Date: `2026-07-23`
- Artifact: `stage09-p1-20260723-r24`
- Source commits: `41fe589`, `271ec50`, `ea77237`
- 红线: 未发送消息，未改 webhook/allowlist/群成员，未确认 draft，未调用 LLM/Provider，未写业务记录，未改 Caddy/Docker/DNS，未清理 r23/r22 或 Stage03。

## 验证与部署结果

| Check | Result |
| --- | --- |
| release/static/Nginx RED 后 GREEN | `PASS` |
| backend Stage09 focused | `5 passed` |
| Mini App relevant | `4 files / 21 tests passed` |
| Mini App build | `exit 0` |
| r24 release/venv/static atomic switch | `true` |
| sealed validators、0033 offline migration、manifest | `true` |
| real database migration | `20260723_0033` |
| HTTPS health/root/static/handoff | `200` |
| handoff headers | `no-store` / `no-referrer` |
| HTTP root / ACME probe | `308` / `200` |
| API/worker/outbox/Redis/Nginx | `5 active` |
| PostgreSQL/Redis public listener | `false` |
| r23 rollback source/venv/static retained | `true` |

ACME gate 仅新增并保留既有 webroot 下固定普通文本 probe；未修改 ingress/Caddy/Docker/80/443。r24 上传包、partial upload、offline SQL、临时 runtime/Nginx fixture、Bot API 临时文件均已清理；r23/r22、r24 immutable artifacts、manifest、root-only rollback backup 与固定 probe 保留。

## 未完成项目

| Check | Result |
| --- | --- |
| real issue → exchange → browser bootstrap | `blocked`：没有可安全复用的真实 initData，未伪造身份或记录 raw credential |
| `getChatMenuButton` | `true` |
| `setChatMenuButton` | `false`：三次受控尝试均 Telegram HTTP `400`，脱敏类别 `button` |
| webhook/sendMessage/其它 Telegram 写入 | `0` |
| Telegram Desktop 人工验收 | `pending-user` |

用户应在 Telegram Desktop 重新打开 Mini App，测试“全屏工作区”和“在浏览器打开工作台”，并确认浏览器宽屏的 Base、数字员工与客户—群聊导航。人工验收通过前不得 retirement 或清理旧 release。
