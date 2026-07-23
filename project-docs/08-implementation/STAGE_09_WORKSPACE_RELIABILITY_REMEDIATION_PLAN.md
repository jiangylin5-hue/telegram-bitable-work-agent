# Stage09 工作台可靠性与体验收口实施计划

> **For agentic workers:** 必须按任务顺序执行；每个行为变更先写失败测试，再写最小实现，完成任务后执行该任务列出的验证命令。

## Status

- Document status: approved implementation plan
- Scope: 真实生产页面已暴露的导航死路、导入失败残留/500、错误不可恢复、桌面浏览器控件错位，以及已实现能力的可发现性与视觉收口
- User authorization: 2026-07-24，允许删除 Base `22` 中经核对为失败导入遗留的空表和两个空字段；不触及该 Base 的其他表或任何已有记录
- Current Progress: 已完成受授权的精确生产清理：Base `22` 中失败导入残留的空表 `42a1cfbf-09ae-42d3-bb35-097fa8df89b4` 及其 2 个空字段已删除，记录数复核为 0；import job 与其他业务数据未改动。Task 1–3 已完成并经独立审查通过：导入提交失败会回滚并提供安全、可恢复的中文提示；浏览器版不会渲染 Telegram 专属启动控件，任一可用导航会收起临时工作台并使在途请求失效，Team Bot 提供明确返回、加载、失败和空状态；桌面工作台具备 12px 留白、中文侧栏说明、真实表格操作入口及清晰的规划中边界。本轮尚未发布到生产或进行需要新建业务数据的真实浏览器导入提交；Task 4（发布和真实验收）进行中。

## Goal

让用户能从每个已实现的工作台返回、在桌面与 Telegram 中看见正确的入口、在导入冲突时得到可操作的提示；任何失败的导入均不得留下一张半成品表或转化为 500。

## Architecture

导入继续使用 Stage06 既有 preview → explicit commit 协议，不新增文件存储、权限绕过或浏览器端 SQL。服务层在写入前检查目标 Base 的 table key，API 层对所有 commit 失败执行数据库回滚并将 key 冲突翻译为稳定的 409 安全错误码；Mini App 仅显示该安全错误码对应的修复指引。

团队 Bot、草稿、协作、记忆和治理仍复用现有受权 API 与组件。其界面从遮住整个 shell 的“无退路覆盖层”调整为保留左侧导航和清晰返回操作的工作台表面；不把未实现的复制、归档、删除、导出和批量操作伪装成可用功能。

## Tech Stack

- FastAPI、SQLAlchemy 2.x、PostgreSQL 16、Alembic（本包不新增迁移）
- React、TypeScript、TanStack Query、Vitest、Testing Library、Tailwind CSS/Lucide
- 原生 systemd/Nginx 部署；不使用 Docker

## Global Constraints

- 保持表格优先：所有成功写入必须保留既有审计与受控服务边界。
- 不传递、展示或记录原始群消息、Provider trace、密钥、数据库凭据或未过滤业务数据。
- 所有中文面向用户；API、字段名、错误码与文件名保持英文稳定。
- `import_table_key_conflict` 是唯一新增可公开给 Mini App 的错误码；不得泄露数据库约束名、SQL、原始异常或已有表的内容。
- 失败提交必须回滚本次 table/field/record 写入；已持久化的 idempotency reserve 继续按既有协议处理。
- 对 Base `22` 的生产修复只能删除 table id `42a1cfbf-09ae-42d3-bb35-097fa8df89b4` 及其两个字段，并且操作前再次确认记录数为 `0`；不得删除 import job 或其他业务对象。
- 浏览器验收中的创建或导入提交须使用明确授权的受控测试数据；用户文件与业务数据不重新上传或提交，除非再次获得动作时确认。

## 已确认根因与证据

1. Team Bot 使用 `.assistant-context-backdrop` 全屏覆盖，`AppShell` 的 `WorkspaceLaunchControls` 又固定在更高层级；关闭按钮被覆盖，点击左侧导航也不会清除 `teamBotPanel`。这解释了“进去后无法返回”。
2. `ImportWizard.safeError()` 只保留文件格式/大小文案，所有 API 422/409/500 都退化为“导入暂时无法继续”。
3. `commit_import_endpoint()` 对 `PlatformValidationError` 调用 `_commit_if_sqlalchemy()`，而不是 rollback；真实请求在 03:52:41 形成 table 与两个 field 后返回 422。再次提交撞上 PostgreSQL `uq_tables_base_key`，未捕获的 `IntegrityError` 返回 500。
4. 生产只读核查确认该表有 `0` 条记录、`2` 个字段；因此它可被授权的精确清理，不影响任何业务记录。

