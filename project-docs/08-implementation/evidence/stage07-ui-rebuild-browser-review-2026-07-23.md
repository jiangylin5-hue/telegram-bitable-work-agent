# Stage07 UI 重做：浏览器与视觉对照记录

## Status

- Evidence status: `executed_with_visible_delta_recorded`
- Date: 2026-07-23
- Surface: 本地、受控、脱敏 Mini App 视觉样例；不是公网 Mini App 部署证据
- Browser console: `error=0`, `warn=0`
- UI release acceptance: `partial`，原因见“可见差异”；不以截图或单测替代最终产品验收

## 1. 本轮实现范围

1. `WorkspaceHome` 现在以队列 / 最近 Base / 助理入口三栏呈现。队列的 Base 跳转只从真实 `destination.base_id` 与已加载 `recent_bases` 映射得到；缺失映射会明确显示“未在当前列表”，不伪造群聊、客户或员工关系。
2. `BaseCanvas` 保持表格为主要工作面，新增仅来自当前授权 Base、表、视图、可访问记录数和可见字段数的右侧上下文栏。
3. Team Bot、草稿审阅与数字员工管理从视觉模态框改为全尺寸工作台。三者改为非模态 `region` 语义，保留导航可用性，修复了“`aria-modal` 与可操作侧栏并存”的无障碍冲突。
4. 在 901–1080px 先行单列堆叠，避免桌面三栏最小宽度产生横向溢出；900px 以下保持全宽、逐栏阅读和 44px 关键按钮。
5. 移除 Home 中没有真实回调的“搜索、排序、快速查找、新建记录、全部”伪入口；已保留的 Base、草稿、团队 Bot 与受控摘要入口都由既有 ID/回调驱动。

## 2. 已保存的浏览器截图

截图均使用受控合成 DTO，不含真实业务数据或 Provider 原文。文件位于本报告同级目录下的 `stage07-ui-rebuild-2026-07-23/`：

| 截图 | 视口 | 覆盖面 |
| --- | --- | --- |
| `01-home-1440x900.png` | 1440×900 | 队列、真实 Base 映射入口、助理入口 |
| `02-base-1280x720.png` | 1280×720 | 高密度表格、授权上下文栏 |
| `03-team-bot-1440x900.png` | 1440×900 | 助手目录、授权视图、会话和审计 |
| `04-draft-1440x900.png` | 1440×900 | 字段级差异、显式确认/拒绝 |
| `05-employee-1440x900.png` | 1440×900 | 目录、范围配置、审计约束 |
| `06-draft-430x932.png` | 430×932 | 移动端草稿逐栏阅读 |
| `07-employee-390x844.png` | 390×844 | 移动端员工配置逐栏阅读 |
| `08-team-bot-1024x768.png` | 1024×768 | 中等宽度单列堆叠、无横向溢出 |

Home 的“查看草稿”入口在同一浏览器运行中已实际点击并进入草稿工作台；该入口不再只是静态链接。

## 3. 与已批准参考图的同图对照

每张对照图左侧为批准参考、右侧为当前实现（同一图像输入中并排），已人工查看：

- `comparison-01-home-reference-left-prototype-right.png`
- `comparison-02-base-reference-left-prototype-right.png`
- `comparison-03-team-bot-reference-left-prototype-right.png`
- `comparison-04-employee-reference-left-prototype-right.png`

可见的一致点：白色画布、冷灰分隔线、Azure 单主色、低圆角、三栏职责、表格/字段级信息优先，以及没有深色 AI 面板、渐变或卡片墙。

可见差异：参考图使用了大量队列、助手、表格行和活动数据；本地样例严格只提供三条队列、三条记录和一名员工。因此 Home、Base、Team Bot 下半部分仍比参考图空。该差异已如实保留：本轮没有为追求截图密度伪造不存在的群聊—客户—员工关系或生产数据。后续要消除这一差距，需要真实可授权的队列/多员工/活动数据供 UI 渲染，而不是再在前端硬编码展示项。

## 4. 代码与浏览器验证

本轮新增的前端回归包含：队列 Base 跳转、Base 上下文栏、三工作台结构、非模态语义和无回调入口隐藏。

已执行：

```text
npm.cmd test -- --run src/test/workbench-layout.test.tsx src/test/draft-employee-hub.test.tsx src/test/team-bot-workbench.test.tsx src/test/digital-employee-management-workbench.test.tsx
# 4 files, 14 tests passed

npm.cmd test -- --run
# 65 files, 236 tests passed

npm.cmd run build
# tsc -b && vite build passed
```

## 5. 结论与剩余项

本轮已经把原先的小弹窗/稀疏页面改为可用的工作台结构，修复了一个重要无障碍语义冲突和中间断点溢出风险，且不改变草稿确认、权限过滤、审计或后端合同。

仍不能宣称“与生成参考图像素级一致”或“完整 Stage07 UI 验收通过”：当前最大可见差距是受控样例数据密度，而公网域名目前也不是最新 Mini App 的部署证据。下一轮 UI 收口应优先接入真实的、授权过滤后的队列/员工/活动 DTO，再以相同参考图重新对照，而不是通过假数据掩盖问题。
