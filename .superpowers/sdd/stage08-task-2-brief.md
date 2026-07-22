# Stage08 Package A · Task 2：Execution Ticket 持久化与 UnitOfWork

## 目标

在已确认且已写入契约的 Stage08 Runtime Foundation 中，持久化最小 `Stage08ExecutionTicket`，并使既有 `Stage06PlatformUnitOfWork` 的内存与 SQLAlchemy 两种实现都可安全读写它。PostgreSQL 仍是唯一真源；本任务不创建运行服务、路由、Tool Gateway、Memory/RAG 或 Provider/Telegram 调用。

## 已确认的不可变约束

- Ticket 状态唯一集合为：`planned`、`executing`、`succeeded`、`failed`、`denied`、`cancelled`、`timed_out`、`expired`。
- 状态迁移语义为：`planned → executing → 终态`；本任务只建模/约束，不实现状态驱动服务。
- `pending_confirmation` 和 `confirmed` 只属于既有 `RecordChangeDraft`，不得用于 execution ticket。
- `tool_summary` 只保存脱敏、结构化摘要；不得保存 prompt、response、raw_text、token、api_key 或任何自由文本输出。
- `trace_id` 在同一 workspace 中唯一；不是全局唯一。
- 只允许本地、可抛弃 PostgreSQL 运行集成测试。复用项目现有 `STAGE06_LOCAL_DATABASE_URL` 及 `classify_local_postgres_url` 的安全门禁；不设置、不展示任何连接凭据。

## 允许变更的文件

- 新建 `backend/app/models/stage08_runtime.py`
- 新建 `backend/alembic/versions/20260717_0028_stage08_runtime_foundation.py`
- 修改 `backend/app/models/__init__.py`
- 修改 `backend/app/services/stage06_platform.py`
- 新建 `backend/tests/integration/test_stage08_runtime_postgres.py`
- 新建/追加 `.superpowers/sdd/stage08-task-2-report.md`

除以上文件和报告外不要修改任何文件。不得 stage、commit、reset、checkout。

## 交付物

### 1. ORM 与迁移

创建 `Stage08ExecutionTicket`，表名为 `stage08_execution_tickets`。复用 `UuidPrimaryKeyMixin` 与 `TimestampMixin`，并额外具有可空 `completed_at`（带时区）。字段必须为：

- `workspace_id: UUID`，外键 `workspaces.id`，非空；
- `employee_id: UUID`，外键 `digital_employees.id`，非空；
- `actor_id: str`，最大长度 120，非空；
- `action: str`，最大长度 120，非空；
- `trace_id: str`，最大长度 120，非空；
- `request_fingerprint: str`，最大长度 64，非空；
- `status: str`，最大长度 40，非空；
- `budget: dict`，PostgreSQL `JSONB`，非空；
- `tool_summary: list`，PostgreSQL `JSONB`，非空；
- `completed_at: datetime | None`，带时区，可空。

必须有下列数据库约束/索引，并以稳定命名显式指定：

- `(workspace_id, trace_id)` 的 `UniqueConstraint`，名称 `uq_stage08_execution_ticket_workspace_trace`；
- `status IN ('planned', 'executing', 'succeeded', 'failed', 'denied', 'cancelled', 'timed_out', 'expired')` 的 `CheckConstraint`，名称 `ck_stage08_execution_ticket_status`；
- `(workspace_id, status, created_at DESC)` 索引，名称 `ix_stage08_execution_ticket_workspace_status_created`。

迁移 revision 必须是 `20260717_0028`，`down_revision = "20260713_0027"`，upgrade/downgrade 对称。迁移须使用与项目现有迁移一致的 PostgreSQL 可执行 SQLAlchemy/Alembic 写法，不依赖 autogenerate。

在 `app.models` registry 导入并公开模型，确保 Alembic `target_metadata` 实际包含表。

### 2. UnitOfWork 接口与两种实现

在 `Stage06PlatformUnitOfWork` protocol、`InMemoryStage06PlatformUnitOfWork` 与 `SqlAlchemyStage06PlatformUnitOfWork` 中增加完全一致的最小方法：

```python
def add_execution_ticket(self, ticket: Stage08ExecutionTicket) -> None: ...
def get_execution_ticket(self, ticket_id: UUID) -> Stage08ExecutionTicket | None: ...
def get_execution_ticket_by_trace(
    self, workspace_id: UUID, trace_id: str
) -> Stage08ExecutionTicket | None: ...
```

内存实现须维护独立 `execution_tickets` 集合并按 workspace+trace 精确匹配。SQLAlchemy 实现须使用 session 和受限条件查询；本任务不需要锁方法或状态更新方法。

### 3. 集成测试（TDD）

先写 `backend/tests/integration/test_stage08_runtime_postgres.py` 的失败测试，再写实现。测试应复用 `tests.integration.test_stage07_governance_postgres` 中的 `stage06_postgres` fixture/本地数据库门禁或等价的受保护 fixture；不要连接远程数据库。

至少覆盖：

1. migration 后 schema 含表、必要列、显式 unique/check/index；
2. 通过 SQLAlchemy UoW 创建一条 `planned` ticket、commit 后可按 id 与 workspace+trace 读回，JSONB 数据保持结构；
3. 相同 workspace + trace 的第二条 ticket 在真实 PostgreSQL 中因唯一约束失败；不同 workspace 可使用相同 trace；
4. DB 约束实际拒绝 `pending_confirmation` 和 `rejected` ticket status（不能只测 Pydantic）；
5. InMemory UoW 的按 id 与 workspace+trace 查询行为可由集成或紧邻最小测试覆盖。

TDD 证据须在报告里明确记录先 RED（缺模型/表/方法）、后 GREEN。运行：

```powershell
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
alembic heads
git diff --check -- backend/app/models/stage08_runtime.py backend/alembic/versions/20260717_0028_stage08_runtime_foundation.py backend/app/models/__init__.py backend/app/services/stage06_platform.py backend/tests/integration/test_stage08_runtime_postgres.py
```

如果本机未配置受门禁保护的本地 PostgreSQL，保留 pytest 的明确 skip 原因，仍运行迁移/模型的可行静态检查并在报告中如实记录；不要将此当作通过的真实 PostgreSQL 证据。

## 明确禁止

- 不调用 OpenRouter/任何 LLM Provider、Telegram、webhook 或外部 API。
- 不运行或新增外部写入、真实消息发送、API route、gateway、执行服务、memory/RAG、向量库或 Milvus。
- 不保存未脱敏 tool input/output；不修改 Task 1 的 Pydantic contracts。
- 不改现有 Stage07 前端或无关测试。

## 完成回报

报告须列出：改动文件、RED/GREEN 命令和结果、Alembic head、真实 PostgreSQL 结果或明确 skip、`git diff --check`、无外部调用确认、未完成风险。
