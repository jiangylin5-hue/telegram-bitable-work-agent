# Stage09 首个真实工作区初始化证据（2026-07-23）

## Status

- Evidence status: `executed`
- Native artifact: `stage09-p1-20260723-r22`
- Source commits: `9e4df47`、`c14ad18`、`8ef4d25`、`8c5adf3`、`d95907e`
- Scope: Telegram Mini App 首次可访问工作区的真实数据初始化与服务端授权链路核验。

## 已执行的真实写入

原生 Stage09 平台库此前已完成迁移但没有业务对象，导致签名身份即使进入 Mini App 也无法解析到工作区。本次通过唯一已持久化的私聊 `/stage07-bind` 标记解析目标；没有读取或输出 Telegram 原始 ID、token、数据库 URL 或完整消息正文。

初始化脚本在一个数据库事务中创建并提交：

- 1 个 active workspace 和 1 个 owner membership；
- 1 条 active `chat_user` Telegram binding；
- 1 个客户协作 Base、客户/项目/群聊 3 张表，以及 3 条真实起始记录；
- 1 个 active 数字员工；
- 1 条 active 群聊 → 客户 → 项目业务上下文映射；
- 1 条 `stage09.first_workspace_provisioned` 审计事件。

脚本对同一 binding 可重跑：若绑定已经存在且完整，只返回 `existing`，不会新增第二个工作区。

## 发布与核验

1. r18/r19 的密封包、错误 Nginx unit 和错误内部地址探针问题均在原子切换保护下回滚；没有将失败版本保留为 `current`。
2. r20/r21 在“真实数据库事务演练、最终 rollback”阶段分别发现并拦住了关联记录与数字员工未 flush 的问题，未切换服务。
3. r22 的同一真实事务演练通过后才切换 source、venv 和 static symlink。API、worker、outbox、Redis 与系统 Nginx 均为 active；API 回环和 `https://stage07.jiangtest1.online/health` 都通过。
4. 写入后服务端以真实 binding 对应的 member identity 调用既有 Mini App service：bootstrap 返回 1 个 workspace；Home 返回 1 个 Base 和 1 条授权业务关系索引。

## 当前边界

- 这证明服务端已具备真实的 workspace/binding/data/relationship 链路，不是前端 mock 数据。
- 仍需用户关闭并重新打开 Telegram Mini App，取得新的 signed `initData` 后观察 Home、Base 和数字员工页面；该人机可见验证完成前，不将 Stage07 全量视觉验收标记为通过。
