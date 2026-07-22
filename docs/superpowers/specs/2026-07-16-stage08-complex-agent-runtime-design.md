# Stage08 复杂 Agent 运行时设计

## Status

- Status：已获用户确认的设计规格；实现前仍需审阅独立实施计划。
- Scope：构建受权限约束、可审计的复杂 Agent 运行时，覆盖知识问答、实时查表、群聊上下文、RAG、自动业务 Memory、任务草稿与 LangGraph 协作子图。
- Out of scope：Stage07 浏览器验收收口、生产部署、任意直接写入、不受限 Telegram 发送、自治 Agent 相互通信、文件自动写入 Memory，以及 Milvus 生产数据面。

## 产品目标

Stage08 的首个业务闭环是通用知识助手：它能依据内部证据回答、检索已授权文件、使用已授权 Telegram 群聊上下文；当资料不足时可给出明确标注的通用建议；需要落地时只生成受控的任务或记录草稿。

用户既可直接 `@employee`，也可让协调 Agent 处理复杂请求。任何持久业务结果必须落到表格记录、草稿、业务 Memory 或审计事件；单纯聊天回复不是持久业务结果。

## 架构选择

采用“协调 Agent + 专长 LangGraph 子图”，而不是单一巨型 Agent 或自由运行的自治 Agent 群。

```text
Mini App / Telegram @employee
-> Coordinator Graph
-> Context Planner
-> 并行 Structured Data / Group Context / Knowledge Retrieval 子图
-> Analyst
-> Draft Agent（需要时）
-> Policy Gate
-> answer、draft 或 execution ticket
-> AgentRun、tool、memory 与 audit evidence
```

只有协调 Agent 可以对外回复。各专长子图只交换类型化状态，不能直接访问数据库、传递任意 prompt、直接写入或直接发送消息。

## 回答与证据策略

`Context Planner` 可选择以下一个或多个路径：

1. 实时结构化查表，用于业务事实；
2. 当前已授权群聊上下文；
3. 已授权文件、摘要与业务 Memory 的检索；
4. 不依赖内部资料时的通用模型推理。

回答必须标明其依据：`business_data`、`confirmed_memory`、`retrieved_material`、`analysis_from_current_material` 或 `general_advice`。

内部资料不足时可给通用建议，但必须说明该建议并非基于内部业务数据；不得声称查询到了未实际检索的数据。

## 数据源与上下文工程

数据源包括已授权的工作区表格记录、上传文件、Telegram 群消息和 MemoryItem。

每次运行只构造必要上下文：

- 请求者、员工、workspace/base/table/view、客户、项目和群聊作用域；
- 当前群最近消息窗口；
- 实时查表结果；
- 必要时按时间衰减检索的已授权群历史；
- 已授权文件与 Memory 的检索片段。

禁止将整张表或完整群聊历史直接塞入 prompt。Tool Gateway 只取受限切片，`Context Planner` 再压缩并标注来源。

## 业务 Memory

Memory 是可追溯的业务上下文，不是任意模型转录，也不是隐藏思维链。

`MemoryItem` 包含类型、规范化载荷、workspace/customer/project/group 作用域、来源引用、置信度、提取元数据、版本/替代关系、TTL/有效状态、删除状态与审计引用。

自动写入规则：

- 已落表的确认决策、订单、任务和事件会写入业务 Memory；
- 高置信群聊决策、偏好、风险、客户事实和项目事实可以自动写入；
- 上传文件仅用于检索，不自动生成 Memory。

冲突信息必须新建版本并标记冲突，不能无来源地覆盖旧信息。无需逐条人工确认即可自动写入，但用户仍拥有撤销、删除、失效和审计可见性控制。

## 检索数据面

PostgreSQL 是权限、来源版本、Memory、删除、TTL、provenance 与审计的唯一真源。首发向量索引使用 `pgvector`，并与关键词和结构化过滤组合。

