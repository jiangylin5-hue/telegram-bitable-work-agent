# Stage10 Agent Event Runtime 实施与验收

## Status

- Status: implemented, publicly deployed and accepted on r66
- Scope: 主管 Agent 与只读 Specialist 的持久化控制面、事务 Outbox、Redis Streams 适配、可恢复安全 SSE，以及 Mini App 兼容接入
- Approval: 用户于 2026-07-28 明确批准方案、架构和技术细节复核后实施
- Compatibility: Stage08 同步接口与原 SSE 接口继续保留；Stage10 由后端和前端两个 feature flag 控制
- Excluded: 业务记录自动写入、草稿自确认、Telegram 发送、未验收的公开流量切换、原始 prompt/推理/检索证据明文持久化、通用无限制 Agent 框架

## 1. 目标与完成定义

Stage10 解决的不是“让多个大模型自由聊天”，而是把主管与子 Agent 之间的协作变成可审计、可恢复、可去重的任务协议。完成状态必须同时满足：

1. 请求先经过既有 Stage06/Stage08 身份、workspace、digital employee、record 和 action scope 校验；
2. PostgreSQL 原子持久化 run、checkpoint、command、event 与 outbox；
3. 子 Agent 只接收注册表允许的 capability 和安全引用，不接收数据库凭证或任意 SQL；
4. Redis Streams 只承担至少一次传输，不能成为业务真源；
5. 重复投递不会重复执行已完成 command，也不会重复生成 durable result；
6. SSE 重连必须重新授权，并从 `Last-Event-ID` 后安全回放；
7. 浏览器只收到 allowlist 事件和经过 `AssistantQuerySafeView` 校验的结果；
8. 任何失败只暴露稳定错误码和脱敏文案，不能暴露 provider 异常、prompt、原始字段值或内部 metrics。

## 2. 最终架构

```text
Mini App / API caller
  -> POST /api/stage10/agent-runs
  -> Stage06 identity + Stage08 scope/idempotency preparation
  -> PostgreSQL transaction
       AgentWorkflowRun
       AgentRunCheckpoint
       AgentEvent(run.accepted)
       AgentPrivateInput(AES-GCM ciphertext, short TTL)
       AgentOutboxEvent
  -> Supervisor dispatch
       registered capability only
       AgentCommand(platform.tabular.analyse)
       checkpoint + event + outbox
  -> independent outbox publisher -> Redis Streams
  -> independent read-only Specialist consumer
       claim lease
       recheck scope hash and deadline
       rebuild private LangGraph/OpenRouter context in memory
       execute existing Stage08 collaboration path
       validate AssistantQuerySafeView
       persist artifact metadata/reference only
       checkpoint + event + outbox
  -> Supervisor fan-in
       validate child/run/capability/scope/artifact
       run.completed
  -> GET /api/stage10/agent-runs/{run_id}/events
       reconnect authorization
       PostgreSQL event replay
       safe SSE projection
  -> React strict parser + sequence reducer
```

关键边界：LangGraph v1 仍使用 `checkpointer=None`。可恢复性由外层控制面 checkpoint 提供；恢复时重新授权、重新读取当前数据并重建私有上下文，而不是反序列化旧 prompt、模型回复或检索材料。为了让独立 worker 在 API 进程退出后仍可重建原始请求，新增短期 AES-256-GCM 私有输入表；它只存密文/nonce/key version/AAD hash/scope hash/过期时间，不属于 checkpoint，也不进入 Redis、SSE、日志或审计。

## 3. 数据模型与事务边界

Alembic revision `20260728_0034` 新增六张控制面表和一张隔离的短期密文输入表：

| Table | 责任 | 关键约束 | 明确禁止 |
| --- | --- | --- | --- |
| `agent_workflow_runs` | 根 run 状态、scope hash、deadline、lease、safe result ref | root idempotency 唯一；状态有界；保留 `target_record_id` 供重连授权 | query、prompt、原始结果 |
| `agent_run_checkpoints` | append-only 控制状态 | `(run_id, checkpoint_no)` 唯一；`control_json` 由 schema allowlist 校验 | 私有 graph state、字段值 |
| `agent_commands` | 不可变 Specialist 工作项 | command ID、run sequence、idempotency hash 唯一；capability 固定注册 | 任意 tool 名、任意 payload |
| `agent_artifacts` | 验证后的结果元数据 | content hash、scope hash、validation status | 重复存储模型原文或秘密 |
| `agent_events` | append-only 生命周期事实 | `(run_id, sequence)` 唯一；因果/关联 ID 必填 | stack trace、原始 tool output |
| `agent_outbox_events` | 数据库到 Redis 的事务交接 | event ID 唯一；成功发布后才写 `published_at` | 未密封消息、权限对象 |
| `agent_private_inputs` | worker 重建请求的短期密文 | run/command 唯一；AES-GCM AAD 绑定 scope；TTL；消费标记 | 明文 query、prompt、检索材料、provider response |

