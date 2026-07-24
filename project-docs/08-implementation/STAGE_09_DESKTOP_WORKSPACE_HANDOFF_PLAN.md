# Stage09 Telegram 全屏与浏览器工作台交接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram Mini App 优先全屏；全屏不可用时，已验证用户可安全进入浏览器宽屏工作台。

**Architecture:** 前端 SDK adapter 管理 Telegram 全屏与 `openLink`。后端把已验证 Telegram identity 转成短期一次性 handoff，再交换为 HttpOnly browser session；现有业务 API 继续使用 `Stage06RequestIdentity` 和授权服务。

**Tech Stack:** React、TypeScript、Vitest、FastAPI、SQLAlchemy、Alembic、PostgreSQL、Telegram Mini Apps JavaScript API。

## Global Constraints

- ticket 只出现在 URL fragment，禁止 query、浏览器存储、审计正文或日志。
- handoff TTL 固定 5 分钟，browser session TTL 固定 8 小时；ticket 原子单次消费。
- cookie 固定 `Secure; HttpOnly; SameSite=Lax; Path=/`。
- 不改变 Stage03 Docker、r23 入口、Telegram webhook、LLM、allowlist 或业务记录。
- 每项实现先 RED，再最小 GREEN，并保留独立测试证据。

### 2026-07-24 补充：浏览器会话过期恢复

**已确认事实：** 浏览器工作台会话按现行安全约定在 8 小时后过期。过期不会删除工作区、Base 或用户授权；重新从 Telegram 的“打开工作区”进入即可签发新的单次 handoff 并建立新的浏览器会话。

**本次范围：** 保持 handoff 5 分钟、浏览器会话 8 小时、`Secure; HttpOnly; SameSite=Lax` cookie 与现有权限模型完全不变。前端在 bootstrap 收到 `401` 或 `403` 时，不再只显示“当前身份没有可访问的工作区”，而是明确说明“当前浏览器工作台会话已失效或无访问权限，请返回 Telegram 重新打开工作区”。该提示不得泄露身份、会话有效期、cookie、ticket 或授权明细。

**验收：** 为 `401` bootstrap 编写先失败后通过的 UI 自动化测试；真实桌面入口由用户从 Telegram 重新打开后应进入已授权工作区，而非停留在无说明的空白页。此补充不延长会话、不自动登录，也不改变任何业务数据。

### 2026-07-24 补充：Mini App 浏览器入口身份恢复与能力收口

**根因证据：** 用户在 Telegram Mini App 内点击浏览器入口后，生产 Nginx/API 均记录到三次 `POST /mini-app/browser-handoffs` 返回 `401`。返回体的安全代码为 `stage06_verified_identity_required`，与无身份头的受控探针返回完全一致；数据库中 handoff/session 的数量没有新增。结论是前端模块级 `telegramInitData` 在入口点击时已被清空，后端按设计拒绝，不能以旧首页渲染推断为仍有交接权限。

**修复设计：**

1. `AppContent` 已持有仅内存的 `TelegramMiniAppLaunch.initData`。每次创建 browser handoff 前，必须从该受控内存来源重新设置 API 身份头，再请求 `POST /mini-app/browser-handoffs`；不得写入 localStorage、sessionStorage、URL、日志或页面正文。
2. Telegram host 不具备 `requestFullscreen` 或不满足版本要求时，适配器返回明确的 `fullscreenUnsupported` 状态；界面不再显示点击后必然无效的“进入专注全屏”按钮，保留可用的浏览器入口。
3. 浏览器入口的失败提示必须仅在该次点击失败后出现；成功的新点击会清除旧提示。提示只给恢复方向，不暴露原始身份、ticket、cookie、HTTP 细节或授权对象。

**不在范围：** 不调整 5 分钟 Telegram initData 校验策略、不修改 handoff/session TTL、不增加永久登录、不改变数据库 schema、不会放宽 Telegram、浏览器或业务权限。

**验收：** 先写失败测试证明“模块级身份已清空时，入口仍用当前 Mini App 内存身份发起 handoff”与“不支持全屏时不渲染无效按钮”；再以真实 Telegram 身份点击验证 API 从 `401` 变为受控 `201`，浏览器完成 ticket exchange 后进入工作台。

---

### Task 1: Telegram 全屏兼容层和入口控件