## 文件职责映射

| 文件 | 责任 |
| --- | --- |
| `backend/app/services/stage06_templates.py` | 提交导入前的 table key 冲突检查；不创建重复表。 |
| `backend/app/api/routes/stage06_templates.py` | 失败 rollback、409 映射和稳定安全错误码。 |
| `backend/tests/unit/test_stage06_template_import_api.py` | API 冲突、失败不残留、正常导入回归。 |
| `mini-app/src/app/api.ts` | `import_table_key_conflict` 的安全错误码解析。 |
| `mini-app/src/app/ImportWizard.tsx` | 可恢复的冲突文案、定位 key 输入与提交锁。 |
| `mini-app/src/test/import-wizard.test.tsx` | 导入冲突可恢复的界面回归。 |
| `mini-app/src/app/App.tsx` | 导航切换时关闭临时工作台、只在 Telegram host 传递打开方式控件。 |
| `mini-app/src/app/AppShell.tsx` | 可见中文导航、真实入口与规划入口的分组。 |
| `mini-app/src/app/WorkspaceLaunchControls.tsx` | 非 Telegram 环境不渲染专注/浏览器交接控件。 |
| `mini-app/src/app/TeamBotWorkbench.tsx` | 明确返回入口、开始步骤、真实空/失败状态。 |
| `mini-app/src/styles.css` | 去除冲突的覆盖层规则，保持留白、可返回与桌面/移动响应式。 |
| `mini-app/src/test/app-shell-navigation.test.tsx`、`mini-app/src/test/team-bot-workbench.test.tsx`、`mini-app/src/test/workspace-launch-controls.test.tsx` | 导航、返回可见性、环境分支回归。 |
| `project-docs/08-implementation/evidence/` | 生产清理、构建、真实域名浏览器验收的脱敏证据。 |

---

### Task 1: 原子导入与冲突恢复

**Files:**
- Modify: `backend/app/services/stage06_templates.py`
- Modify: `backend/app/api/routes/stage06_templates.py`
- Modify: `backend/tests/unit/test_stage06_template_import_api.py`
- Modify: `mini-app/src/app/api.ts`
- Modify: `mini-app/src/app/ImportWizard.tsx`
- Modify: `mini-app/src/test/import-wizard.test.tsx`

**Consumes:** 既有 `Stage06TemplateImportUnitOfWork.list_tables(base_id)`、`PlatformValidationError`、`ApiError`。

**Produces:** API `409 {detail: {code: "import_table_key_conflict"}}`；失败 commit 不提交半成品资源；前端聚焦 `数据表 key` 并显示可编辑的恢复提示。

- [ ] **Step 1: 写失败的后端冲突测试**

```python
def test_stage06_template_import_commit_rejects_duplicate_table_key_without_new_resources() -> None:
    # 创建 Base、首张 key="customers" 表和一个 awaiting_confirmation import job。
    # 同 key commit 返回 409，且 tables/fields/records 数量均不变化。
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "import_table_key_conflict"
    assert len(uow.tables) == tables_before
    assert len(uow.fields) == fields_before
    assert len(uow.records) == records_before
```

- [ ] **Step 2: 运行失败测试，确认当前实现会错误地接受或抛出未处理异常**

Run: `python -m pytest backend/tests/unit/test_stage06_template_import_api.py -q`

Expected: 新增断言失败；现有正常 CSV/XLSX 测试仍是基线。

- [ ] **Step 3: 实现最小原子性修复**

```python
# stage06_templates.py, commit_import_job
if any(table.key == table_key for table in uow.list_tables(base.id)):
    raise PlatformValidationError("import_table_key_conflict", table_key)

# stage06_templates.py, _http_error
elif code in {"idempotency_conflict", "idempotency_in_progress", "import_table_key_conflict"}:
    status_code = 409

# commit endpoint except blocks
except (PlatformValidationError, Stage06AuthorizationError) as exc:
    _rollback_if_sqlalchemy(uow)
    raise _http_error(exc) from exc
except IntegrityError as exc:
    _rollback_if_sqlalchemy(uow)
    raise HTTPException(status_code=409, detail=error_detail("import_table_key_conflict", "import_table_key_conflict")) from exc
```

`_rollback_if_sqlalchemy()` 必须与现有 route helpers 一致：若 UoW 没有 SQLAlchemy session 则不做任何事；不得提交失败的业务资源。