同一状态转移中的 checkpoint、event 和 outbox 必须在同一数据库事务提交。Redis 发布失败只增加发布尝试，不能回滚已经接受的 run；重复发布由数据库唯一约束和幂等状态机消除副作用。

## 4. 命令、事件与状态机

### 4.1 Command envelope

`AgentCommandEnvelope` 采用 `agent-command.v1`，字段严格、禁止 extra key。v1 只允许：

- `target_capability=platform.tabular.analyse`
- `command_type=analyse_visible_records`
- UUID 因果链：`command_id`、`run_id`、`causation_id`、`correlation_id`
- `scope_proof_ref=scope:sha256:<hash>`
- 最多 16 个安全 artifact ref
- deadline 与 idempotency SHA-256

Specialist 消费前必须验证 schema version、capability、scope proof、deadline、lease 和 command 状态。已完成 command 的重复投递只回放已有完成状态，不再次调用 LLM。

### 4.2 Event envelope

`AgentEventEnvelope` 采用 `agent-event.v1`。主管可发 `run.*`，Specialist 只能发 `agent.*`，模型输出不能改变这个权限规则。公开事件投影为：

- `status`: `accepted | queued | running | waiting_approval`
- `artifact_ready`: 安全 artifact ref 与短标签，不含内容
- `result`: 经过严格验证的 `AssistantQuerySafeView`
- `error`: 稳定 code 与脱敏 message
- `done`: 终态

前端要求 event body、SSE `id` 和 `Last-Event-ID` 序列一致；拒绝缺口、未知字段、超限事件、非法 UUID、重复但不同 event ID、私有 UUID 混入 answer，以及 completed 前没有 result 的非法转移。

### 4.3 Run 状态机

```text
accepted -> queued -> running -> completed
                           |-> degraded
                           |-> failed
                           |-> cancelled
                           |-> waiting_approval  (协议保留，v1 不启用写路径)
```

- `Supervisor` 创建和终结 run，并负责 fan-in；
- `Specialist` 只能完成自己的 command；
- cancellation 只阻止后续 command，不能伪造上游 provider 已取消；
- lease 过期后允许其他 worker 领取；未过期的 lease 不能被抢占；
- scope hash 不一致立即拒绝继续执行或回放。

## 5. API、权限与安全投影

### 5.1 创建 run

`POST /api/stage10/agent-runs`：

1. 只接受 `requested_action=read_only`；
2. 复用 Stage08 `prepare_assistant_query`，不复制权限和 skill 选择逻辑；
3. `redis_worker` 模式在同一事务中提交 accepted run、加密输入、queued command 与 outbox，然后立即返回 202；
4. 独立 worker 重新授权、解密并复用 `complete_assistant_query` 触发真实 LangGraph/OpenRouter 路径；`embedded` 仅保留给本地兼容测试；
5. 复用 Stage08 idempotency record 作为结果所有者，Stage10 artifact 仅存 `storage_ref` 和 hash；
6. provider/worker 失败时保留 durable failed event，并把外部异常脱敏为 `agent_run_internal_failure`。

### 5.2 SSE 重连

`GET /api/stage10/agent-runs/{run_id}/events`：

1. 解析严格的十进制 `Last-Event-ID`；
2. 根据 run 保存的 workspace、employee、target record 重新执行当前授权；
3. 重算 scope hash，和 run 原 scope hash 比对；
4. 从 PostgreSQL 回放 cursor 后的 event；
5. 只投影 allowlist 字段；
6. 结果引用必须解析到 completed idempotency record，并再次通过 safe-view 校验；
7. 权限撤销返回 403，run 不存在返回 404，cursor 非法返回 422，安全结果损坏返回独立 500，不能误报为权限拒绝。

## 6. Redis Streams 与恢复

Redis adapter 支持 publish、consumer group read、ack 和 `XAUTOCLAIM` pending takeover。消息在入队和出队两侧都经过 Pydantic JSON boundary 校验。部署形态应为：

```text
outbox publisher
  -> publish sealed envelope
  -> mark published only after XADD success

specialist consumer
  -> XREADGROUP
  -> claim run/command lease
  -> durable transition + outbox commit
  -> XACK

recovery consumer
  -> XAUTOCLAIM idle pending message
  -> check command durable state
  -> replay completed or resume eligible work
```

真实分布式验收必须启动独立 publisher 与 specialist worker，覆盖 XADD、XREADGROUP、commit-before-XACK、XAUTOCLAIM 和重复投递。只有 adapter/内存协议测试不能再作为 Stage10 完成证据。

## 7. Mini App 接入

