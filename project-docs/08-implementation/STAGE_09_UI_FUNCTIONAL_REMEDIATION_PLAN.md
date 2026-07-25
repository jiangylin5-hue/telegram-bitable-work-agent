# Stage09 UI 功能完整性修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已上线工作台中“看得到但不完整可操作”的导入、对象菜单、关系跳转、浮层退出与全量前端回归收口为真实、可恢复、可验证的工作流。

**Architecture:** 保持现有 FastAPI、权限投影、React App 状态与受控写入边界不变。导入仍只能通过现有 Preview → Commit API；前端只在服务端 `commit` 收据成功后报告持久化成功，并把后续回读/跳转失败降级为可恢复的导航提示。所有新对象操作只复用已有受控面板和 API，未实现能力仍必须禁用并标注“即将上线”。

**Tech Stack:** React + TypeScript + Vitest + Testing Library、FastAPI/SQLAlchemy、Nginx。

## Global Constraints

- 不修改 Telegram、群聊原文、权限模型、审计模型或 Stage03 Docker。
- 不新增伪造 API；复制、归档、批量编辑、导出仍是禁用的计划项。
- 真实写入只允许受控的既有导入/创建 API；测试数据必须使用既有非敏感 Stage09 fixture。
- 文案使用中文；错误不得泄露 Cookie、Provider、原始请求体或数据库异常。
- 每项先写失败测试，再做最小修复；提交前运行覆盖该项的前后端测试。
- 真实 Chrome/Telegram 导入证据仍须由可用的浏览器控制连接完成，不能用模拟测试替代。

---

## 文件与职责

| 文件 | 职责 |
| --- | --- |
| `deploy/stage09-native/nginx/stage09-p1-public-https.conf.template`、`deploy/stage09-native/nginx/stage09-p1.conf.template` | 公网与内部入口的导入请求体上限，必须覆盖 Base64 后的 10 MiB XLSX。 |
| `mini-app/src/app/ImportWizard.tsx` | 文件预览、可恢复错误与 commit 成功状态。 |
| `mini-app/src/app/App.tsx` | commit 收据、后续回读/打开失败的降级，以及 Base 中关系跳转。 |
| `mini-app/src/app/template-import-types.ts` | 前端展示用的 commit 后导航状态类型。 |
| `backend/app/api/routes/stage06_templates.py`、`backend/app/services/stage06_templates.py` | 损坏 XLSX、无效 source key、超长/非法表 key 的受控校验。 |
| `mini-app/src/app/BaseCanvas.tsx`、`mini-app/src/styles.css` | Base/表右键和显式更多菜单、关系索引按钮及可见焦点。 |
| `mini-app/src/app/TemplateImportHub.tsx`、`mini-app/src/app/BuilderCreatePanel.tsx` | Escape、遮罩关闭、焦点归还。 |
| `mini-app/package.json` | 固定可重复的串行回归命令。 |

### Task 1: 导入真实成功与可恢复失败

**Files:**
- Modify: `deploy/stage09-native/nginx/stage09-p1-public-https.conf.template`
- Modify: `deploy/stage09-native/nginx/stage09-p1.conf.template`
- Test: `deploy/stage09-native/scripts/test-native-service-assets.sh`
- Modify: `mini-app/src/app/ImportWizard.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/template-import-types.ts`
- Test: `mini-app/src/test/import-wizard.test.tsx`
- Test: `mini-app/src/test/import-flow.test.tsx`
- Test: `mini-app/src/test/template-import-api.test.ts`

**Interfaces:**
- Consumes: `api.commitImport(jobId, values, idempotencyKey): Promise<ImportCommitReceipt>`。
- Produces: `ImportCommitReceipt` 可选 `navigationWarning?: string`，只表示后续打开 Base 失败，绝不否定已持久化的导入。

- [ ] **Step 1: 写失败测试：已提交后回读失败仍显示成功收据**

```tsx
await expect(commitImport('job-1', values)).resolves.toMatchObject({
  baseId: 'base-1',
  tableId: 'table-1',
  navigationWarning: expect.stringContaining('已创建'),
})
```