- [ ] **Step 4: 写失败的 Mini App 冲突测试**

```tsx
test('keeps the preview editable after a table-key conflict', async () => {
  const onCommit = vi.fn().mockRejectedValue(new ApiError(409, 'import_table_key_conflict'))
  // 完成 preview，提交后断言：错误明确提示 key 已存在、key input 仍可编辑、不会显示成功状态。
  expect(await screen.findByRole('alert')).toHaveTextContent('数据表 key 已存在')
  expect(screen.getByLabelText('数据表 key')).toBeEnabled()
  expect(screen.queryByText('已创建数据表')).not.toBeInTheDocument()
})
```

- [ ] **Step 5: 运行 Mini App 失败测试**

Run: `npm.cmd test -- --run src/test/import-wizard.test.tsx`

Expected: 新增测试因错误码未被公开解析、界面回退为通用文案而失败。

- [ ] **Step 6: 实现安全错误码与可恢复 UI**

```tsx
// api.ts
| 'import_table_key_conflict'

// ImportWizard.tsx
if (caught instanceof ApiError && caught.code === 'import_table_key_conflict') {
  setError('数据表 key 已存在。请修改 key 后再次确认创建。')
  tableKeyInputRef.current?.focus()
  return
}
```

通用 409 必须显示“请求发生冲突，请刷新后重试”；422 的已知导入错误码使用对应中文原因；未知错误才保留通用文案。不得显示约束名或原始异常。

- [ ] **Step 7: 运行 Task 1 回归**

Run: `python -m pytest backend/tests/unit/test_stage06_template_import_api.py -q; npm.cmd test -- --run src/test/import-wizard.test.tsx src/test/template-import-api.test.ts src/test/import-flow.test.tsx`

Expected: 全部通过。

- [ ] **Step 8: 提交 Task 1**

```powershell
git add backend/app/services/stage06_templates.py backend/app/api/routes/stage06_templates.py backend/tests/unit/test_stage06_template_import_api.py mini-app/src/app/api.ts mini-app/src/app/ImportWizard.tsx mini-app/src/test/import-wizard.test.tsx
git commit -m "fix(import): make commit atomic and recoverable"
```

### Task 2: 可返回工作台与正确环境入口

**Files:**
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/AppShell.tsx`
- Modify: `mini-app/src/app/WorkspaceLaunchControls.tsx`
- Modify: `mini-app/src/app/TeamBotWorkbench.tsx`
- Modify: `mini-app/src/test/app-shell-navigation.test.tsx`
- Modify: `mini-app/src/test/workspace-launch-controls.test.tsx`
- Modify: `mini-app/src/test/team-bot-workbench.test.tsx`

**Consumes:** 既有 `navigationRoute`、各面板关闭 callback、Telegram `readTelegramMiniAppLaunch()` 和 `TelegramFullscreenState`。

**Produces:** 桌面工作台没有 Telegram 专属控件；可用导航项切换后关闭覆盖层；每个工作台顶部都有“返回工作区”与关闭；左侧导航显示中文名称和说明。

- [ ] **Step 1: 写失败的导航与 host 分支测试**

```tsx
test('does not render Telegram launch controls outside Telegram', () => {
  render(<WorkspaceLaunchControls telegramState={null} onOpenBrowser={vi.fn()} />)
  expect(screen.queryByLabelText('工作台打开方式')).not.toBeInTheDocument()
})

test('renders a visible return action in the Team Bot workbench', () => {
  render(<TeamBotWorkbench {...props} />)
  expect(screen.getByRole('button', { name: '返回工作区' })).toBeVisible()
})
```

在 `App` flow 测试中增加：打开 Team Bot 后触发 `onNavigate('bases')`，Team Bot workbench 不再存在且 Base directory 可见。

- [ ] **Step 2: 运行失败测试**

Run: `npm.cmd test -- --run src/test/app-shell-navigation.test.tsx src/test/workspace-launch-controls.test.tsx src/test/team-bot-workbench.test.tsx src/test/team-bot-app-flow.test.tsx`

Expected: 新测试失败，因为当前浏览器环境仍渲染 launch controls，Team Bot 没有返回按钮，导航不会关闭 panel。

- [ ] **Step 3: 实现最小状态收口**

```tsx
// App.tsx
function dismissTransientWorkbenches(): void {
  teamBotRequestVersion.current += 1
  setTeamBotPanel(undefined)
  setDraftEmployeePanel(undefined)
  setAssistantContextPanel(undefined)
  setCollaborationPanel(undefined)
  setMemoryPanel(undefined)
  setGovernancePanel(undefined)
  setGovernanceWritePanel(undefined)
}

