# Stage07/Stage08 能力与 Mini App 对齐审计（Stage09 发布前）

## Status

- Latest Release Evidence: 2026-07-24 的 r28 已作为 Stage09 原生 current 发布；部署、健康检查、公开静态资源与未认证拒绝分支均有实测证据。真实 Telegram 身份下的交互式浏览器验收尚待重新交接，不能据此把 Stage07/Stage08 标为全量验收完成。完整记录见 `project-docs/08-implementation/evidence/stage09-workspace-reliability-remediation-2026-07-24.md`。
- Document status: active implementation directive
- Scope: 已实现的 Stage07 表格工作台与 Stage08 协作运行时，和当前 Mini App 的可发现、可操作、可验收程度对齐
- Current Progress: 2026-07-24 已完成源码、路由、测试和现有页面的第一轮交叉审计，并完成本地真实浏览器的桌面（1440px）和移动（390px）交互复验：表格操作中心、Stage08 安全协作和记忆只读工作台均可从实际入口打开。r26 静态版本已原子发布；`stage09.jiangtest1.online` 是当前主域名，历史 Telegram Main Mini App 的 `stage07.jiangtest1.online` 作为兼容入口，以独立且匹配域名的 TLS 证书服务同一份 r26 静态页面和原生 API。Telegram Desktop 的浏览器交接已从被宿主拦截的 `window.open()` 改为官方 `WebApp.openLink()` bridge；完整 Mini App 回归与发布后两个域名的公网验证均通过。真实 FastAPI/PostgreSQL 授权查询、真实 LLM 或 Telegram 身份验收仍需独立证据，本文件不是整阶段验收通过声明。
- Evidence levels:
  - `implemented-local`：受控服务/API、前端代码和自动化测试存在；未必已在真实 Telegram/生产浏览器验收。
  - `partial-local`：路径存在，但关键角色、失败分支或浏览器交互仍缺证据。
  - `not-implemented`：当前没有符合产品边界的服务/API/UI，不能用伪入口冒充已完成。

## 1. 审计结论

过去阶段的底层工作没有白费：表格、视图、模板导入、治理、数字员工、草稿确认、记忆、RAG、群上下文和 LangGraph 协作均已有可复用的受控实现。但是它们分散在 API、测试和少数工作台中，首页与导航没有形成用户可理解的“工作路径”。

本次实施按以下原则收口：

1. 先接入已有、受权限和审计保护的能力，不复制后端规则，也不让浏览器拼接原始 schema、SQL、权限或群聊文本。
2. 对真正缺失的 Base/Table/Field 生命周期、批量操作和导出，显式登记为下一模块；不把灰色按钮或静态样式当成交付。
3. 每个新入口都必须显示真实的加载、空态、拒绝、冲突或失败状态；没有权限时不提供虚假成功路径。
4. 群聊只作为服务端受权上下文。Mini App 只能看到安全的“是否作为证据使用”信号，不读取原始消息、片段、聊天 ID、绑定 ID 或上下文窗口。

## 2. 表格能力台账

| 能力 | 已有底层证据 | 当前 UI/状态 | 本次处理 |
| --- | --- | --- | --- |
| 浏览/切换 Workspace、Base、Table、View、分页记录 | `stage06_platform` 路由与 `BaseCanvas` | 已有，入口分散 | 在操作中心和导航中统一发现路径 |
| 新建空 Base（附首张表与默认 Grid） | `POST /workspaces/{id}/base-initializations` | `WorkspaceHome` 的“新建 Base” | 保留既有受控初始化，增加可发现说明 |
| 新建表 | `POST /bases/{id}/table-initializations` | Base 画布 `+` | 接入表格操作中心，不直连原始 primitive |
| 新建字段、关系、查找字段 | Field/F2 初始化路由与权限过滤 candidate 查询 | Base 画布存在入口 | 接入操作中心并保留字段权限约束 |
| 新建与配置 Grid/Kanban/Calendar/Form 视图 | View 初始化、presentation、成员授权路由 | `ViewBuilderPanel` | 接入操作中心，表达可用边界 |
| 新建/编辑记录及版本冲突重读 | Record service + `RecordDetailPanel` | 画布和详情存在 | 在操作中心形成“记录”入口 |
| CSV/XLSX 新建 Base 导入 | Stage06 模板/导入服务、预览、显式 commit | `TemplateImportHub` | 直接接入；后续真文件选择/提交进行浏览器验收 |
| CSV/XLSX 导入当前 Base | 同上 | Base “更多”菜单 | 接入操作中心，不重做导入协议 |
| 官方模板安装、保存自定义模板 | Template 服务、审计、幂等 | `TemplateImportHub`、`SaveTemplatePanel` | 直接接入并显示其真实状态 |
| Base 重命名/描述/归档/删除/复制 | 无符合当前安全边界的完整 API | `not-implemented` | 新生命周期模块，不用假入口代替 |
| Table 重命名/key 编辑/复制/归档/删除 | 无完整 API | `not-implemented` | 新生命周期模块 |
| Field 编辑/排序/删除 | 无完整 API | `not-implemented` | 新生命周期模块；须处理 View 影响 |
| View 复制/删除/恢复/改默认 | 无完整 API | `not-implemented` | 新生命周期模块 |
| 记录删除/归档/恢复 | 无用户级 API | `not-implemented` | 新生命周期模块 |
| CSV/XLSX/View 导出 | 无 API | `not-implemented` | 独立导出模块，先做权限/字段脱敏设计 |
| 勾选后批量编辑/删除 | UI checkbox 无状态、无 API | `not-implemented` | 独立 bulk 模块；不能把装饰性 checkbox 保留为可点击功能 |

