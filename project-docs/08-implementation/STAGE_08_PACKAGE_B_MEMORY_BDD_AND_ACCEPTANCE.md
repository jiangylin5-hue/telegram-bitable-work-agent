# Stage08 Package B：Business Memory BDD 与验收合同

## Status

- 2026-07-18 update：Task B5 已完成真实 disposable local PostgreSQL 收口与 Fix Round 2 独立复审（`PASS / 0 Critical / 0 Important`）。B5 首先复现同一 confirmed draft 并发 enqueue 的唯一键竞态，再以 draft transition row lock 在 idempotency lookup 前串行化已持久化草稿；`pg_blocking_pids` 实证第二会话被第一会话 `FOR UPDATE` 阻塞，释放后复用同一 reference-only event 且最终仅一条 outbox。Package B 模块套件 `120 passed`、Alembic 单一 head `20260718_0029`、compile/static/diff 检查均通过。B1-B5 现可关闭 Package B；该结论不表示 Stage08、Package C、真实 LLM 或部署完成。
- 2026-07-18 update：Task B4 已完成任务级实现、真实 local PostgreSQL 证据及两轮独立复审。仅精确受控的 `telegram_message + group_candidate_projection + stage06-binding:<uuid>` 可进入候选路径；`0.85` 阈值、递归载体拒绝、safe list/revoke、exact fingerprint、TTL/version 与 lifecycle fail-closed 均已覆盖。101 项 B4 测试和 134 项 B3/B2/runtime 回归通过。B5 已在后续更新中完成 Package B 最终 PostgreSQL/生命周期收口。
- 2026-07-18 update：Task B3 已完成任务级 TDD 和两轮独立复审。已确认草稿只在 audit 后 enqueue reference-only event；worker materialization 的 record/policy/字段/actor/scope 漂移均 fail closed，`identity_field_keys` 通过不返回原始值的内部 HMAC token 参与生命周期判定。81 项聚焦测试通过；该任务不作为 PostgreSQL outbox 并发/Package B 完整验收证据，相关证据留给 B5。Task B4 详细 SDD 已完成并开始实施。
- 2026-07-18 update：用户已确认 `table.settings.memory_policy` 的 B3 映射形状，且确认 B4 的部署候选最低置信度为 `0.85`。用户已确认专用 HMAC key 生成的内部 identity token，使 `identity_field_keys` 参与 same-identity 判定而不持久化原始值或向读取 API 暴露；B3 已进入 task-level TDD。
- Scope：版本化业务 Memory、已确认表格事件、受控群聊候选、冲突、TTL、撤销、删除和安全读取。
- Current Progress：B1（模型/迁移/UoW）、B2（类型化投影与安全生命周期）、B3（confirmed-draft reference-only outbox/HMAC identity）、B4（受控群候选与 safe API）和 B5（真实 PostgreSQL 生命周期/并发收口）均已完成任务级实现与独立复审。Package B 已关闭；其保留风险仅是后续 Package C 及 Stage08 运行时、真实 Provider、部署工作，不属于 Business Memory 包未完成项。
- Out of Scope：文件自动写入 Memory、向量索引、RAG、LangGraph、Provider 调用、Telegram 发送、新权限角色、生产部署。

## 共同前提

- 调用者身份已由既有 verified identity 解析；任何 scope 以 `workspace_id` 为最小锚点。
- Memory 不保存完整群聊、原始消息、prompt/response、隐藏字段、Telegram user ID、provider key 或链式推理。
- 表格事件仅在 `RecordChangeDraft.status="confirmed"` 后进入 Memory；pending/rejected/failed 草稿不产生 Memory。
- 所有写入经服务层、引用型 outbox 与审计；不改源记录、不确认草稿、不发送外部消息。

## B-01：持久化对象与来源版本

**Given** 一个已授权工作区与一个带版本的 source reference  
**When** 服务创建 `MemoryItem` 或 `MemoryExtractionCandidate`  
**Then** 必须持久化 `workspace_id`、类型、生命周期状态、scope、脱敏 payload、source refs、source fingerprint、版本和生命周期时间；JSONB 形状与 canonical 状态由数据库约束保护。  
**And** 同一 workspace/type/source fingerprint 只能幂等地对应一个 item/candidate。  
**And** 不允许任意文本或 raw 字段进入上述 JSONB。

## B-02：已确认表格事件

**Given** 一个配置了允许 Memory 规则的表和一个确认完成的记录变更  
**When** 确认服务完成其既有 record/audit 操作  
**Then** 仅创建带 workspace/table/record/version/policy reference 的 outbox event。  
**When** Memory materializer 处理该 event  
**Then** 重新读取当前记录、按规则和字段权限投影字段，并写入幂等 Memory 与脱敏审计。  
**And** event payload、audit 和 Memory 不包含源记录的未授权字段或原始 values。

## B-03：受控群聊候选

**Given** 一个绑定到工作区且仍有效的 Telegram 群聊 source reference  
**When** 一个高置信度、类型允许的结构化提取投影被提交给候选服务  
**Then** 服务创建 `candidate`，只保存归一化 payload 与 source reference。  
**And** 原始消息仅可短暂存在于 source adapter 进程内，不能进入候选、Memory、outbox、audit 或 API。

## B-04：冲突、版本与生命周期

**Given** 同一 identity key 的 active Memory  
**When** 等价事实再次到达  
**Then** 返回既有 item，不产生重复版本。  
**When** 同 identity key 的新事实与 active payload 不同  
**Then** 新对象为 `conflicted`，旧事实不被静默覆盖。  
**When** 管理者撤销、source 删除/撤权或 TTL 到期  
**Then** 对应对象分别迁移为 `revoked`、`deleted` 或 `expired`，并带脱敏 audit；读取立即 fail closed。

## B-05：安全读取与撤销 API

**Given** 已验证调用者  
**When** 调用 `GET /api/stage08/memory?workspace_id=...`  
**Then** 路由先执行 `workspace.read`，服务再核验 item 状态、TTL、source validity、relation scope 与每个 source field 的当前可见性。  
**And** 任何不确定性返回空投影/拒绝，绝不暴露不可读 ID、field key 或正文。  
**When** owner/admin 使用 `POST /api/stage08/memory/extractions/{id}/revoke` 并提交正确 `expected_version`  
**Then** candidate 迁移为 `rejected` 或关联 item 迁移为 `revoked`，且返回不含原始 payload 的生命周期回执。  
**And** foreign workspace、非管理权限、版本冲突和失效 source 均 fail closed。

## 验收证据

| Requirement | 最低证据 |
| --- | --- |
| B-01 | 单元合同测试 + local PostgreSQL JSONB/status/unique 约束 |
| B-02 | 确认草稿后 reference-only outbox + materializer 幂等测试 |
| B-03 | 候选脱敏、绑定 scope、无 raw 群聊保留测试 |
| B-04 | 等价幂等、冲突不覆盖、TTL/delete/revoke 读取拒绝测试 |
| B-05 | API 403/409、字段撤权后读取拒绝、审计脱敏测试 |

Package B 完成不等于真实 Provider 评测、向量检索、Milvus 决策或生产部署完成。