function selectNavigation(route: AppShellRoute) {
  dismissTransientWorkbenches()
  // 继续既有 canvas / builder 清理与 route 加载
}
```

`AppShell` 只在 `isTelegramMiniApp === true` 时渲染 `WorkspaceLaunchControls`。`TeamBotWorkbench` 的返回按钮调用既有 `onClose`，且 header 语义清晰；其他同类工作台沿用同一关闭/返回模式。规划入口保留，但移动到“规划中”分组并显示中文标签，不再伪装成主操作。

- [ ] **Step 4: 运行 Task 2 回归**

Run: `npm.cmd test -- --run src/test/app-shell-navigation.test.tsx src/test/workspace-launch-controls.test.tsx src/test/team-bot-workbench.test.tsx src/test/team-bot-app-flow.test.tsx src/test/workbench-layout.test.tsx`

Expected: 全部通过；现有 Mini App 行为未被删除。

- [ ] **Step 5: 提交 Task 2**

```powershell
git add mini-app/src/app/App.tsx mini-app/src/app/AppShell.tsx mini-app/src/app/WorkspaceLaunchControls.tsx mini-app/src/app/TeamBotWorkbench.tsx mini-app/src/test/app-shell-navigation.test.tsx mini-app/src/test/workspace-launch-controls.test.tsx mini-app/src/test/team-bot-workbench.test.tsx mini-app/src/test/team-bot-app-flow.test.tsx
git commit -m "fix(workspace): make workbenches navigable"
```

### Task 3: 视觉密度与真实能力发现路径

**Files:**
- Modify: `mini-app/src/styles.css`
- Modify: `mini-app/src/app/WorkspaceHome.tsx`
- Modify: `mini-app/src/app/TableOperationCenter.tsx`
- Modify: `mini-app/src/app/TeamBotWorkbench.tsx`
- Modify: `mini-app/src/test/workbench-layout.test.tsx`
- Modify: `mini-app/src/test/table-operation-center.test.tsx`

**Consumes:** Task 2 的返回和导航结构、既有 `TableOperationCenter` capability registry。

**Produces:** 留有 12px 外框的桌面 surface、可读中文左栏、真实表格操作入口、Team Bot 引导与真实空态；所有未实现功能仍是不可触发的“规划中”状态。

- [ ] **Step 1: 写失败的真实入口与视觉结构测试**

```tsx
test('shows visible Chinese labels for desktop navigation actions', () => {
  render(<AppShell {...props} />)
  expect(screen.getByRole('button', { name: 'Bases：浏览和打开多维表格' })).toHaveTextContent('Bases')
  expect(screen.getByText('浏览和打开多维表格')).toBeVisible()
})

