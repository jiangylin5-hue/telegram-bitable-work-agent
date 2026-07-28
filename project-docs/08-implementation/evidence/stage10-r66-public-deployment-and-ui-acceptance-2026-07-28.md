# Stage10 r66 公网部署、真实 UI 与最终审计报告

## Status

- Status: passed
- Executed At: 2026-07-28 Asia/Shanghai
- Public URL: `https://stage07.jiangtest1.online`
- Active Artifact: `stage09-p1-20260728-r66-conversation-routing`
- Artifact SHA-256: `7ED5A4ADFABE80CCDD15104B06928F146D67361B2731A596FC63543C79DB62AF`
- Database Head: `20260728_0034`
- Scope: Stage10 只读 Agent 事件运行时、真实中文多表问答、skill 路由、生产 Mini App 和故障恢复
- External-write Boundary: 未发送 Telegram，未自动确认草稿，未写入生产业务记录，未调用业务 Provider 写接口

## 1. 发布路径与回滚

本轮没有直接覆盖运行目录。每个候选都经过固定 source、venv、static 三件套和密封包校验，再通过有界 readiness gate 原子切换。

| Revision | 结果 | 说明 |
| --- | --- | --- |
| r62 | rejected and removed | 首次候选未通过运行门禁，未保留为可回滚版本 |
| r63 | rejected and removed | 前端 Stage10 flag 未进入静态构建，未激活 |
| r64 | activated, retained | Stage10 分布式运行时首次完整上线，保留为架构级回滚点 |
| r65 | activated, retained | 修复前端自动路由、skill 选中态及 query 被覆盖问题，保留为直接回滚点 |
| r66 | active | 增加服务端纯问候/能力询问边界路由，业务问题仍保持检索优先 |

激活前生产数据库备份为 `/opt/stage09-p1/backups/stage09-p1-pre-r64-20260728.dump`，SHA-256 为 `e7b0d073c71d21fc9f62292b7f53a4df26526c510e827844aa977be71a32f60c`。两次失败激活均触发自动回滚；r64、r65、r66 的正式激活未触发回滚 trap。

## 2. 最终运行形态

```text
Browser / Telegram Mini App
  -> Nginx HTTPS
  -> FastAPI create-run / reconnectable SSE
  -> PostgreSQL run + checkpoint + command + event + outbox
  -> independent outbox publisher
  -> Redis Streams
  -> independent read-only tabular specialist worker
  -> Stage08 authorized retrieval + LangGraph + OpenRouter
  -> validated safe artifact
  -> PostgreSQL terminal event
  -> SSE safe projection
```

生产指针均解析到 r66：

- source: `/opt/stage09-p1/releases/stage09-p1-20260728-r66-conversation-routing`
- venv: `/opt/stage09-p1/venv/stage09-p1-20260728-r66-conversation-routing`
- static: `/var/www/stage09-p1/stage09-p1-20260728-r66-conversation-routing`

API、worker、outbox bridge、Agent outbox publisher、Agent tabular worker、专用 Redis 与 Nginx 均为 active；`/health` 返回 `{"status":"ok"}`。最近两小时上述应用 unit 没有 error 级 journal 记录。

## 3. 真实浏览器 UI 验收

浏览器使用生产域名和真实 owner 会话。没有注入 fixture 响应，也没有改写浏览器存储。最终控制台应用级 `error/warn` 为 0。

### 3.1 显式 skill

- 操作：点击“汇总分析”。
- 可访问性：`汇总分析 aria-pressed=true`，`自动选择 aria-pressed=false`，其余 skill 均为 false。
- 输入保护：点击 skill 后输入框保持空白，没有把 skill 描述写成用户 query。
- Query：`请汇总客户与项目的关键信息、当前状态和下一步建议。`
- Answer：`客户“明日璀璨”的主要项目是“年度协作升级”，目前处于“方案确认”阶段。最近一次联系是2026年7月23日。下一步建议是“确认报价范围并预约价格沟通”，下一个里程碑是2026年7月25日。`
- Run: `fdb8396a-4504-4347-88a8-bc90f6e4cd17`
- Skill: `platform-tabular-analysis`
- Retrieval: 1 citation，no degradation
- Durable events: accepted -> dispatched -> started -> completed -> run.completed

### 3.2 自动选择与表格检索

- Query：`明日璀璨客户现在是什么阶段，项目下一步做什么？`
- Answer：`明日璀璨客户目前处于“方案确认”阶段，项目下一步是“确认报价范围并预约价格沟通”。`
- Run: `e11cebeb-ddc5-4f5c-8912-2f93e9f3e46c`
- Skill: `platform-base`
- Retrieval: 1 citation，no degradation

### 3.3 日常对话与路由边界

纯问候只在服务端、仅对完整匹配的自动只读 `mixed` 请求归一化为 `general_advice`。前端始终发送 `mixed`，因此不会自行绕过检索。

