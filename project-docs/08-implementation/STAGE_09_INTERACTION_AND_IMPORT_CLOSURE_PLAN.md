# Stage09 交互与导入收口计划

## Status

### r33 online visual baseline — 2026-07-24

- Native release `stage09-p1-20260724-r33` passed the sealed-release, HTTPS/readiness and service-health gates.
- Fixed visual references remain in `evidence/design-references/stage09-feishu-bitable/`; the authorized online Home capture is retained at `evidence/screenshots/stage09-r33/workspace-home-browser-viewport.png`.
- The baseline uses only factual workspace counts and actual controlled entries. It deliberately does not fabricate records to imitate a populated Bitable grid.

### r34 import semantic-field closure — 2026-07-24

- The CSV fixture `evidence/stage09-ui-acceptance-sample.csv` is a retained, non-sensitive acceptance sample. It creates a separate `Stage09 UI 验收样例` Base only and must not modify existing customer data.
- Import inference now recognizes commonly named business columns: `状态` / `status` / `stage` are created as `status`; `优先级` / `priority` and other category columns are created as `single_select`. Number, date and checkbox inference remains unchanged.
- The Mini App mapping editor now exposes the portable field types that the backend already supports (`状态`、单选、多选、链接、邮箱、电话 included). Relation, lookup and formula remain intentionally excluded because they require a pre-existing schema rather than an import guess.
- Verification before deployment: backend import/API regression `20 passed`; Mini App import/API/grid regression `3 files / 31 tests`; production build passed. A real Telegram/browser commit remains a required separate evidence item, not substituted by these tests.
- r34 native deployment has completed its sealed-release, offline-migration, service-health, HTTPS and corrected root-level readiness gates. Browser control reached the real authorized Home but timed out before file selection; no import write was made and no success is claimed. Full redacted evidence: `evidence/stage09-r34-semantic-import-deployment-2026-07-24.md`.

### r37 real LLM quality closure — 2026-07-25

- r37 is the active native release. Its sealed-release, offline-migration, service-health and public readiness gates passed; r35 was rejected before activation because its archive accidentally contained a historical Stage07 environment example, while r36/r37 only package `deploy/stage09-native`.
- A fresh real OpenRouter 12-Case run passed `12 / 12`, with `9 / 9` Provider calls completed and no timeout. The run is synthetic-fixture safety/contract evidence, not a claim that real customer copy has been human-scored. Full Chinese report: `evidence/stage09-r37-real-llm-quality-2026-07-25.md`.
- Real browser import is now verified through the authorized Home → template/import panel → new Base → file-selection dialog. The final file upload and new acceptance Base commit remain blocked on the Chrome extension's file URL permission; no import write has occurred in this attempt.

- Document status: active implementation plan
- Visual source of truth: `project-docs/08-implementation/evidence/design-references/stage09-feishu-bitable/README.md` and its five retained reference images. UI changes must compare to the matching image rather than reconstructing the target from conversation history.
- Scope: 已上线 Mini App 中已经声明为可用的表格、模板、导入、导航、数字员工与协作入口的可操作性收口。
- Current Progress: 2026-07-25 r37 已将真实 OpenRouter 12-Case 安全/结构评测收口为 `12 / 12` 通过，并保留前两次失败的原因与修复证据。导入 UI 已在真实授权 Chrome 中走到文件选择步骤；隔离 CSV 的上传、字段映射、提交独立验收 Base、打开网格并核对状态/优先级色标签仍待完成，因此不能据此称为完整产品验收。

## 目标

## 2026-07-24 视觉真源与当前收口

- 五张图像参考已作为仓库受控资产保存于 `evidence/design-references/stage09-feishu-bitable/`；视觉验收必须用对应页面截图与该资产对照，不得仅依据长对话中的描述复刻。
- 线上 r32 已通过真实服务、HTTPS 与授权 Home 页面验证；对应截图保存于 `evidence/screenshots/stage09-r32/workspace-home-browser-viewport.png`。
- 该截图暴露了空队列场景下的密度与语义色不足。本次 r33 只补真实计数、真实入口及真实对象的状态色，不填造业务记录，也不修改权限、数据契约或写入边界。