每个检索 chunk 包含 workspace/source 标识、来源类型/版本、客户/项目/群聊关系、可见性投影、时间戳、有效状态和来源指针。应用先计算允许来源集合再检索，并对每个返回结果再次做权限核验。

通过 `RetrievalProvider` 抽象未来接入 Milvus。未来 Milvus 只能保存可重建的 embedding 副本、最小授权投影及来源/版本元数据，不能成为权限或删除的权威来源。

仅当出现可量化触发条件才评估 Milvus：百万级 chunk、延迟/并发目标无法达成，或已验证存在高吞吐多向量/批处理需求。

## Tool Gateway 与动作策略

现有命中的 Skill 将接到类型化、后端授权的工具。首批工具为实时 `record.query`、`table.summarize`、`contact.resolve`、`import.preview`、`tool_catalog.inspect`、`task.create_draft` 与 `record_change_draft.create`。

任何工具调用的权限都是 employee、caller、workspace/base/table/view/field 与 Telegram chat scope 的交集。

动作分层：

- 默认仅回答、引用和创建草稿；写入与发送都要用户确认；
- 单独批准的低风险内部状态更新可以自动执行；
- 只有用户批准且 allowlist 的测试群可自动回复或建任务；生产群仍必须确认。

写入类动作必须经过 `PolicyGate`、execution ticket、幂等和审计；除非单独批准的动作等级另有规定，否则仍沿用现有 draft/confirmation 合同。

## LangGraph 运行模型

每次运行创建可定位的运行状态：trace、取消、幂等键、工具调用、预算和终止原因。

专长节点：

- `ContextPlanner`：选择受限的数据路径与执行计划；
- `StructuredDataAgent`：通过 Tool Gateway 查询实时业务事实；
- `GroupContextAgent`：组装最近窗口/历史检索，并可提出 Memory 候选；
- `KnowledgeRetrievalAgent`：检索文件和 Memory chunk；
- `AnalystAgent`：输出有证据边界的分析与不确定性；
- `DraftAgent`：只创建任务或记录变更草稿；
- `PolicyGate`：校验权限、引用可见性、输出合同、动作等级、预算与确认规则。

独立读取可以并行，但所有节点共享总时间、token、工具调用、检索 chunk、嵌套深度和重试上限。失败必须安全降级：内部检索失败后可以给带标签的通用建议，但不能给无证据业务断言或绕过写入门禁。

## 质量、安全与运维

评测必须覆盖查表准确性、字段/记录撤权、引用、群聊时效与作用域、Memory 冲突/删除、草稿 payload 安全、工具拒绝、部分失败和模型/Provider 降级。

真实 Provider 评测器必须实现单 case 进程级超时、失败隔离、受限并发、脱敏指标与清理，避免慢响应阻塞整个批次。

记录 prompt version、graph version、模型元数据、token/成本/延迟聚合、工具调用、检索数量、Memory 变更和策略决定；不得持久化原始密钥、任意隐藏 prompt、模型原始回复或思维链。

## 实施包

1. Runtime Foundation：执行计划/运行/工具/ticket 合同、预算、取消、幂等、审计与类型化 Tool Gateway。
2. Business Memory：schema、自动事件/群聊提取、版本、冲突、TTL、删除、撤权与审计。
3. Context Engineering：群聊窗口/历史、客户项目关系、上下文编排与证据标签。
4. RAG 与 Indexing：chunk/version/reindex/delete 流程、PostgreSQL/pgvector 混合检索、检索抽象。
5. LangGraph Collaboration：协调器/专长子图、结构化状态、并行读取、Policy Gate 与 Draft 路径。
6. Quality and Operations：标注评测、Provider 隔离、可观测性与基于指标的 Milvus 决策门。

## 验收方向

每个实施包都要有独立 BDD/SDD、安全合同、涉及持久化时的迁移计划、fixture 测试、local PostgreSQL 测试与安全的真实 Provider case。任一包完成都不代表 Stage07 已验收，也不代表生产就绪。
