# Stage09 桌面舒适模式与真实导航 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Telegram Desktop 默认保持可切换的窗口体验，并让左侧每一个可见图标打开真实功能且带中文用途提示。

**Architecture:** Telegram adapter 继续负责 `ready`、`expand` 和全屏事件，但把全屏请求改为明确的用户动作，同时补充 `exitFullscreen`。`WorkspaceLaunchControls` 始终提供安全浏览器 handoff，并依据当前宿主状态显示进入/退出全屏。`AppShell` 将导航建模为 route、受控 action 或明确禁用的未来入口；未来模块保留图标骨架但不再使用无处理 hash 链接。

**Tech Stack:** React、TypeScript、Vitest、Telegram Mini Apps JavaScript API、既有 Stage09 browser handoff。

## Global Constraints

- 不修改 Telegram initData、handoff ticket、browser session、后端 API、数据库、Nginx、Bot 配置或服务器。
- 保留 `ready()`、`expand()`、fragment-only handoff、同步预开浏览器页与安全 URL 校验。
- 不修改用户现有 `.superpowers/sdd/*` 未提交文件。
- 所有新增可见文字、提示和文档均为中文；代码接口维持英文。

---

### Task 1: 可选全屏和始终可见的浏览器入口

**Files:**
- Modify: `mini-app/src/app/telegram-mini-app.ts`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/WorkspaceLaunchControls.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/telegram-mini-app.test.ts`
- Test: `mini-app/src/test/workspace-launch-controls.test.tsx`

**Interfaces:**
- `requestTelegramMiniAppFullscreen()` 仅由按钮点击调用。
- `exitTelegramMiniAppFullscreen()` 返回 `requested | unsupported | already_windowed`。
- `WorkspaceLaunchControls` 接收 `onRequestFullscreen`、`onExitFullscreen` 和已授权的 `onOpenBrowser`；它不持有身份数据或 ticket。

- [ ] **Step 1: 写失败测试。**

```ts
test('does not request Telegram fullscreen when the application mounts', () => {
  render(<App />)
  expect(requestFullscreen).not.toHaveBeenCalled()
})

test('shows the browser workspace action while Telegram is fullscreen', () => {
  render(<WorkspaceLaunchControls telegramState={{ kind: 'fullscreen' }} onOpenBrowser={vi.fn()} />)
  expect(screen.getByRole('button', { name: '在浏览器打开完整工作台' })).toBeVisible()
})
```

- [ ] **Step 2: 验证 RED。**

```text
cd mini-app
npm.cmd run test:run -- telegram-mini-app workspace-launch-controls
```

Expected: 新断言因当前自动全屏和仅 `UNSUPPORTED` 时显示浏览器入口而失败。

- [ ] **Step 3: 最小实现。**

```ts
prepareTelegramMiniAppViewport()
const unsubscribe = subscribeTelegramMiniAppFullscreen(setTelegramFullscreenState)
setTelegramFullscreenState(readTelegramMiniAppFullscreenState())
return unsubscribe
```

在控件中只从明确的 `onClick` 调用全屏请求或退出；保留现有浏览器 handoff click 流。为 `.app-shell`、`.desktop-sidebar` 和 `.app-content` 添加 12px 视觉留白、圆角和窄窗口回退规则。

- [ ] **Step 4: 验证 GREEN。**

```text
cd mini-app
npm.cmd run test:run -- telegram-mini-app workspace-launch-controls browser-handoff
npm.cmd run build
```

Expected: 测试和 TypeScript/Vite 构建通过。

- [ ] **Step 5: 提交。**

```text
git add mini-app/src/app/telegram-mini-app.ts mini-app/src/app/App.tsx mini-app/src/app/WorkspaceLaunchControls.tsx mini-app/src/styles.css mini-app/src/test/telegram-mini-app.test.ts mini-app/src/test/workspace-launch-controls.test.tsx
git commit -m "fix(mini-app): make fullscreen optional"
```

### Task 2: 真实左栏导航和中文用途提示

**Files:**
- Modify: `mini-app/src/app/AppShell.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/app-shell-navigation.test.tsx`

**Interfaces:**
- `AppShell` 接收 `onOpenDraftHub`、`onOpenTeamBot`、`onOpenGovernance` 受控 action。
- 每个可见 navigation item 有 `label`、`description`、`onClick?`、`availability`；渲染为 `button`，并输出中文 `title`、`aria-label`、`data-nav-hint`。`availability='planned'` 时使用 `disabled` 和“即将上线”说明。

- [ ] **Step 1: 写失败测试。**

```tsx
test('opens real supported destinations and has Chinese usage hints', () => {
  render(<AppShell {...props} onOpenDraftHub={openDrafts} onOpenTeamBot={openBot} />)
  fireEvent.click(screen.getByRole('button', { name: '待确认：查看待处理草稿' }))
  fireEvent.click(screen.getByRole('button', { name: '团队 Bot：使用已授权团队助手' }))
  expect(openDrafts).toHaveBeenCalledTimes(1)
  expect(openBot).toHaveBeenCalledTimes(1)
})
```

- [ ] **Step 2: 验证 RED。**

```text
cd mini-app
npm.cmd run test:run -- app-shell-navigation
```

Expected: 当前 `#...` 占位链接和缺失 action props 使断言失败。

- [ ] **Step 3: 最小实现。**

```ts
const primaryItems = [
  { label: '工作区', description: '查看今日事项', onClick: () => onNavigate('home') },
  { label: '待确认', description: '查看待处理草稿', onClick: onOpenDraftHub },
  { label: 'Bases', description: '浏览和打开多维表格', onClick: () => onNavigate('bases') },
  { label: '团队 Bot', description: '使用已授权团队助手', onClick: onOpenTeamBot },
]
```

已实现入口只在对应 action 可用时启用；没有现有页面的消息、视图、自动化、设置入口保留为 `disabled` 的“即将上线”按钮，绝不保留无处理 hash 链接。CSS 使用 `data-nav-hint` 在 hover/focus 时显示中文说明，避免永久扩大 72px 图标栏。

- [ ] **Step 4: 验证 GREEN。**

```text
cd mini-app
npm.cmd run test:run -- app-shell-navigation app-shell workspace-launch-controls telegram-mini-app
npm.cmd run build
git diff --check
```

Expected: 所有指定测试、构建和 diff 检查通过。

- [ ] **Step 5: 提交。**

```text
git add mini-app/src/app/AppShell.tsx mini-app/src/app/App.tsx mini-app/src/styles.css mini-app/src/test/app-shell-navigation.test.tsx
git commit -m "fix(mini-app): wire supported sidebar navigation"
```

### Task 3: 发布和 Telegram Desktop 验收

**Files:**
- Modify: `project-docs/08-implementation/evidence/stage09-desktop-workspace-handoff-2026-07-23.md`

- [ ] **Step 1: 在本地构建并生成下一枚原生 Stage09 release。**

```text
cd mini-app
npm.cmd run test:run
npm.cmd run build
```

- [ ] **Step 2: 复用 r24 的密封、预检、原子切换和 bounded readiness gate 发布新 release。**

不改 Telegram webhook、Bot 菜单、LLM、业务数据、旧 Docker、r24/r23 回滚工件。

- [ ] **Step 3: 记录脱敏证据并推送。**

记录 artifact id、HTTPS health/root/static、五项 systemd、回滚保留和用户 Desktop 验收结果；不记录 initData、ticket、cookie 或 runtime secret。