用户不应逐个猜测页面是否可用。本包把“可点击”限定为以下三类结果：

1. 打开已存在的受控工作流，并能返回原位置；
2. 执行真实 API，明确显示成功、可恢复错误或权限拒绝；
3. 尚未实现的能力保留为“即将上线”，但不伪造跳转或成功。

不在本包新增 Base、Table、Field、View、Record 的生命周期 API，也不降低权限、审计、草稿确认或群聊上下文的保护边界。

## 已确认问题与根因

### 导入

- 真实生产请求已证实：文件预览 `200`，确认创建 `422`。
- `ImportJob.mapping` 在预览阶段由服务端保留为空数组；浏览器直接把该数组渲染为“字段映射”，导致用户无法检查或修改默认映射。
- 前端对未枚举的受控 API 错误只显示泛化“导入暂时无法继续”，隐藏了服务端拒绝类别，无法让用户修正输入。
- 导入提交会先持久化幂等占位，再在校验失败时回滚业务写入；占位没有被终止，后续相同幂等键只能得到 `idempotency_in_progress`。

### 交互

- 已有按钮大多能进入对应面板，但缺少统一的关闭、返回焦点、键盘退出与错误恢复行为。
- Base、表、视图、记录缺少同一套“当前对象操作”入口；用户必须记住工具栏的位置。
- 规划中模块当前为禁用图标或按钮，不能表达“存在但尚无后端契约”的明确边界。

## 实施范围

### I1：真实导入闭环

1. 导入预览收到空映射时，由已验证的 `detected_schema` 在客户端生成可编辑的默认标量映射；不上传原始文件以外的数据，不接受客户端自定义字段类型。
2. 默认 `table_key` 使用稳定、安全、可编辑的 ASCII key；保留中文数据表名称。用户输入不合法、重复或服务端拒绝时，在当前字段旁展示中文原因和稳定错误代码。
3. `422`、`409`、权限拒绝、预览过期和网络错误必须有不同文案与下一步；失败后表单、映射和焦点保持可继续编辑。
4. 服务端在导入提交失败时终止本次幂等占位，使同一键可安全重试；成功仍可重放原收据，冲突仍被拒绝。
5. 为 CSV、XLSX、中文表名、空映射、重复 key、字段映射错误、预览过期和重试分别建立自动化覆盖。

### I2：统一对象操作

1. Base 顶部、表标签和记录行提供一致的操作入口。已有可用动作只复用现有受控面板：打开、创建记录、配置视图、导入、保存模板、打开详情。
2. 鼠标右键在桌面端打开同一对象菜单；触屏端保留现有显式“更多”入口，不依赖长按。
3. `Escape` 关闭最顶层浮层，关闭后焦点回到触发按钮；所有菜单有可见焦点、`aria` 标签和空白处关闭行为。
4. 未实现的复制、归档、批量编辑、导出等不创建假 API。菜单中以禁用说明项显示其边界与后续方向。

### I3：导航与失败状态

1. 所有侧栏/底栏中可用入口必须抵达真实页面或工作台；规划入口显示“即将上线”并可说明，不静默无反应。
2. 加载、空数据、无权限、网络失败、冲突和成功状态均能返回、重试或继续编辑。
3. 所有新菜单和浮层在 390px、桌面 1440px 下可用；表格横向滚动只限于表格区域。

### I4：显式 AI 对话入口