- [ ] **Step 2: 写失败测试：401/403 导入错误给出会话/权限中文下一步**

```tsx
expect(await screen.findByRole('alert')).toHaveTextContent('浏览器会话已失效')
expect(await screen.findByRole('alert')).toHaveTextContent('当前身份没有导入权限')
```

- [ ] **Step 3: 实现最小前端修复**

```ts
const receipt = await api.commitImport(importJobId, values, crypto.randomUUID())
try { await refreshAndOpenCommittedBase(receipt) }
catch { return { ...receipt, navigationWarning: '数据表已创建；暂时无法自动打开，可从 Bases 重新进入。' } }
return receipt
```

`safeError` 必须将 `401` 映射为“浏览器会话已失效，请从 Telegram 重新打开工作台后重试”，将 `403` 映射为“当前身份没有导入权限”。`ImportWizard` 成功区展示 `navigationWarning`，但不再显示“导入暂时无法继续”。

- [ ] **Step 4: 显式设置 Nginx 请求体上限**

```nginx
client_max_body_size 16m;
```

将该行置于两个模板的 `server` 内、任何 `location` 之前；16 MiB 必须覆盖 10 MiB XLSX 的 Base64 请求体与 JSON 包装。`test-native-service-assets.sh` 必须断言渲染后的内部 Nginx 配置含有该指令。

- [ ] **Step 5: 运行测试并提交**

Run: `npm.cmd test -- --run src/test/import-wizard.test.tsx src/test/import-flow.test.tsx src/test/template-import-api.test.ts --maxWorkers=1`

Expected: all passing.

### Task 2: 服务端导入输入归一化

**Files:**
- Modify: `backend/app/api/routes/stage06_templates.py`
- Modify: `backend/app/services/stage06_templates.py`
- Test: `backend/tests/unit/test_stage06_template_import.py`
- Test: `backend/tests/unit/test_stage06_template_import_api.py`
- Test: `backend/tests/unit/test_stage06_import_limits.py`

**Interfaces:**
- Consumes: 当前 `ImportJob.detected_schema` 与 commit `field_mapping`。
- Produces: 损坏 XLSX、未知 `source_key`、非法/超长表 key 统一返回已白名单的 `PlatformValidationError` / 422。

- [ ] **Step 1: 写失败测试**

```python
assert response.status_code == 422
assert response.json()['detail']['code'] in {
    'invalid_excel_file', 'invalid_import_mapping', 'invalid_table_key'
}
```

覆盖损坏 ZIP/XLSX、`field_mapping.source_key` 不在 `detected_schema`、超过 120 字符和不符合稳定 key 规则的 `table_key`。

- [ ] **Step 2: 实现最小服务端校验**

```python
if mapping.source_key not in detected_keys:
    raise PlatformValidationError('invalid_import_mapping')
if not TABLE_KEY_RE.fullmatch(table_key) or len(table_key) > 120:
    raise PlatformValidationError('invalid_table_key')
```

捕获 `zipfile.BadZipFile` 与 `xml.etree.ElementTree.ParseError` 并转换为 `PlatformValidationError('invalid_excel_file')`，不得透出解析异常原文。

- [ ] **Step 3: 运行测试并提交**

Run: `python -m pytest -q backend/tests/unit/test_stage06_template_import.py backend/tests/unit/test_stage06_template_import_api.py backend/tests/unit/test_stage06_import_limits.py`

Expected: all passing.

### Task 3: Base/表统一对象菜单与关系跳转