| Query | Answer | Run | Citation | 判定 |
| --- | --- | --- | ---: | --- |
| `你好` | `您好！我是一个语言模型，可以回答您的问题并提供帮助。` | `94feb11b-cc2a-44a4-8c38-4e7a409f86fa` | 0 | 纯问候正常对话 |
| `你好，明日璀璨客户现在是什么阶段？` | `明日璀璨客户目前处于“方案确认”阶段。` | `9b52457b-0c92-4789-986e-6404ed95a65e` | 1 | 带业务文本，不降级，继续检索 |

这组边界 case 证明“像日常大模型一样回复”与“业务事实必须检索”可以同时成立，而不是由前端用宽泛关键词猜测意图。

## 4. 真实中文 20 Case 指标

隔离 r7 使用真实 OpenRouter `google/gemini-2.5-flash`、真实 PostgreSQL、真实 Redis Streams 和独立 publisher/worker。测试数据为 3 张表、32 条记录、2 个关联字段和 26 条关联边；完整逐 case query、answer、skills、P/R/Ready/Acc、评分与延迟见 `stage10-r7-real-20-case-distributed-report-2026-07-28.md`。

| Metric | Result |
| --- | ---: |
| Cases / Completed | 20 / 20 |
| HTTP/SSE success | 20 / 20 |
| Skill hit rate | 100% |
| Retrieval precision | 100% |
| Retrieval recall | 100% |
| Retrieval readiness | 100% |
| Answer accuracy | 100% |
| Composite score | 100/100 |
| Mean end-to-end latency | 2111.65 ms |

测试同时覆盖精确 ID、过滤、计数、空结果和隐藏字段拒答。恢复演练覆盖 XADD、XREADGROUP、30 秒 pending idle 后 XAUTOCLAIM、commit-before-XACK、重复投递去重和超时终态收敛。

## 5. 最终回归证据

| Gate | Fresh Result |
| --- | --- |
| Backend Unit + API | `1537 passed in 88.26s` |
| Server focused collaboration API | `71 passed in 9.70s` |
| Mini App | `79 files / 411 tests passed in 194.00s` |
| Production build | passed; 1853 modules transformed |
| Alembic | one head `20260728_0034` on production PostgreSQL |
| Static parity | local/server JS and CSS SHA-256 exact match |
| Browser | explicit skill, auto retrieval, pure greeting and greeting+business boundary passed |
| Browser console | 0 application errors/warnings |

Static hashes：

- `index-Ae67yWVw.js`: `b4b005b84132257e5979b4453276a0b59192fd6279eec7272be22d90ab806ba0`
- `index-DkaFQZWM.css`: `1691c6dad089641f0bac5f47e7afd2ff20f869c2258f52e4a1df97b1c43c6a93`

## 6. Skipped / Environment-qualified Checks

- 最终 Unit+API 与 Mini App 命令没有 skip。
- 本地直接执行包含全部 integration 的 `pytest -q` 时，测试库 fixture 无权执行 `CREATE EXTENSION vector`，因此在 fixture setup 阶段失败；这不是业务断言失败，也不被计为通过。真实 PostgreSQL/pgvector、Redis 和进程恢复由服务器隔离 r7 的 246 项 integration 验收及分布式 20-case 报告覆盖。
- Telegram 发送、草稿自动确认和业务记录写入没有执行；它们是本阶段明确排除的副作用，不是遗漏的自动化测试。

## 7. Cleanup 与剩余风险

已删除未激活的 r62/r63 source、venv、static；已停止并删除隔离 Stage10 acceptance 服务/目录，删除 `stage10_test_r4`、`stage10_acceptance_r2` 测试库与角色、对应 HBA 项及服务器/本机临时发布包。最终浏览器检查完成后，按创建时间边界撤销本轮 4 个测试 browser session 与 4 个 handoff；更早的用户会话未改动。本机临时 SSH key 也已删除。保留 r64/r65 回滚工件、r66 当前工件和生产备份。

剩余风险：

1. 目前只注册一个只读 `platform.tabular.analyse` Specialist；增加新 Specialist 必须新增 capability、权限、事件和恢复测试，不能复用任意 tool 名。
2. 公开 SSE 对不存在或不可见 run 使用 404 隐藏资源存在性；客户端必须把它视为不可恢复的授权/资源终态，而不是无限重连。
3. 模型质量指标来自固定真值集，不能代表所有开放域 query；新增字段类型、语言和大表规模后应扩展 truth set。
4. 生产业务写入仍走 Stage08 草稿确认链，Stage10 v1 未开放写操作。

## 8. Acceptance Decision

Stage10 只读事件运行时、真实多表检索、skill 命中、中文回答、生产 UI、恢复边界和部署回滚证据满足本阶段验收条件。r66 作为当前生产版本，r64/r65 作为受控回滚版本；后续工作应以扩展 Specialist 覆盖和持续质量基准为新阶段，而不是继续修改本阶段真源。