- `VITE_AGENT_EVENT_RUNTIME_ENABLED=true` 且请求为只读时尝试 Stage10；后端还必须命中 `AGENT_EVENT_RUNTIME_ALLOWED_WORKSPACE_IDS`；
- 非灰度 workspace 的 Stage10 404 必须无损回退 Stage08，不能把灰度控制暴露成聊天失败；
- 写入/草稿路径继续使用 Stage08，不允许因为 feature flag 绕过确认；
- POST 创建 run 后 GET SSE；连接中断最多进行一次有界重连，并携带最后序列；
- 新事件被转换成现有 Stage08 workbench event interface，避免复制第二套聊天 UI；
- UI 显示 `只读模式 · 可恢复事件流`，让用户知道当前执行边界；
- 工作区级对话在没有显式 Base/record 上下文时保持 `intent=mixed`，由服务端在数字员工授权范围内完成 skill 选择和表格检索；前端不得把普通输入静默降级为 `general_advice`，否则会出现“skill 命中但检索未执行”的假阴性；
- 服务端仅对自动、只读、完整命中纯问候/能力询问 allowlist 的 `mixed` 请求生成 `general_advice` 有效命令；带任何业务文本的问题保持 `mixed`。prepare/resume 必须共享同一归一化函数，避免分布式恢复后路由漂移；
- skill 选项只约束路由，不替换用户已输入的问题。`自动选择` 与显式 skill 必须暴露互斥的可见选中态和 `aria-pressed`，并在用户继续编辑 query 后保持选择；
- feature flag 关闭时保持既有行为和部署兼容性。

## 8. 分步实施记录

| Step | 修改内容 | 状态 |
| --- | --- | --- |
| 1 | 严格 command/event/checkpoint/SSE schema 与拒绝私有字段测试 | complete |
| 2 | SQLAlchemy 六表模型、0034 migration、唯一约束与真实 PostgreSQL smoke | complete |
| 3 | run/checkpoint/event/outbox 状态机、lease、幂等、scope drift | complete |
| 4 | Redis Streams 发布、读取、ack、pending claim adapter | complete; real Redis and recovery accepted |
| 5 | 固定 capability registry、主管 dispatch/fan-in、只读 Specialist | complete |
| 6 | feature-flagged run API、重新授权、安全 SSE 投影 | complete |
| 7 | React 严格解析、重连 reducer、Stage08 UI 兼容接入 | complete |
| 8 | 全量回归、安全扫描、浏览器验收、文档同步 | complete |
| 9 | 加密私有输入、独立 publisher/worker、XAUTOCLAIM、灰度 allowlist | complete |
| 10 | 隔离服务器、真实 Redis/PostgreSQL/OpenRouter/中文多表/UI 验收与生产部署 | complete |
| 11 | 生产 UI 自动路由质量修复：工作区级 `mixed` 意图、skill 选中反馈、不得覆盖 query；真实中文问题复测 | complete on r66 |

## 9. Verification Evidence

最终结果：

- Backend Unit+API: 1537 passed；生产 r66 collaboration API: 71 passed；
- Mini App: 79 files / 411 tests passed；production build passed；
- Alembic: production PostgreSQL one head `20260728_0034`；
- Real distributed infrastructure: PostgreSQL、Redis XADD/XREADGROUP/XAUTOCLAIM/XACK、独立 publisher/worker、worker crash/pending takeover 和 timeout cleanup 均通过；
- Real LLM 20-case: `google/gemini-2.5-flash` through OpenRouter，20/20 completed，skill hit、precision、recall、readiness、answer accuracy 均为 100%，平均端到端 2111.65 ms；
- Static parity: 本地与 r66 生产 JS/CSS SHA-256 完全一致；
- Public Browser: 显式“汇总分析”、自动检索、纯 `你好`、`你好` 加业务问题四类均实测通过；业务 case 有 citation 且无 degradation；console 0 application error/warning；
- 完整逐 case 与部署证据见 `evidence/stage10-r7-real-20-case-distributed-report-2026-07-28.md` 和 `evidence/stage10-r66-public-deployment-and-ui-acceptance-2026-07-28.md`。

## 10. Remaining Boundaries

1. Stage10 v1 只注册只读 `platform.tabular.analyse`；新增 Specialist 必须重新定义 capability、权限、事件、恢复和验收真值集；
2. Telegram 发送、业务记录写入和草稿自动确认仍不属于 Stage10；
3. 模型质量报告覆盖固定中文多表真值集，后续字段类型、语言和数据规模扩展应增加持续基准；
4. Stage08 compatibility path 继续保留，移除前必须另行制定迁移计划。

## 11. Temporary Cleanup

- 隔离验收 systemd transient units 已停止，`/opt/stage10-acceptance`、测试 env、上传包和临时脚本已删除；
- `stage10_test_r4`、`stage10_acceptance_r2` 数据库/角色和对应 HBA 项已删除；
- 未激活的 r62/r63 source、venv、static 已删除；r64/r65、r66 与生产备份按回滚策略保留；
- 本轮创建的 4 个 browser session 和 4 个 handoff 已按时间边界撤销；本机临时发布包与 SSH key 已删除；
- 本地 build 产物遵循既有 ignore 规则；没有新增重复架构文档。
