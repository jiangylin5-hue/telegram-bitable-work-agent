# Stage08 测试与验证计划

## Status

- Scope：定义 Stage08 各层测试、环境、数据集、真实 Provider 规则和验收证据格式。
- Status：planning baseline。

## 1. 测试层级

| 层级 | 目标 | 必测对象 | 禁止替代 |
| --- | --- | --- | --- |
| Unit | 纯合同、策略、状态、chunk、排序、冲突 | Pydantic、policy、graph node、adapter | 不得以 mock 成功替代权限断言 |
| Service | service boundary 与 UoW 行为 | ticket、Memory、retrieval、draft | 不得直接测 ORM 绕过 service |
| API | identity、scope、DTO、错误合同 | runtime/memory/query/reindex API | 不得暴露 raw payload |
| PostgreSQL | migration、事务、锁、并发、删除 | ticket、Memory、source/chunk、idempotency | SQLite 不可替代 |
| Graph | fan-out/fan-in、取消、降级、budget | Coordinator 与子图 | 单节点测试不等于协作测试 |
| Live provider | 合成数据下结构、引用、草稿、拒绝 | 隔离 case runner | 不得访问真实业务数据或发送消息 |
| UI | 后续单独阶段 | 证据标签、ticket/draft/Memory 管理 | 本 Stage08 后端包不自动宣称前端验收 |

## 2. 最小测试矩阵

### 权限与数据

- employee 无对应 action、caller 无 workspace/base/view/field 权限、chat scope 不匹配、客户/项目/群关系不匹配均返回 deny；
- 检索前 source set 与检索后 record/field reread 都必须被测；
- 删除、撤权、TTL、source version 改变后，旧 chunk、旧引用和旧 Memory 不能再被读取；
- 任何 audit/DTO/log 测试必须断言不包含隐藏 field、原始群聊、prompt、response、secret。

### Tool Gateway 与草稿

- 仅 allowlist tool 可实例化；未知 tool、raw prompt key、超预算、超深度和重复执行 fail closed；
- `record.query` 只能返回 caller 可见 field key/计数；
- draft adapter 只创建 `pending_confirmation`，源 record 不变，`proposed_values` 不进入脱敏结果；
- ticket 同 key 同指纹重放，异指纹冲突；同 workspace 并发请求经 workspace 行锁串行化，trace 冲突不遗留 `in_progress` 幂等记录；重放必须再次复核 workspace 与 request fingerprint；终态 ticket 不可复活。

### Memory 与群聊

- 表格事件自动写入可追溯 Memory；同事件重复不产生多份活跃 Memory；
- 群聊高置信决策/偏好/风险写入候选/Memory 时必须有 source ref、scope、confidence；
- 冲突不覆盖；撤销/删除使索引立即不可读；完整原文不进入 payload；
- 最近窗口、时间衰减历史、跨群隔离和窗口上限均有固定 fixture。

### RAG 与协作图

- chunker 对 source version 稳定、可重建、可删除；
- 结构化过滤与向量检索的权限条件一致；HNSW 过滤场景有召回基线；
- Coordinator 并行读取不超过预算；任一 read 子图失败会产生标签化降级而非虚构事实；
- Analyst/Draft 不能直接调用未授权工具；Draft 必须经过 Policy Gate。

## 3. 真实 Provider 评测规则

- 所有 case 使用新建的合成内存 workspace、record、文件片段和群聊片段；不连接持久化业务数据库。
- 每 case 在独立子进程运行，硬超时，结果仅保留 case ID、布尔门禁、计数、固定失败标签和模型元数据存在性。
- `TELEGRAM_SEND_MODE=dry_run`，禁止 Telegram 发送、webhook 修改、draft 确认、外部 provider 写入。
- 首发语料至少覆盖：可见查表、隐藏字段拒绝、撤权 reread、引用可访问、通用建议标签、草稿 payload、群聊时效、Memory 冲突、RAG 删除、tool deny、预算超限和子图失败降级。
- 真实调用不是生产证明；不能替代 PostgreSQL、API 或 UI 验收。

## 4. 质量门槛

| 指标 | 门槛 | 失败处理 |
| --- | --- | --- |
| 权限越权/隐藏泄漏 | 0 | 阻断包验收 |
| 草稿前源记录直接变更 | 0 | 阻断包验收 |
| 引用不可访问 | 0 | 阻断包验收 |
| ticket 重复执行 | 0 | 阻断包验收 |
| 超时 case 影响其他 case | 0 | 阻断评测器 |
| 合成 live case 结构/安全门禁 | 100% | 回归与定位后重跑 |
| Memory 删除/撤权后可读取 | 0 | 阻断检索包 |

## 5. 证据格式

每个证据文件必须写明：变更包、命令、测试数与结果、数据库/Provider/Telegram 边界、使用数据是否合成、未执行项、剩余风险、临时文件清理结果。禁止写入 key、chat ID、webhook、原始 prompt/response 或业务正文。