1. 将已存在但语义含糊的“智能协作”统一呈现为“AI 对话”，同时保留它是由数字员工、授权工作区、群聊上下文、长期记忆和知识检索共同构成的业务协作，不伪装成无边界公共聊天。
2. 首页、侧栏和 Base 工具条均提供同一真实入口；首页以高可见度操作卡说明“选择数字员工后直接提问”，而不是只隐藏在右侧助手栏。
3. 在 Base 中以可收起的右侧 AI 面板呈现对话，保留用户的表格工作区；首页、团队 Bot 等没有 Base 主画布的页面可以使用同一受控面板的自适应呈现。面板打开即预选第一个已授权数字员工；用户仍可切换员工、选择只读分析或待确认草稿。会话内显示安全投影后的提问与回答历史，但每轮明确标注为“重新检索当前授权上下文”，不会声称把聊天原文写入长期记忆或自动带入未授权内容。
4. 保持现有 `/api/stage08/assistant/query`、权限复核、引用标签、草稿确认与审计边界；失败只显示受控文案和重试入口，不能泄露 provider、原始上下文或传输错误。
5. `Escape`、遮罩点击和关闭按钮都能退出对话，焦点返回入口；桌面和 Telegram 小屏均保留可见的输入区和提交按钮。

### I5：飞书式工作台体验升级

1. 以公开飞书多维表格的产品语法作为交互参考：左侧为有文字解释的对象导航，顶部保留 Base/表/视图层级，中央始终优先显示业务数据表，右侧只在需要时承载上下文、AI、导入或审查工作流。
2. 将“表格操作”升级为右侧受控操作抽屉：新建数据表、Excel/CSV 导入、模板、字段操作和保存模板按真实 API 能力呈现；未实现项明确为“即将上线”，不创造假操作。
3. 首页改为可继续处理的队列工作台：待确认事项、可访问 Base、AI 对话和最近业务对象有明确入口；不依赖空白页或隐藏侧栏作为主要功能发现方式。
4. Base 与团队 Bot 使用同一关系语言展示 `数字员工 → 已授权群聊 → 客户 → 项目`，每个业务对象可跳回既有详情/表格入口；群聊仅以受控上下文源和聚合事实出现，禁止把原文作为 UI 数据。
5. 视觉基线为白底/暖白画布、细灰分割线、深墨文字、单一蓝色主动作、轻量状态色、紧凑但不拥挤的表格行和 8px 圆角。禁止渐变、发光、堆叠大卡片、无意义装饰和未连接后端的假数据。

## 验收方法

### 自动化

- 每个新增交互先写失败测试，再做最小实现。
- 前端：导入组件、真实 App 流、对象菜单、键盘/焦点、侧栏/底栏入口。
- 前端对话：首页、侧栏和 Base 的 AI 对话入口；默认受权员工；多轮本地安全投影；关闭/焦点恢复；真实 API 调用参数与受控失败态。
- 后端：导入提交校验失败后的幂等重试、成功重放、冲突不写入。
- 运行受影响测试、稳定的完整 Mini App 测试命令、后端导入测试与生产构建。

### 浏览器与生产

1. 使用受控本地 fixture 逐条点击并截图：Home → Base → 表/视图/记录 → 右键菜单 → 导入预览 → 错误恢复 → 成功收据。
2. 真正的 Telegram 身份下，再执行一条最小 CSV/XLSX 导入：预览、可见映射、确认创建、Base 中打开新表。该操作会真实写入，必须有用户当前授权与审计证据。
3. 部署后读取状态码、审计计数和页面截图；不得读取或写入群聊原文、密钥、Cookie、导入文件原文或业务记录全文到证据文档。

## 完成标准

- 真实导入不再以泛化错误掩盖受控拒绝；用户可在原表单修正后继续。
- 同一个提交键在失败后不永久卡住；重复成功提交不重复写入。
- 所有当前“available”入口有真实终点、回退和失败状态；所有“planned”入口有明确非可用说明。
- 用户无需猜测 LLM 是否已接入：任何可访问工作区均可从首页、导航或 Base 进入“AI 对话”，并对已授权数字员工完成一次真实受控提问。
- 对象右键和工具栏操作语义一致，且不会绕过现有权限、审计和草稿确认。
- 测试、构建、浏览器截图与一次真实 Telegram 导入分别记录；在缺少真实写入证据时，不宣称上线验收完成。
