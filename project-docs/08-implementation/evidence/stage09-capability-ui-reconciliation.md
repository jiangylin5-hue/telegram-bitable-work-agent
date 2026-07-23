# Stage07/Stage08 能力接入 Mini App：本地浏览器验收证据

## Status

- Date: 2026-07-24
- Scope: Stage07 表格能力可发现性、Stage08 安全协作和长期记忆的 Mini App 接入。
- Result: 本地源码、全量 Mini App 自动化回归、受控浏览器交互、真实 Stage09 静态版本发布和公网 HTTPS 页面资源验收均已完成；真实 FastAPI/PostgreSQL 授权查询、真实 LLM 协作结果和 Telegram Mini App 身份链路仍待用户侧受控验收，不能以本文件替代。

## 1. 自动化验证

在 `mini-app` 目录执行：

```powershell
npm.cmd test -- --run
npm.cmd run build
```

结果：

- Vitest：`73` 个测试文件、`294` 个测试全部通过。
- TypeScript + Vite production build：通过。
- `git diff --check -- mini-app project-docs docs`：通过；未包含用户已有的 `.superpowers/sdd/*` 未提交改动。

覆盖点包含：

- 表格操作中心将已实现的 Base、表、字段、视图、记录、模板和导入操作分发回原有受控面板；导出等未实现项保持禁用并标注“即将上线”。
- Stage08 查询只发送安全请求字段，安全响应不会渲染 provider/private context；`group_context` 只显示受权上下文已被使用的证据标签。
- 记忆工作台只显示安全投影，并明确“记忆指导做法，表格决定实时业务事实”。
- 移动端“更多工作台”菜单可以打开智能协作、记忆与知识和成员权限，不再把它们藏在宽屏右栏中。

## 2. 真实浏览器交互

### 环境与边界

- 使用本地 Vite 运行时：`http://127.0.0.1:4179/`。
- 使用本机 Chrome Chromium 内核，实际点击/输入/等待页面状态，不是组件快照。
- 为把验收限制在 UI contract，本次浏览器请求由受控 API fixture 返回安全 DTO；没有写入数据库、调用真实 LLM、发送 Telegram 或读出原始群聊。
- fixture 故意携带 `private_context: "must not render"`，页面中确认未出现该文本。

### 桌面宽度 1440px

1. 点击首页“表格操作”打开 `表格操作中心`。
   - 新建 Base、模板与导入等已实现入口可用。
   - “导出数据”保持禁用，文案明确说明需要独立的脱敏、权限和异步任务设计。
2. 点击“智能协作”，选择已授权数字员工，输入协作请求并提交。
   - 等待到“已使用受权群聊上下文作为证据”出现。
   - 页面未显示 fixture 私有字段。
3. 点击“记忆与知识”。
   - 展示安全长期记忆项和版本。
   - 展示知识边界：没有安全知识源目录投影时，不允许客户端填写或猜测来源 ID。
4. 浏览器 console/page error 计数为 `0`。

### 手机宽度 390px

1. 点击底部“更多：打开其他工作台”。
2. 从弹出菜单打开“智能协作”，选择员工、提交请求并看到群聊上下文安全证据。
3. 关闭后再次打开“更多”，进入“记忆与知识”，看到长期记忆与知识边界。
4. 浏览器 console/page error 计数为 `0`。

这一轮确认了此前手机宽度下右侧助理栏隐藏导致的新能力无入口的问题已被处理；它不意味着所有桌面功能在 Telegram 容器中已经验收。

## 3. r25 原生静态发布与公网 HTTPS 验证

- Source commit：`28c05eb`（`feat(mini-app): expose stage08 workspace capabilities`）。
- 发布方式：只发布 `mini-app/dist` 到服务器不可变目录 `stage09-p1-20260724-r25`，原子切换 `/var/www/stage09-p1/current`；r24 作为 `current.previous` 保留。
- 上传包 SHA-256：`c2af224c625b40db5099c43f7e37df6c10d04ddef6c211598e897de2cbc67cd3`，服务器端复算一致；Nginx 配置检查通过后才切换。
- 发现并处理既有 ingress 缺口：静态目录已是 Stage09，但服务器 Nginx 仍写着 `stage07.jiangtest1.online` 及其证书，导致 `stage09.jiangtest1.online` 的正常 TLS 校验失败。通过现有 release 内的 Nginx renderer 将 host 切至 Stage09，使用既有 ACME webroot 申请对应 Let’s Encrypt 证书，再通过 `nginx -t` 和 reload 生效。
- 公网正常 TLS 验证：`https://stage09.jiangtest1.online/` 为 `200`，`/health` 为 `200`，r25 的 CSS/JS 静态资源均为 `200`。真实 Chrome 载入首页并请求两个 r25 asset；没有 Telegram `initData` 的普通浏览器收到 `/mini-app/bootstrap` 的预期 `401`，页面正确显示无可访问工作区，而不是伪造身份或数据。
- 本次发布未迁移数据库、未重启 API/worker/outbox/Redis、未改 Telegram webhook/allowlist、未调用 LLM、未写业务记录，也未触碰 Stage03。
- 本地和服务器 `/tmp` 的上传压缩包均已在验证后清理；r24 静态目录、r25 当前静态目录及 Nginx 配置前备份保留为回退证据。

## 4. 未被掩盖的后续缺口

| 项目 | 现状 | 下一步 |
| --- | --- | --- |
| Base/Table/Field/View/Record 生命周期、复制、删除、归档与恢复 | 没有完整安全 API | 独立写 schema、关系完整性、恢复窗口、审计与权限 contract 后实现 |
| 批量编辑/删除、CSV/XLSX/View 导出 | 没有产品级 API | 先定义字段脱敏、异步任务、下载权限与审计 |
| 记忆撤销 | 安全列表没有稳定 item/candidate 标识 | 后端补安全版本化列表 contract 后接入明确确认操作 |
| RAG 重建 | 后端没有安全知识源目录 projection | 补授权 source-directory API、幂等 ticket 与审计后接入 |
| 真实授权运行时 | 公网页面与静态资源已验证；未用真实 Telegram `initData` 调用 FastAPI/PostgreSQL 或 OpenRouter | 从 Telegram 打开 Mini App，以受控只读问题完成一条无原文群聊泄露的真实闭环 |

## 5. 验收结论

本包证明“已有能力在 UI 中能被发现、可以走入既有受控流程，并在桌面和手机浏览器中可交互”，而且新版前端已经部署到 Stage09 公网域名。它没有把尚未实现的生命周期、导出、批量、RAG 重建或真实 Telegram/LLM 授权调用伪装成已交付。下一道门是从 Telegram 打开已部署的 Mini App，以真实身份和现有授权工作区完成等价的只读闭环。