**Files:** Modify `mini-app/src/app/telegram-mini-app.ts`, `mini-app/src/app/App.tsx`, `mini-app/src/app/AppShell.tsx`, `mini-app/src/styles.css`, `mini-app/src/test/telegram-mini-app.test.ts`; create `mini-app/src/app/WorkspaceLaunchControls.tsx` and `mini-app/src/test/workspace-launch-controls.test.tsx`.

**Interfaces:** `requestTelegramMiniAppFullscreen(): 'requested' | 'unsupported' | 'already_fullscreen'`; `WorkspaceLaunchControls({ telegramState, onOpenBrowser })` carries no identity data.

- [ ] **Step 1: Write failing tests.** Add a version-8 runtime fixture that expects `requestFullscreen` exactly once; add a render test that expects `在浏览器打开工作台` after `fullscreenFailed(UNSUPPORTED)`.
- [ ] **Step 2: Verify RED.** Run `cd mini-app && npm run test:run -- telegram-mini-app workspace-launch-controls`; expected failure because state and controls do not exist.
- [ ] **Step 3: Implement the smallest adapter.** Call existing `ready`/`expand`; only call `requestFullscreen` when SDK capability/version permits; subscribe and unsubscribe fullscreen events; render compact controls outside grids.
- [ ] **Step 4: Verify GREEN.** Run `cd mini-app && npm run test:run -- telegram-mini-app workspace-launch-controls && npm run build`; expected exit 0.
- [ ] **Step 5: Commit.** Run `git add mini-app/src/app mini-app/src/styles.css mini-app/src/test && git commit -m "feat(mini-app): add fullscreen workspace controls"`.

### Task 2: One-time handoff and browser session

**Files:** Create `backend/alembic/versions/20260723_0033_mini_app_browser_handoffs.py`, `backend/app/services/stage09_browser_handoffs.py`, `backend/tests/unit/test_stage09_browser_handoffs.py`; modify `backend/app/models/stage07_telegram.py`, `backend/app/services/stage06_identity.py`, `backend/app/api/deps.py`, `backend/app/api/routes/stage06_platform.py`, `backend/app/schemas/stage06_platform.py`, `backend/app/core/config.py`, `backend/tests/unit/test_stage07_mini_app_api.py`.

**Interfaces:** `issue_browser_handoff(uow, identity, now)` returns raw ticket only to authenticated Mini App; `exchange_browser_handoff(uow, ticket, now)` atomically consumes it and returns session token; `resolve_browser_session_identity(uow, token, now)` returns `Stage06RequestIdentity(source='browser_session')`; routes are `POST /mini-app/browser-handoffs` and `POST /mini-app/browser-handoff-exchanges`.

- [ ] **Step 1: Write failing tests.** Assert storage contains `SHA-256(ticket)` but not raw ticket; assert second exchange gets `browser_handoff_consumed`; assert expired/revoked ticket is rejected; assert exchange response sets `Secure`, `HttpOnly`, `SameSite=Lax` cookie and browser cookie can call `/mini-app/bootstrap`.
- [ ] **Step 2: Verify RED.** Run `cd backend && pytest tests/unit/test_stage09_browser_handoffs.py tests/unit/test_stage07_mini_app_api.py -q`; expected failure because model, service and routes are absent.
- [ ] **Step 3: Implement minimal persistence.** Add two timestamped models: `mini_app_browser_handoffs(ticket_hash,user_id,telegram_user_id,expires_at,consumed_at,revoked_at)` and `mini_app_browser_sessions(token_hash,user_id,telegram_user_id,expires_at,revoked_at)`. Generate with `secrets.token_urlsafe(32)`. Exchange uses a conditional update so only one request can consume a ticket.
- [ ] **Step 4: Implement trusted identity.** Existing identity dependency prefers valid Telegram init data, then valid named browser cookie, then development header only outside staging/production. Exchange sets cookie plus `Cache-Control: no-store` and `Referrer-Policy: no-referrer`; it never logs body/token values.
- [ ] **Step 5: Verify GREEN.** Run `cd backend && pytest tests/unit/test_stage09_browser_handoffs.py tests/unit/test_stage07_mini_app_api.py tests/unit/test_stage07_telegram_mini_app_identity.py -q`; expected all pass.
- [ ] **Step 6: Commit.** Run `git add backend && git commit -m "feat(stage09): add secure browser workspace handoff"`.