## 3. 数字员工、协作与治理能力台账

| 能力 | 已有底层证据 | 当前 UI/状态 | 本次处理 |
| --- | --- | --- | --- |
| 数字员工创建、编辑授权、启动/暂停 | `stage07_digital_employee_management` | `DigitalEmployeeManagementWorkbench` | 接入统一协作入口与关系索引 |
| 安全草稿：总结、记录更新草稿、差异确认/拒绝 | Stage07 draft 路由、幂等、审计 | `DraftEmployeeHub` | 在首页、Base、协作结果形成连续入口 |
| 成员、字段权限、审计治理 | Governance read/write 路由 | 两个治理工作台 | 仅加强导航可发现性，不降级权限模型 |
| Assistant Context | Stage07 安全 contact/view/summary 投影 | `AssistantContextWorkbench` | 作为协作入口的低风险上下文选择器保留 |
| Team Bot 安全汇总 | Stage07 安全 selected view projection | `TeamBotWorkbench` | 接入协作入口；真实 Provider 质量另做验收 |
| Stage08 LangGraph 协作查询 | `POST /api/stage08/assistant/query`，严格 `AssistantQuerySafeView` | 无 Mini App | 本次新增受控协作工作台，只传 workspace、员工、意图、问题、可选当前记录 |
| Stage08 长期 Memory 查看/撤销 | `GET /api/stage08/memory`、受版本撤销路由 | 新增只读记忆工作台；当前列表安全投影没有可撤销的稳定 item/candidate 标识 | 已接入安全查看；撤销 UI 暂不实现，避免浏览器猜测标识或发出错误写入 |
| Stage08 RAG 重建 | `POST /api/stage08/knowledge/reindex`、ticket/audit | 新增知识边界说明；当前没有安全的知识源目录 API | 暂不提供来源 ID 输入框或重建按钮；待后端提供授权 source-directory projection 后再接入 |
| 群聊上下文 | 服务端私有 `Stage08GroupContextAuthorityFactory`、C2/C3 组合 | 无公开群聊 UI | 仅在协作结果显示安全 citation/status，不暴露消息或标识符 |
| 群聊—客户—项目—员工关系索引 | `BusinessContextRelation` 安全投影 | 首页已有但群入口只跳 Assistant Context | 修正为可操作的关系上下文选择/跳转，并保留服务端权威关系 |

## 4. 本次交付范围与顺序

### P0：已实现能力的可发现与可操作入口

- 新建 `TableOperationCenter`：把现有的 Base、表、字段、视图、记录、导入、模板能力按真实权限和场景收拢；点击复用现有面板与受控 API。
- 在首页、Base 画布和左侧导航保持同一语义，不能让用户必须猜测哪个图标可用。
- 继续保留未来扩展图标，但统一显示“即将上线”，无可点击的虚假跳转。

### P1：Stage08 协作工作台

- 建立 `CollaborationWorkbench`，用已有员工、当前 Workspace 和当前记录上下文调用协作 API。
- 渲染 `AssistantQuerySafeView` 的状态、答案、安全证据类别、降级码和草稿引用；不渲染 provider 输出、trace、私有 evidence 或身份标识。
- 结果若产生草稿，只跳转既有草稿确认流，不在协作页绕过确认。

### P2：记忆与知识源受控工作台

- 只读展示当前 actor 有权读取的长期记忆；明确“记忆不是业务事实，业务事实仍以表格实时读取为准”。
- 当前只读展示安全记忆投影，并明确业务事实仍由实时表格决定。因为安全列表没有撤销所需的稳定标识、后端也没有知识源目录投影，本包不提供撤销或重建写入按钮；不在页面加载时产生任何写入。

### P3：安全群上下文可见性

- 不增加原始群聊浏览器 API。
- 仅通过协作 SafeView citation `group_context` 与未来经过专门审查的 status 投影，告诉用户本次回答是否使用了已授权群聊上下文。

## 5. 非本包能力与后续模块

Base/Table/Field/View/Record 生命周期、复制、删除、归档、批量编辑和导出必须另立设计/契约/迁移模块。原因不是不重要，而是它们会改变 schema、数据保留、关联完整性、版本冲突、权限、审计和恢复语义。本包只先让已经实现的能力真正可用，避免以界面代替业务能力。

## 6. 验收标准

本包完成不能只靠组件测试。最低证据为：

1. 对新增客户端 transport 做类型/拒绝分支测试，对既有权限与草稿确认回归测试。
2. 本地真实 FastAPI + PostgreSQL + Mini App 浏览器至少覆盖：进入操作中心、新建受权对象入口、导入向导打开、协作只读结果、草稿跳转、无权/降级状态。
3. 部署后，在真实域名/Telegram Mini App 至少完成一条不暴露私有上下文的查询闭环；所有创建/导入/撤销等写入均保留审计或 ticket 证据。
4. 不把“页面存在”描述成“Stage07/Stage08 全部验收通过”。
