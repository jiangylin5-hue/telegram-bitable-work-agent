# Stage08 Package F：运行指标范围与 Milvus 决策

## Status

- Decision status：accepted — retain `pgvector`, do not introduce Milvus in Stage08
- Date：2026-07-22
- Evidence basis：Package F final review `PASS / 0 Critical / 0 Important / 0 Minor`；F3/R2/R3 versioned synthetic Provider evidence，其中 R3 为 12/12 全门禁通过且含安全 action enum。

## 已获得的受控质量指标

F3 R3 在最多两路并发、每 case 独立进程的固定 12-case 合成矩阵中记录：

| 指标 | 结果 | 解释 |
| --- | ---: | --- |
| Case 通过率 | 12 / 12 | 合成权限、引用、群时效、RAG lifecycle、草稿压力、取消/replay、双语与降级矩阵 |
| 超时 | 0 | 仅本次受控 Provider 批次，不等于生产 SLO |
| Provider invoked / completed | 9 / 9 | 明确区分 Provider 前终止/故障/协调器 case |
| Usage metadata presence | 8 | 只记录是否存在，不保存 token/cost 值 |
| 延迟 | 4 under_250ms、6 under_5s、2 over_5s | 仅离散桶，避免存储敏感/可识别请求细节 |
| 动作 | read_only 5、general_advice 1、deny 2、none 4 | 严格 case/action 映射已由 parent revalidation 验证 |

这些指标证明当前 Package F 的受控质量链路、超时隔离和脱敏留存。它们不证明真实工作负载吞吐、长时间稳定性、生产成本或召回率。

## Milvus 决策

当前继续使用 PostgreSQL + pgvector：

- PostgreSQL 仍是权限、source version、删除/撤权和业务事实真源；
- `PostgresRetrievalProvider` 已满足 Stage08 的可重建检索路径；
- 没有生产规模证据表明 pgvector 已成为容量、延迟或运维瓶颈；
- 在没有真实规模/SLO 数据时引入 Milvus 会增加双写、删除传播、回放、回退与权限重读的运维复杂度，而不能提高本轮受控质量证据。

因此 F-04 的当前结论是：**不满足引入 Milvus 的触发条件，维持 pgvector，不创建 Milvus 集群、双写或新依赖。**

## 未来触发门槛（生产前不实施）

只有连续真实生产观测同时显示下列至少一项，才创建新的技术决策并请求用户确认：

1. 在权限后过滤与 PostgreSQL current-state 重读都保持的条件下，pgvector 检索 p95 长期超出产品 SLO；
2. chunk 规模、QPS 或并发索引重建已由容量报告证明超过单 PostgreSQL 可接受运营边界；
3. 删除/撤权传播、索引重建或备份恢复已造成可量化且持续的业务风险；
4. 双写回放、`chunk_id/source_version` 一致性、PostgreSQL 回退与删除 SLA 已有独立压测设计和运维负责人。

触发后仍需新增 `MilvusRetrievalProvider` 决策、双写/回退方案、真实负载压测、权限重读和删除 SLA 证据；本文件不授权这些工作。

## 生产剩余项

Stage08 的开发/质量证据可以关闭，但生产上线仍需要服务器环境、PostgreSQL/pgvector/Redis、HTTPS/webhook、secret rotation、observability、rollback、真实 Telegram controlled smoke 与生产权限审计。这些属于后续生产就绪工作，不由本次 Package F evidence 代替。