**Files:**
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/styles.css`
- Test: `mini-app/src/test/record-context-menu.test.tsx`
- Test: `mini-app/src/test/base-canvas-management.test.tsx`
- Test: `mini-app/src/test/workbench-layout.test.tsx`

**Interfaces:**
- Consumes: `onOpenTableOperations`、`onImportIntoBase`、`onSaveTemplate`、`onOpenRecord`、`openBusinessRecordReference`、`openBusinessEmployeeReference`、`openAssistantContext`。
- Produces: Base/表/记录的右键与显式“更多”入口共用真实受控动作；每个可点击关系对象调用已有跳转函数。

- [ ] **Step 1: 写失败测试：Base/表右键、键盘菜单与显式更多入口**

```tsx
fireEvent.contextMenu(screen.getByRole('heading', { name: 'CRM' }))
expect(screen.getByRole('menu', { name: 'Base 操作' })).toBeVisible()
fireEvent.keyDown(screen.getByRole('tab', { name: 'Customers' }), { key: 'ContextMenu' })
expect(screen.getByRole('menu', { name: '数据表操作' })).toBeVisible()
```

验证菜单仅调用 `onOpenTableOperations`、`onImportIntoBase`、`onSaveTemplate`、`onCreateRecord`、`onCreateField` 等已有 handler，复制/归档仍 `disabled`。

- [ ] **Step 2: 写失败测试：Base 内每个关系对象可进入既有终点**

```tsx
fireEvent.click(screen.getByRole('button', { name: '打开客户记录 明日璀璨' }))
expect(onOpenRecordReference).toHaveBeenCalledWith(relation.customer)
```

员工调用现有员工详情 handler；群聊调用受控 Assistant Context；客户和项目调用现有记录引用跳转。不得渲染原始群聊文本。

- [ ] **Step 3: 实现最小菜单与关系按钮**

```tsx
<button onContextMenu={(event) => openObjectMenu(event, { kind: 'table', table: item })}>
  <Table2 size={16} />{item.name}<ChevronDown size={14} />
