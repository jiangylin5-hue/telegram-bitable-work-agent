# Stage09 r40 回归与线上就绪检查（2026-07-26）

## Scope

本次检查在已部署的 `stage09-p1-20260725-r39` 基础上执行，只验证现有功能与线上可达性；不创建 Base、数据表、记录、导入任务或 Telegram 消息，不修改生产数据。

## 回归结果

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| Mini App 全量交互回归 | `npm.cmd run test:run` | `76 files / 353 tests passed`，耗时 `249.27s` |
| Mini App 生产构建 | `npm.cmd run build` | 通过；TypeScript 与 Vite 构建成功 |
| 导入、Mini App、关系跳转、助手上下文与 Team Bot 后端边界 | `python -m pytest -q backend/tests/unit/test_stage06_template_import.py backend/tests/unit/test_stage06_template_import_api.py backend/tests/unit/test_stage06_import_limits.py backend/tests/unit/test_stage07_mini_app_api.py backend/tests/unit/test_stage07_relation_lookup.py backend/tests/unit/test_stage07_assistant_context_api.py backend/tests/unit/test_stage07_team_bot_knowledge_api.py backend/tests/unit/test_stage07_draft_employee_hub_api.py` | `106 passed in 25.29s` |
| 公网根页 | `GET https://stage07.jiangtest1.online/` | HTTP `200`，429 bytes |
| 公网健康检查 | `GET https://stage07.jiangtest1.online/health` | HTTP `200`，`{"status":"ok"}` |
| 公网首页构建资源 | 首页引用 `index-ClvZQGCh.js`、`index-CBGJFEX0.css` | 两个资源均 HTTP `200`；大小分别为 `489,580`、`107,889` bytes，与本轮本地 production build 输出一致 |

## 真实浏览器会话观察

已接管用户已打开的线上工作台标签页，并读取到授权后的首页语义结构：工作区、待确认、Bases、团队 Bot、AI 对话、记忆与知识、成员与权限；首页可访问 3 个 Base，业务关联可到数字员工、群聊上下文、客户记录和项目记录，个人助理抽屉也可显示。

浏览器的全页截图命令在 CDP `Page.captureScreenshot` 阶段超时；随后读取浏览器日志的调用也触发了浏览器连接的超时重置。该现象发生在浏览器自动化通道，不能据此推定线上 Mini App 本身失败。由于未取得本轮可保存的线上截图，本轮不能替代视觉对比验收。

## 未执行的真实写入

- 未提交 CSV/XLSX Preview/Commit；
- 未新建或修改 Base、表、字段、记录、视图、模板或权限；
- 未发送 Telegram 消息；
- 未触及 Stage03 Docker、Webhook 或生产数据库结构。

## 结论与后续门槛

代码回归、构建、核心 API 边界和公网服务均为通过。仍未完成的唯一产品级证据是：在稳定的已授权浏览器/Telegram 会话中，完成一次受控导入或新建后，逐步确认菜单、跳转、AI 对话和持久化结果。该操作会产生真实业务对象，必须在执行该写入动作前再次取得用户确认，并保留结果截图与审计证据。
