# Stage09 Telegram 全屏与浏览器工作台交接设计

> **Status:** 用户于 2026-07-23 确认实施  
> **Scope:** Telegram 内优先全屏；客户端无法全屏时，安全切换到浏览器宽屏工作台。  
> **Out of scope:** 不改变工作区、Base、记录、数字员工、群聊、客户或字段权限语义；不把 Telegram 原始 `initData` 放入 URL、浏览器存储或审计正文。

## 1. 根因

当前 Mini App 已调用 `Telegram.WebApp.ready()` 与 `expand()`。`expand()` 只能要求 Telegram 扩展到**宿主允许的最大高度**，不能改变 Telegram Desktop 的原生弹窗宽度；截图中的窄窗口由 Telegram Desktop 容器控制，而不是页面 CSS 固定宽度。

Telegram 的 `requestFullscreen()` 可以在支持 Bot API 8.0+ 的客户端请求全屏，但客户端可能以 `fullscreenFailed(UNSUPPORTED)` 拒绝。因此不能把“Telegram 全屏”作为唯一桌面方案。复杂多维表格必须具备浏览器宽屏入口；Telegram 继续承担消息、提醒、轻操作和可信身份发起入口。

## 2. 已确认体验

```text
Telegram 打开工作区
  -> ready + expand
  -> 支持时 requestFullscreen
       -> Telegram 全屏工作台
  -> 不支持、失败或用户主动选择
       -> “在浏览器打开工作台”
       -> 一次性交接票据（仅 URL fragment）
       -> 同源 exchange
       -> HttpOnly browser session cookie
       -> 清除 fragment 后进入宽屏工作台
```

| 动作 | 可用条件 | 结果 |
| --- | --- | --- |
| `全屏工作区` | Telegram WebApp 支持 Bot API 8.0+ 且尚未全屏 | 请求 Telegram 进入全屏；失败时保留当前页面。 |
| `在浏览器打开工作台` | 已验证 Telegram Mini App 身份 | 在用户点击事件中调用 `WebApp.openLink()`，在默认浏览器进入同一用户、同一权限的工作台。 |

普通浏览器、未验证网页和无 Telegram SDK 的环境不显示 Telegram 专属控件。

## 3. 安全交接协议

### 3.1 票据流

1. Mini App 只在已验证 `X-Telegram-Init-Data` 上下文中调用 `POST /mini-app/browser-handoffs`。
2. 服务端复用 Telegram 签名、过期、绑定与 workspace member 校验，产生随机 `ticket`；数据库只存 `SHA-256(ticket)`，绝不存 raw ticket 或 raw `initData`。
3. 用户点击后打开 `https://<same-origin>/browser-handoff.html#ticket=<ticket>`。ticket 位于 fragment，不会被发送至 Nginx、API、referer 或访问日志。
4. 静态 handoff 页面读取 fragment，通过同源 `POST /mini-app/browser-handoff-exchanges` 的 JSON body 交换票据；成功后先清除 fragment，再跳转到 `/`。
5. exchange 只能消费一次、未过期且未撤销的 ticket，创建 browser session 并设置 host-only `Secure; HttpOnly; SameSite=Lax; Path=/` cookie。exchange 响应固定 `Cache-Control: no-store` 与 `Referrer-Policy: no-referrer`。

### 3.2 持久化与生命周期

| Object | 持久化字段 | 生命周期 | 规则 |
| --- | --- | --- | --- |
| `mini_app_browser_handoffs` | `ticket_hash`、`user_id`、`telegram_user_id`、`expires_at`、`consumed_at`、`revoked_at` | 5 分钟 | 仅已验证 Telegram 启动可以签发；仅可消费一次。 |
| `mini_app_browser_sessions` | `token_hash`、`user_id`、`telegram_user_id`、`expires_at`、`revoked_at` | 8 小时 | cookie 仅携带 raw token；每次 API 请求重新校验 hash、过期和撤销状态。 |

两种 token 都用 `secrets.token_urlsafe(32)` 生成。所有无效、过期、撤销或重放失败返回稳定安全错误码，不回显 token、用户、绑定或 workspace 信息。

### 3.3 身份优先级

```text
valid X-Telegram-Init-Data
  -> telegram_binding identity
valid browser session cookie
  -> browser_session identity
development header（仅非 staging/production）
  -> development_header identity
otherwise
  -> 401
```

浏览器 session 只恢复既有 `Stage06RequestIdentity` 所需的 `user_id` 和 Telegram trace 信息。所有 workspace、base、table、field、record 权限仍由每个既有服务端 endpoint 重新执行；browser session 不授予额外字段、写入、Bot 发送或系统权限。

## 4. 前端边界

`telegram-mini-app.ts` 是 Telegram SDK 兼容层：调用 `ready()`、`expand()`，有能力时请求全屏，订阅 `fullscreenChanged` 与 `fullscreenFailed`。它不参与身份判断，也不读取或持久化 `initDataUnsafe`。

`WorkspaceLaunchControls` 是独立的紧凑控件：提供“全屏工作区”和“在浏览器打开工作台”、加载态及通用失败提示。它不位于数据网格中，不改变业务路由，也不保存 ticket。

`browser-handoff.html` 是最小静态页面：只读取 fragment、调用同源 exchange、清除 fragment、跳转首页并显示通用错误。它不加载工作区数据、不缓存 ticket、没有第三方脚本。

## 5. Telegram 入口配置

发布后把单一 Bot 的菜单按钮设置为 Main Mini App / `web_app` 入口，同时保留当前消息中的“打开工作区”按钮作为兼容路径。Main Mini App 或 direct-link 入口减少 mobile compact 打开方式；Desktop 宽度仍由全屏请求和浏览器交接兜底。

这是一次受限 Telegram Bot 配置写入：只更新 menu button URL/text，不发送消息、不改变 webhook、allowlist、聊天成员或业务记录。必须在代码发布与端到端交接验证后执行并保存脱敏回执。

## 6. 验收标准

1. 支持 fullscreen 的 Telegram runtime 调用 `ready`、`expand`、`requestFullscreen`，并依据 `fullscreenChanged` 更新控件。
2. 不支持 runtime 时不抛错，稳定显示浏览器宽屏入口。
3. raw Telegram `initData`、handoff ticket、browser session token 不进入 URL query、浏览器存储、审计正文或日志。
4. ticket 只可由已验证 Telegram binding 签发，5 分钟内单次消费；重放、过期、撤销、非法格式均拒绝。
5. cookie 必须为 `Secure`、`HttpOnly`、`SameSite=Lax`；仍受全部既有权限控制。
6. Telegram Desktop 实测点击“在浏览器打开工作台”后，浏览器显示宽屏工作台并可进入 Base、数字员工、客户—群聊关系索引。
7. 浏览器刷新、session 过期或 exchange 失败只显示安全恢复状态，不泄露身份或票据。

## 7. 非目标与回退

- 不通过 CSS 强行改变 Telegram Desktop 原生弹窗尺寸。
- 不允许 URL 携带 `tgWebAppData`、raw init data 或长期 credential。
- 不实现跨设备同步、永久登录、第三方 OAuth 或多浏览器会话管理。
- 若 browser handoff 异常，Mini App 保持原 Telegram 身份路径可用；不影响 Telegram 入口、数据库、LLM、Bot 发送或 r23。