</button>
```

菜单使用 `role="menu"`/`role="menuitem"`、Escape、遮罩点击关闭和触发元素焦点归还；表标签上的 `ChevronDown` 必须打开同一菜单，不能再只是装饰。关系索引使用已有 `WorkspaceHome` 同名 aria-label 与 handler。

- [ ] **Step 4: 运行测试并提交**

Run: `npm.cmd test -- --run src/test/record-context-menu.test.tsx src/test/base-canvas-management.test.tsx src/test/workbench-layout.test.tsx --maxWorkers=1`

Expected: all passing.

### Task 4: 浮层退出一致性与可重复全量回归

**Files:**
- Modify: `mini-app/src/app/TemplateImportHub.tsx`
- Modify: `mini-app/src/app/BuilderCreatePanel.tsx`
- Modify: `mini-app/src/test/setup.ts`
- Modify: `mini-app/vitest.config.ts`
- Modify: `mini-app/package.json`
- Test: `mini-app/src/test/template-app-flow.test.tsx`
- Test: `mini-app/src/test/builder-create-panel.test.tsx`

**Interfaces:**
- Consumes: 每个面板的 `onClose()`。
- Produces: Template Hub 与 Builder 面板支持 Escape、遮罩关闭、关闭后焦点归还；`test:run` 使用固定单 worker。

- [ ] **Step 1: 写失败测试**

```tsx
fireEvent.keyDown(document, { key: 'Escape' })
expect(onClose).toHaveBeenCalledTimes(1)
expect(trigger).toHaveFocus()
```

遮罩点击需关闭未提交的面板；正在安装/保存时不得透过遮罩关闭。

- [ ] **Step 2: 实现最小关闭协议**

```tsx
useEffect(() => {
  const closeOnEscape = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
  document.addEventListener('keydown', closeOnEscape)
  return () => document.removeEventListener('keydown', closeOnEscape)
}, [onClose])
```

以现有 `ImportWizard` / `TableOperationCenter` 的模式实现；关闭回调在 `App.tsx` 保持现有触发元素引用和 focus 恢复。

- [ ] **Step 3: 固定全量回归命令**

```json
"test:run": "vitest run --no-file-parallelism --maxWorkers=1"
```

Vitest 配置必须显式保留 `isolate: true`，测试 setup 在每个用例后调用 Testing Library `cleanup()`；不得通过把 `testTimeout` 增大或使用 `--no-isolate` 来掩盖异步残留。默认开发 `test` 保持 watch 行为。

- [ ] **Step 4: 全量验证并提交**

Run: `npm.cmd run test:run`

Expected: all Mini App test files and tests passing without并发超时。

### Task 5: 分支级审查阻断项修复

**Scope:** 修复最终分支审查发现的五项可上线阻断：表格操作中心子层叠放、导入字段映射原子校验、模板安装 pending 关闭、模板焦点生命周期、无管理权限时的数字员工关系入口。

**Files:**

- Modify: `mini-app/src/app/App.tsx`
- Modify: `mini-app/src/app/TableOperationCenter.tsx`
- Modify: `mini-app/src/app/TemplateImportHub.tsx`
- Modify: `mini-app/src/app/BaseCanvas.tsx`
- Modify: `mini-app/src/styles.css`
- Modify: `mini-app/src/test/table-operation-center.test.tsx`
- Modify: `mini-app/src/test/template-app-flow.test.tsx`
- Modify: `mini-app/src/test/workbench-layout.test.tsx`
- Modify: `backend/app/services/stage06_templates.py`
- Test: `backend/tests/unit/test_stage06_template_import.py`
- Test: `backend/tests/unit/test_stage06_template_import_api.py`

**Root causes:**

1. `TableOperationCenter` 的 `suspended` 条件只覆盖模板、Base Builder 与 Table Builder，未覆盖字段 Builder、视图 Builder、记录详情/创建面板；父抽屉仍可覆盖和响应子层。
2. 导入提交在创建 Base/Table 前只校验 `target_key` 非空和不重复，缺少稳定 key 规则及 120 字符上限、字段展示名 160 字符上限；真实 PostgreSQL 可能在写入中途才失败。
3. `TemplateImportHub` 只阻止 Escape/遮罩关闭，右上角关闭按钮在 `installingId` 存在时仍然可触发 `onClose()`。
4. 保存模板入口未保存准确的 return-focus trigger，`TemplateImportHub` 打开时也未把焦点移入模态内容；从 suspended 抽屉打开时焦点可能停留在 `aria-hidden` 父层。
5. Base 业务关系中“打开数字员工”无条件走管理端点，读取权限用户可能触发 403 并切到 denied 状态。

**Interfaces:**

- Consumes: 当前 `TableOperationCenter` 的受控 action handlers、既有 `openTeamBot()` 只读协作入口、现有 `PlatformValidationError`。
- Produces: 任一表格操作子层均独占可点击/可访问顶层；非法导入映射在任何资源创建前稳定返回白名单 422；安装中所有关闭入口关闭；模板流具备正确初始焦点和准确 return-focus；员工关系入口不再触发越权管理 API。

- [ ] **Step 1: 先写失败测试，覆盖所有表格操作子层**

  - 从操作中心依次打开字段、视图、记录、模板、Base 与 Table 创建入口。
  - 断言子层在视觉/点击层级上可交互；父抽屉不再是 dialog/modal、不响应 Escape/遮罩、不暴露可操作控件；子层关闭后焦点返回实际 action trigger。

- [ ] **Step 2: 先写失败测试，覆盖真实 PostgreSQL 边界前的导入拒绝**

  - `target_key` 包含空格或不符合稳定 key 规则、超过 120 字符、字段名超过 160 字符时，断言 `422` 与 `invalid_import_mapping`。
  - 每一例均断言 Base/Table/Field/Record 数量不变，禁止部分资源创建。

- [ ] **Step 3: 先写失败测试，覆盖模板 pending 与焦点协议**

  - `installingId` 存在时 Escape、遮罩和关闭按钮均不得调用 `onClose()`。
  - 模板 Hub 打开后焦点进入 dialog 中可用控件；从 Home、Base 更多菜单与表格操作中心的模板入口关闭后，焦点返回对应 trigger。

- [ ] **Step 4: 先写失败测试，覆盖只读数字员工关系入口**

  - 没有 `can_manage_digital_employees` 的关系按钮不得调用管理 API；必须进入现有只读 Team Bot/授权上下文终点或明确提供不可编辑详情。
  - 有管理能力时保留既有管理入口；不得改变权限模型或吞掉 403。

- [ ] **Step 5: 最小修复与回归**

  - 使用一个明确的 child-overlay 状态判断覆盖所有上述子层；suspended 父抽屉保留回焦节点但为 `aria-hidden`、无 dialog/modal 语义、`pointer-events: none` 且层级低于子层。
  - 复用现有 table key 规则或稳定 regex，在 `_validate_field_mapping()` 资源创建前验证 key/name。
  - 关闭按钮遵循 pending guard；Template Hub 使用可见且未禁用的初始焦点。
  - 数字员工非管理访问复用现有 `openTeamBot` 只读端点，不新增 API；管理访问仍走管理端点。

- [ ] **Step 6: 验证并提交**

Run:

```text
python -m pytest -q backend/tests/unit/test_stage06_template_import.py backend/tests/unit/test_stage06_template_import_api.py backend/tests/unit/test_stage06_import_limits.py
npm.cmd run test:run
npm.cmd run build
```

Expected: 后端导入边界与全量前端串行回归均通过；不存在 timeout 扩容或 `--no-isolate` 绕过。

## 验收

1. Nginx 模板允许 16 MiB 请求体；接近上限的合法 XLSX 不会被反向代理提前 413。
2. 导入 commit 已写入后，即使刷新/打开 Base 失败，UI 仍明确显示“已创建”与后续跳转提示。
3. Base、表、记录均有一致的显式或右键对象菜单；每项可用动作可到达受控终点。
4. Base 内员工、群聊、客户、项目均可跳转，且只使用受权聚合关系。
5. Template Hub 与创建面板符合 Escape、遮罩、焦点恢复协议。
6. `npm.cmd run test:run` 可稳定通过；真实 Chrome/Telegram 受控 CSV/XLSX 提交另行保留证据，绝不伪称已通过。

## Current Progress

- 2026-07-25：计划已基于真实 UI 审计、导入代码追踪和全量前端回归发现建立。
- Task 1 complete：`88e5ef4`、`5604cd5`。聚焦前端 21/21、相邻 denied/session 15/15、两个原生 Nginx asset 测试与生产构建均通过；二次独立审查 0 Critical / 0 Important / 0 Minor。真实浏览器写入未执行。
- Task 2 complete：`943e0cf`、`959e640`。导入聚焦后端测试 32 passed，包含坏 ZIP、坏 XML、未知 source key、非法/超长 key 与零 Base/Table/Field/Record 创建断言；独立复审无可行动问题。未运行全量后端测试，未做真实写入。
- Task 3 complete：`631531f`、`e82c02f`。Base/数据表对象菜单、业务关系跳转与多表目标绑定已完成；定向前端测试 3 files / 20 tests 通过，生产构建通过。首轮独立审查发现“未选中表菜单会误作用当前表”等 4 项问题，已修复并经 scoped re-review 判定 Spec PASS、Quality PASS；真实 Chrome/Telegram 菜单和导入写入证据仍待受控浏览器连接恢复后单独保留。
- Task 4 complete：`48ac636`、`8facb9a`、`f9ac2e1`。Template Hub、创建 Base/数据表面板与表格操作中心的 Escape、遮罩、焦点返回和子层叠放已统一；两轮独立复审分别拦截并修复了表格操作中心触发元素回焦、父抽屉覆盖子层/仍作为模态框的问题。最终 `npm.cmd run test:run` 为 76 files / 345 tests passed（225.78s），生产构建与 scoped diff check 通过；真实 Chrome/Telegram 导入写入仍未声称完成。
- 最终分支审查（`07af702..f9ac2e1`）发现 5 项 Important，Task 5 已创建并处于 in_progress：必须先消除所有阻断项，才可推送和部署。
- Task 5 complete：`424e016`、`09ca663`。最终审查的五项阻断均已修复，并在 Task 5 复审中额外发现“模板安装 pending 时仍可切换到新 Base”的入口，已按红绿测试修复。Task 5 的初始独立审查和 fix scoped re-review 均为 Spec PASS、Quality PASS；最终必须在当前 HEAD 重新运行后端导入边界、全量前端串行回归与生产构建，再执行推送和部署。
- 发布前重新验证（当前 HEAD `09ca663`）：后端导入边界 `40 passed in 9.88s`；前端串行隔离回归 `76 files / 353 tests passed in 228.18s`；`npm.cmd run build` 成功；`git diff --check 07af702..HEAD` 成功。待执行的仅为受控推送、服务器发布和真实浏览器/Telegram 写入证据，后者不可由自动化测试替代。
