# Stage09 首个工作区初始化

## Status

- Scope: 原生 Stage09 空平台库的首次受控初始化。
- Current Progress: 待在服务器执行；脚本和前端 Mini App 视口适配正在实现。
- Non-goal: 不迁移旧 Stage03 业务数据；不更改表结构、API contract 或权限模型。

## 问题与目标

原生 Stage09 PostgreSQL 已完成迁移但没有任何 `workspace`、`workspace_member` 或 Telegram binding。因此 Telegram Mini App 即使通过服务入口，也不能解析到受权身份，前端只能呈现“没有可访问的工作区”的兜底状态。

本操作为现有 allowlist 中唯一的私聊 Telegram 用户创建一条真实、可审计的最小业务闭环：

```text
Telegram allowlisted private user
  -> opaque workspace member identity
  -> owner membership
  -> active chat_user binding
  -> 客户协作工作台 Base
  -> 客户 / 项目 / 群聊 tables and linked records
  -> 客户协作数字员工
  -> active group -> customer -> project context mapping
```

## 约束

- 仅当原生 Stage09 数据库中恰好存在一条私聊用户自己发送的 `/stage07-bind` 文本标记时执行；标记的 chat/user 必须相同。缺失、歧义、群聊或格式不合法时安全拒绝，不写库。
- Telegram 原始 ID 只存入已有 binding 字段；工作区 member/owner 使用不可逆的稳定摘要标识，且脚本输出不显示 Telegram ID、令牌、数据库 URL 或业务密钥。
- 复跑幂等：若该 Telegram 用户已有单一 active binding，脚本只报告现状，不新增第二份工作区。
- 写入使用既有平台 service/UoW、已有审计链路与 Stage08 映射模型；不放开 bootstrap 权限，不伪造 initData。
- 生成的数据是可编辑的首个真实工作区内容，不是前端 mock 数据；后续可由 owner 在 Mini App 中继续维护。

## Acceptance Criteria

- 原生数据库中存在一个 active workspace、owner member、active binding、Base、三个表、基础记录、数字员工与一条 active group context mapping。
- 使用真实 Telegram Mini App 重开后，`GET /mini-app/bootstrap` 不再为该用户返回 403，界面进入 workspace home。
- `WebApp.ready()` 与 `WebApp.expand()` 在 Telegram host 启动时调用；普通浏览器不受影响。
- 脚本单元测试、Mini App adapter 测试、前端 build 均通过。
