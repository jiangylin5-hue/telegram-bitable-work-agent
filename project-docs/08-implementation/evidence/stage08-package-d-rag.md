# Stage08 Package D：RAG / pgvector 实施证据

## Status

- Document status：`D0-D5 implementation evidence awaiting independent Package D review`
- Evidence date：2026-07-21
- Scope：Package D 的专用 pgvector 环境、source/chunk 合同、索引/清理 worker、混合检索与引用重验、受控 reindex API。
- Boundary：本证据不关闭 Package D、D5 或 Stage08，不证明真实 embedding/LLM 质量、外部系统调用或生产部署完成。

## 1. D0-D4 已有证据摘要

- D0：专用、loopback、可丢弃的 `pgvector/pgvector:pg17` 环境；本轮读回 `vector=0.8.5`。
- D1：Knowledge source/chunk strict contract、GIN/HNSW、composite workspace/source/version FK；唯一 Alembic head 为 `20260720_0032`。
- D2：受控 Memory projection、确定性 chunk、root-lineage fingerprint、reference-only index/cleanup outbox。
- D3：显式 test embedding adapter、index/cleanup worker、重放/漂移/失败状态收口。
- D4：PostgreSQL keyword + vector + structured narrowing、检索前后授权重读、安全 citation；fresh-current-state 独立复审已通过。

上述事项的详细 RED/GREEN 和独立复审记录保留在各任务报告。本文件重点补充 D5 以及最终 D0-D5 PostgreSQL 组合证据。

## 2. D5 受控 Reindex API

### 2.1 API 与响应

- Endpoint：`POST /api/stage08/knowledge/reindex`。
- request body 字段精确为：`workspace_id`、`knowledge_source_id`、`idempotency_key`、`trace_id`。
- response 字段精确为：`ticket_id`、`status`；`status` 固定为 `accepted`。
- `ticket_id` 对应已验证 source 的既有或新建 `stage08.knowledge.index_requested` reference event ID，不返回 source/chunk/record/field ID、正文、query、scope、hash、embedding、profile、actor、authority 或 audit 状态。
- unknown/嵌套 carrier、projection/chunk/embedding/query/filter/scope/source status/ticket/actor/role 字段均在 dispatch 前以固定脱敏 422 拒绝。

### 2.2 权限与 source 真源

- route 从 verified identity 派生 Actor，并调用既有 `member.manage`。
- service 再次读取 current workspace/member；只接受 active `owner`/`admin`。
- `manager`、builder、operator、viewer、非成员、inactive member 均 fail closed；未修改 `ROLE_ACTIONS`，未新增角色。
- source 不存在、跨 workspace 为非披露 403；terminal lifecycle、过期、source-specific verifier 失败为固定 409。
- 当前只允许经 read-only Memory projection 与完整 root-lineage 复核的 `memory_item`；`document_projection` / `approved_summary` 因无 approved origin verifier 继续 fail closed。

### 2.3 Fresh current-state corrective evidence

初始 PostgreSQL RED 在同一 held SQLAlchemy Session 先缓存 active member，再用 Core/current database operation 将其改为 inactive。旧实现没有抛出拒绝，证据为：

```text
1 failed, 15 deselected
Failed: DID NOT RAISE PlatformValidationError
```

最小 GREEN 只在 D5 service 内采用局部 `select(...).execution_options(populate_existing=True, autoflush=False)` 与 `session.no_autoflush`，重读 workspace、member、source 和 Memory lineage metadata。没有 `expire_all()`、没有 UoW/role/schema 扩展。

最终 held-session PostgreSQL 用例分别验证：

- member 从 active 变 inactive：403/fail closed；
- source 从 active 变 revoked：409/fail closed；
- Memory 从 active 变 revoked：409/fail closed；
- 三种拒绝均不新增 outbox、idempotency 或 audit；
- revalidation 期间无关 pending Workspace 仍留在 `session.new`，数据库读不到该行。

### 2.4 Idempotency、Outbox 与 Audit

- 使用既有 Stage06 idempotency record；operation 为固定 `stage08.knowledge_reindex`。
- 语义 fingerprint 绑定 workspace、source、server-derived actor 与 caller trace；服务端 idempotency trace 由 operation、request fingerprint 和 key 派生，不持久化 raw caller trace。
- 同 workspace/operation/key + 同语义重放同一 `ticket_id/status`，不重复写 event/audit；同 key 改 source 或 trace 为 `idempotency_conflict`。
- outbox 继续使用 D2 reference-only 字段：workspace/source reference、content version、projection hash reference、SHA-256 trace reference；不含正文、chunk、embedding、keyword、query、scope、Memory payload、群聊或 provider response。
- audit 只记录固定 event/status、source type、content version 和当前 `member.manage` permission snapshot；原始 trace、source 内容、query/scope/embedding 均未写入。

## 3. Fresh 验证结果

从 `backend` 执行，pytest 均使用 `-W error -p no:cacheprovider`：

| Verification | Fresh result |
| --- | --- |
| D5 service + API | `109 passed in 11.19s` |
| D1-D5 focused contracts/chunking/service/provider/API | `220 passed in 12.12s` |
| dedicated pgvector D0-D5 matrix | `16 passed in 7.95s` |
| Alembic heads | `20260720_0032 (head)`，唯一 head |
| pgvector extension | `0.8.5` |
| compileall | exit `0` |
| production privacy/external dependency scan | `expire_all=0`、外部 provider/network import=0、默认 test provider 构造=0、direct Memory item payload read=0 |
| `git diff --check` | exit `0`；共享 dirty worktree 仅有既有 CRLF conversion warning，无 whitespace error |

新 D5 API 测试只在该测试模块 import `TestClient` 前精确忽略现有 `StarletteDeprecationWarning`；没有扩大 production warning filter，也未修改全局 pytest/config。所有有效验收轮次均为 0 skip。

## 4. PostgreSQL Cleanup Readback

完整 16 项 pgvector integration 在外层事务回滚后读回：

```text
stage08_knowledge_sources=0
stage08_knowledge_chunks=0
outbox_events=0
stage06_idempotency_records=0
ops_audit_events=0
```

没有保留测试 source/chunk/event/idempotency/audit、临时脚本、credential、DSN 或数据集。专用 disposable pgvector container 继续为 Package D 独立复审保留；它不构成 staging/production 证据。

## 5. Skipped Work / Remaining Gate

- 本轮未运行 full backend suite；按 D5 brief 运行 D1-D5 focused 与完整专用 pgvector matrix。
- 未调用真实 embedding、LLM、OpenRouter、Telegram、HTTP、Redis、LangGraph、Milvus、浏览器、Mini App、staging 或 production。
- 没有实现 document upload/query/citation public API，也没有开始 Package E/F。
- D5 与 Package D 必须经过新的独立 Package D review 后，才可由上层任务决定是否关闭。本证据本身不作关闭声明。
