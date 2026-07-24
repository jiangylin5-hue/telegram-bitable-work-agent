# Stage09 r31 交互与导入收口发布证据

## Status

- Date: 2026-07-24
- Scope: 导入可恢复性、可发现的表格操作、记录右键菜单、浮层退出与规划入口说明。
- Git revision: `9eea078` (`fix(workbench): close import and interaction gaps`)
- Server release: `stage09-p1-20260724-r31`
- Result: 部署与自动化回归通过；真实 Telegram 身份浏览器验收未完成，不能标记为完整产品验收。

## 修复内容

1. `ImportWizard` 在服务端预览返回空映射时，从受控 `detectedSchema` 生成可编辑映射；中文字段名保持在数据表显示名，默认 `table_key` 使用安全 ASCII 值。
2. 导入失败会显示稳定、安全的错误代码与下一步，而不是泛化失败文本；`table_key` 冲突继续保留可编辑表单与焦点。
3. 导入业务校验或授权拒绝后，幂等记录会标记为 `failed`，同一请求键可安全重试；已完成请求仍只重放原收据。
4. 桌面端记录行、看板、日历和表单均支持右键打开“记录操作”；已可用动作复用现有详情页，未实现的复制/归档维持禁用说明，不创建假写入。
5. 导入与表格操作面板支持 `Escape`、点击面板外关闭；规划入口会说明“尚未上线且不会跳转”，不再静默无响应。

## 自动化与构建

| Check | Result |
| --- | --- |
| Mini App 新增/关键回归 | `24 passed`（导航、导入、表格操作） |
| Mini App 核心表格链路 | `30 passed`（建表、字段、记录、关联、右键） |
| Mini App 视图/模板/工作区链路 | `41 passed` |
| Mini App 数字员工/协作/记忆/治理链路 | `29 passed` |
| Mini App 全量 Vitest | `76 files / 315 tests passed`；Vitest 自身报告耗时 `59.27s` |
| Mini App production build | `tsc -b && vite build` passed |
| Backend 导入与幂等回归 | `20 passed` |

全量测试外层命令在 Vitest 输出通过结果后被 61 秒调用时限收尾；该限制没有改变 Vitest 已报告的 `76 files / 315 tests passed` 结果。

## 服务器发布证据

| Item | Result |
| --- | --- |
| 密封包 SHA-256 | `92707d9d42d5a404d79278a0e6d289cbe20fcc379088459d619b50e8991124c5` |
| Release layout/assets/native service/data checks | all passed |
| 固定 Alembic 离线校验 | passed，输出哈希 `72f3cd00b331b8afa10531908169683f40dccca2b9374886ec8583e8924de2f1` |
| Release manifest SHA-256 | `abdd6b3f2250af2c620350d54b54c82215ba8fe4637060581723878f3f4baa02` |
| 公网 JavaScript SHA-256 | `3cd83d9bf0a319ec6e3c7016213b6cf9a5fef13992cedf0203599856a05d9b50` |
| Current source / venv / static | all point to r31 |
| Static rollback target | r30 |
| API / worker / outbox | all `active` |
| Loopback `/health` | HTTP `200` |
| `stage07.jiangtest1.online` and `stage09.jiangtest1.online` root | HTTP `200` |

首次候选包因包含历史 `deploy/stage07-acceptance/runtime/.env.stage07-acceptance.example` 被密封布局检查拒绝。该候选从未成为 current，已清理；重新封装时排除历史 Stage07 资产后，r31 通过全部预检并切换。

## 浏览器与真实写入边界

已接管的 Chrome 工作台标签在发布后刷新时连续两次浏览器扩展超时，未执行任何提交、导入、Telegram 发送或业务记录写入。因此本证据不把真实 Telegram 身份下的点击、浏览器 handoff 或新导入表创建写成已通过。

服务器发布临时包、离线 SQL 与 manifest 均已清理。未修改 Docker、Stage03、80/443 所有权、Telegram webhook 或 BotFather 配置。
