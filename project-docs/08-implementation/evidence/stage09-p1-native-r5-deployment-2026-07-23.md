# Stage09 P1 原生 r5 部署真实证据（2026-07-23）

## Status

- Evidence status: `executed`
- Artifact: `stage09-p1-20260723-r5`
- Scope: 已发布 Stage08 验收源码树的原生服务器 release/venv/static 激活与回环验收。
- Result: `PASS`
- Out of scope: 公网 DNS/TLS、80/443 入口变更、历史 Stage03/Docker、真实 Telegram、Provider 写入与业务数据写入。

## 本地发布前证据

| 检查 | 实际结果 |
| --- | --- |
| Mini App production build | `tsc -b && vite build` 通过 |
| Release asset validation | `release-assets: PASS` |
| Runtime preflight | `runtime-preflight: PASS`，包括 PostgreSQL loopback、Redis socket、Stage03/Stage07 marker 拒绝与 unsafe-mode 拒绝 |
| 密封发布包 | backend + `deploy/stage09-native` 由 `git -c core.autocrlf=false archive` 生成；静态包由当前 `mini-app/dist` 生成；SHA-256 manifest 随包上传 |

## 服务器实际执行与独立验证

1. 上传 r5 release、static、SHA-256 manifest 和部署脚本至专用 `/tmp/stage09-p1-r5`。
2. 服务器验证 SHA-256，创建不可变 release、复制隔离 venv、安装静态资源，运行 release layout、native service/data asset、manifest 与固定迁移离线校验。
3. 在 root 控制下执行 `20260720_0032`，原子切换 `/opt/stage09-p1/current`、`/opt/stage09-p1/current-venv`、`/var/www/stage09-p1/current`，启动 API/worker/outbox 与内部 Nginx。
4. 部署脚本的实际结果：`stage09-r5: pass`、API loopback pass、Nginx loopback pass；Nginx syntax test successful。
5. 独立 root 验收再次确认：三处 current 指针均为 r5，`stage09-p1-redis`、API、worker、outbox、Nginx 均 active，migration result 为 `success`，`127.0.0.1:18080/health`、`127.0.0.1:18090/health`、`127.0.0.1:18090/` 全部成功。
6. 验证后删除 `/tmp/stage09-p1-r5` 上传临时目录。

## 说明

本次 r5 的仓库变化是 Stage08 验收与部署证据文档，不包含新的业务运行时代码；重新激活的目的是用同一已发布源码树实测完整原生发布链。生产公网入口仍缺少独立 hostname/DNS，且 80/443 不在本次写入范围内。