test('keeps planned table lifecycle entries disabled and labels them as planned', () => {
  render(<TableOperationCenter scope={{ kind: 'workspace' }} actions={{}} onClose={vi.fn()} />)
  expect(screen.getByRole('button', { name: '导出 CSV / XLSX' })).toBeDisabled()
  expect(screen.getByText('即将上线')).toBeVisible()
})
```

- [ ] **Step 2: 运行失败测试**

Run: `npm.cmd test -- --run src/test/workbench-layout.test.tsx src/test/table-operation-center.test.tsx src/test/app-shell-navigation.test.tsx`

Expected: 当前 icon-only desktop sidebar 和 Team Bot 空白布局不满足新可见结构断言。

- [ ] **Step 3: 实现设计收口**

以现有 token 和 Lucide 图标为基线，做以下限定改动：

```css
/* desktop shell: 保留工作切换留白与可见导航文案 */
.app-shell { min-height: 100dvh; padding: 12px; background: #f4f6f9; }
.desktop-sidebar { width: 188px; border: 1px solid var(--line-subtle); border-radius: 12px; }
.app-content { margin-left: 200px; min-height: calc(100dvh - 24px); }
.nav-item { justify-content: flex-start; gap: 10px; padding: 0 12px; }
.nav-item span { position: static; width: auto; height: auto; clip: auto; }
```

主页只添加由现有 callback 驱动的“继续处理”操作卡和当前 Base/草稿/协作状态，不添加虚构 KPI。Team Bot 在未选择员工时显示 1→2→3 的可操作引导；选择后保持现有授权 view 选择与审计列。所有 CSS 覆盖规则必须收敛为一个最终定义，删除或替换造成同一 selector 互相矛盾的旧覆盖。

- [ ] **Step 4: 运行 Task 3 回归和生产构建**

Run: `npm.cmd test -- --run src/test/workbench-layout.test.tsx src/test/table-operation-center.test.tsx src/test/app-shell-navigation.test.tsx src/test/team-bot-workbench.test.tsx; npm.cmd run build`

Expected: 全部通过，Vite build exit code 为 0。

- [ ] **Step 5: 提交 Task 3**

```powershell
git add mini-app/src/styles.css mini-app/src/app/WorkspaceHome.tsx mini-app/src/app/TableOperationCenter.tsx mini-app/src/app/TeamBotWorkbench.tsx mini-app/src/test/workbench-layout.test.tsx mini-app/src/test/table-operation-center.test.tsx mini-app/src/test/app-shell-navigation.test.tsx
git commit -m "feat(workspace): refine actionable desktop experience"
```

### Task 4: 受控生产修复、发布与真实验收

**Files:**
- Create: `project-docs/08-implementation/evidence/stage09-workspace-reliability-remediation-2026-07-24.md`
- Modify: `project-docs/08-implementation/STAGE_09_CAPABILITY_UI_RECONCILIATION_AUDIT.md`

**Consumes:** Task 1–3 的已提交分支、用户对精确清理的授权。

**Produces:** 精确清理回执、部署版本/哈希、真实域名浏览器逐项结果、未完成项目列表。

- [ ] **Step 1: 再次只读核查目标资源**

Run through the server’s local PostgreSQL socket:

```sql
SELECT count(*) AS records FROM records WHERE table_id = '42a1cfbf-09ae-42d3-bb35-097fa8df89b4';
SELECT count(*) AS fields FROM fields WHERE table_id = '42a1cfbf-09ae-42d3-bb35-097fa8df89b4';
```

Expected: `records = 0` and `fields = 2`; any other result stops deletion and is reported.

- [ ] **Step 2: 在一个事务中删除精确半成品**

```sql
BEGIN;
DELETE FROM fields WHERE table_id = '42a1cfbf-09ae-42d3-bb35-097fa8df89b4';
DELETE FROM tables
WHERE id = '42a1cfbf-09ae-42d3-bb35-097fa8df89b4'
  AND base_id = '6a99b4be-10fc-43ee-86e2-315ab7fa350d';
COMMIT;
```

立即只读确认 table/field 均为 `0`，records 仍为 `0`。不得删除 import job、Base `22` 的默认表或其他资源。

- [ ] **Step 3: 部署已验证的静态包和 Python release**

先推送当前 branch；服务器创建新的 sealed release、安装后端依赖、执行现有 migration check、重启仅 `stage09-p1-api`，再原子切换静态 `current`。不改 Docker、80/443 所有权、Telegram webhook、BotFather URL 或 Nginx host 结构。

- [ ] **Step 4: 实际浏览器验收**

在 `stage09.jiangtest1.online` 和 Telegram 兼容入口依次验证并保存截图：

1. Home → Bases → Home；每次内容切换且无覆盖层遗留。
2. Home → 团队 Bot → 返回工作区；左侧导航仍可用。
3. Home → 表格操作中心 → 导入向导 → 取消；返回原页面。
4. 导入冲突以 409 显示可编辑 key（使用受控测试 job，不提交真实用户文件）。
5. 团队 Bot、草稿、协作、记忆、治理的每个已有入口都有加载/空/失败或真实内容状态；规划入口保持不可触发且有说明。
6. 1440px 桌面和 390px Telegram Mini App 各检查一次；桌面不显示 Telegram 专属控件。

- [ ] **Step 5: 写入证据、更新阶段进度并提交文档**

文档必须分别写明：通过项、失败项、未测项、截图文件、命令、发布 release、静态哈希，以及“生命周期/导出/批量操作仍未实现”。不得将本包写成 Stage07、Stage08 或生产功能全量验收通过。

## Self-Review

- Spec coverage: Task 1 覆盖导入原子性和可恢复错误；Task 2 覆盖返回、路由和错误 host 控件；Task 3 覆盖视觉质量、可发现性和保留规划入口；Task 4 覆盖已授权精确清理、发布和真实验收。
- Boundary coverage: 未实现的生命周期、导出、批量操作没有被伪造；群上下文、Provider trace 和原始业务文件不向浏览器泄露。
- Data protection: 生产删除的 object id、Base id、字段数和记录数均已锁定；任何数量变化均停止操作。
