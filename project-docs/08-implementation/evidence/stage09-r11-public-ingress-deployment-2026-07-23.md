# Stage09 r11 原生服务与公网入口真实部署证据

## Status

- Date: 2026-07-23
- Scope: Stage09 原生服务 r11、专属 HTTPS 入口、GitHub 分支发布
- Result: 已部署并通过真实公网健康验证
- Excluded: Telegram webhook 写入、真实 Telegram 发送、真实 Provider/LLM 调用、Stage07 Browser/UI 验收

## 已执行的真实操作

1. 将仅包含 `backend` 与 `deploy/stage09-native` 的 r11 sealed archive 上传到目标服务器；本地与服务器 SHA-256 一致后才解包。
2. 在切换前执行 release-layout、release-assets、runtime-preflight、public-ingress-assets；每项均通过。release-layout 同时逐字节拒绝 `.sh` 文件中的 CRLF，防止 Ubuntu `dash` 因 Windows 行尾失败。
3. 原子切换 Stage09 的 release、venv 和静态文件 symlink，并只重启 `stage09-p1-api`、`stage09-p1-worker`、`stage09-p1-outbox-bridge`；Nginx 仅 reload。旧 r8 保留为回滚点。
4. 执行受控 public-ingress activation：Nginx 只绑定已发现的 Docker bridge gateway，并只允许历史 Caddy 容器的单一私网 IP；Caddy 通过 stdin Admin API 加载唯一 `stage09-managed` host block。未停止、重建、升级、替换或重启历史 Caddy 容器。
5. 通过 GitHub API 更新 `codex/stage07-mini-app-ui` 远端分支，并回读远端 tree，与本地 HEAD tree 一致。

## 验证证据

| 项目 | 真实检查 | 结果 |
| --- | --- | --- |
| r11 release layout | 服务器 `verify-release-layout.sh` | PASS |
| 发布资产与运行时门禁 | 服务器 `test-release-assets.sh`、`test-runtime-preflight.sh`、`test-public-ingress-assets.sh` | PASS |
| 原生服务 | API、worker、outbox、Nginx 的 `systemctl is-active` | 均为 `active` |
| 内部健康 | Stage09 API loopback health | PASS |
| Caddy → Nginx | 从历史 Caddy 容器访问 bridge gateway 的 `/health` | PASS |
| 公网 HTTPS | 外部客户端访问专属 hostname 的 `/health` 与 `/` | 均为 HTTP 200 |
| GitHub | 远端 ref 回读并比较 tree | 与本地 HEAD 一致 |

## 实施中发现并修复的问题

- **Caddyfile 旧 inode：** 历史容器看到的是启动时绑定的旧 inode，宿主机路径后续的追加不会进入容器。修复为：从容器读取当前 Caddyfile，构建候选配置后经 `docker exec -i ... caddy reload --config -` 加载；失败时以同一接口加载原始运行时配置。该方式没有写宿主机 Caddyfile，也没有改动容器生命周期。
- **Windows CRLF：** Windows 上 `git archive` 曾将 shell 文件导出为 CRLF，导致服务器预检在切换前拒绝 r9/r10。修复为仓库 `.gitattributes` 强制 `*.sh text eol=lf`，并在 release-layout 增加字节级 CRLF 拒绝；r11 archive 已在上传前确认 shell header 为 LF。

## 已知边界与后续动作

- 当前 Caddy 路由是真实生效的运行时配置。由于历史 Caddy 的 bind mount 已与宿主机路径脱节，若未来有人重启或重建该**历史**容器，它会从旧 Caddyfile 启动，Stage09 路由需要使用当前 release 的 activation 脚本重新受控加载；本阶段未也不会为此重启、替换或迁移 Stage03。
- 下一项生产联调是设置 Telegram webhook 到已验证的 HTTPS 入口，随后进行 allowlist 范围内的真实消息/LLM case；两项必须分别留下 Telegram send log、webhook/endpoint 证据和应用审计记录。
- 失败的 r9/r10 source release 目录与本地封存包暂保留为短期排障证据；它们不是 current、venv 或静态发布目标，后续清理前需保留 r8 回滚点和 r11 当前版本。