### Task 3: Fragment-only static handoff and Mini App issuance

**Files:** Create `mini-app/public/browser-handoff.html`, `mini-app/src/test/browser-handoff.test.ts`; modify `mini-app/src/app/api.ts`, `mini-app/src/app/App.tsx`, `mini-app/src/app/WorkspaceLaunchControls.tsx`.

**Interfaces:** `api.createBrowserHandoff()` returns `{ ticket, expiresAt }` only in memory; `buildBrowserHandoffUrl(ticket)` returns same-origin `browser-handoff.html#ticket=...`.

- [ ] **Step 1: Write failing tests.** Click the browser control and assert `WebApp.openLink` receives `#ticket=`, never `?ticket=`, and no storage receives ticket. Test the static page POSTs only `{ticket}`, clears fragment after success and navigates to `/`.
- [ ] **Step 2: Verify RED.** Run `cd mini-app && npm run test:run -- browser-handoff telegram-mini-app`; expected failure because issue API and static page are absent.
- [ ] **Step 3: Implement the smallest flow.** Static page reads only `location.hash`, performs same-origin JSON exchange, calls `history.replaceState`, then `location.replace('/')`; generic failure copy only. `openLink` remains inside the user click handler.
- [ ] **Step 4: Verify GREEN.** Run `cd mini-app && npm run test:run -- browser-handoff telegram-mini-app workspace-launch-controls && npm run build && rg -n "tgWebAppData|ticket=" dist/browser-handoff.html`; expected tests/build exit 0 and no credential literal in asset.
- [ ] **Step 5: Commit.** Run `git add mini-app && git commit -m "feat(mini-app): open secure browser workspace"`.

### Task 4: Seal, deploy, configure Bot main entry and accept

**Files:** Modify `deploy/stage09-native/nginx/stage09-p1-public-https.conf.template`, `deploy/stage09-native/scripts/test-native-public-ingress-assets.sh`, `deploy/stage09-native/scripts/verify-release-layout.sh`, `deploy/stage09-native/scripts/verify-release-assets.sh`, `deploy/stage09-native/scripts/test-release-assets.sh`, `project-docs/08-implementation/STAGE_09_NATIVE_SERVER_DEPLOYMENT_PLAN.md`; create `project-docs/08-implementation/evidence/stage09-desktop-workspace-handoff-2026-07-23.md`.

**Interfaces:** release verifier requires `mini-app/dist/browser-handoff.html` and rejects embedded credential literals; runtime evidence stores only status/count/boolean results.

- [ ] **Step 1: Write failing release and ingress checks.** Require the handoff static asset and reject `tgWebAppData`/`ticket=` literals. Require an exact Nginx `browser-handoff.html` static route that returns `Cache-Control: no-store` and `Referrer-Policy: no-referrer`, rather than proxying the page to FastAPI. Run `cd deploy/stage09-native && sh scripts/test-release-assets.sh && sh scripts/test-native-public-ingress-assets.sh`; expected failure before asset sealing and route/header implementation.
- [ ] **Step 2: Seal and deploy.** Build immutable native release, apply migration, activate through bounded readiness gate, then run real Mini App issue/exchange/browser-bootstrap smoke using only the bound user. Do not send messages, confirm drafts, invoke LLM, alter webhook or retire Docker.
- [ ] **Step 3: Configure Bot entry.** Update only the single Bot menu button/Main Mini App URL/text. No webhook, allowlist, group membership or message write. Record a redacted configuration receipt.
- [ ] **Step 4: Human acceptance.** User tests `全屏工作区` and `在浏览器打开工作台` in Telegram Desktop, then verifies browser-width Base, digital employee and customer-group navigation.
- [ ] **Step 5: Verify and commit.** Run `cd backend && pytest tests/unit/test_stage09_browser_handoffs.py -q`; then `cd ../../mini-app && npm run test:run && npm run build`; then commit evidence and push branch.

## Plan self-review

- Task 1 covers host fullscreen and visual fallback; Task 2 covers secure ticket/session identity; Task 3 keeps ticket fragment-only; Task 4 seals, deploys and records actual Telegram/Desktop evidence.
- The plan changes no unrelated business module and keeps legacy Docker retirement gated on user acceptance.
