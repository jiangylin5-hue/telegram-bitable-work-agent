# Stage08 Package A Task 2 实施报告

## Status

完成，待独立 task review。

## 改动文件

- `backend/app/models/stage08_runtime.py`：新增 `Stage08ExecutionTicket` ORM、canonical ticket 状态检查、workspace 内 trace 唯一约束和按 workspace/status/created_at 的索引。
- `backend/alembic/versions/20260717_0028_stage08_runtime_foundation.py`：新增对称的 Stage08 execution ticket 迁移，revision 为 `20260717_0028`、`down_revision` 为 `20260713_0027`。
- `backend/app/models/__init__.py`：注册并公开模型，使 Alembic `metadata` 收录该表。
- `backend/app/services/stage06_platform.py`：为 protocol、内存和 SQLAlchemy UnitOfWork 增加完全一致的新增、按 ID 查询、按 workspace+trace 查询方法。
- `backend/tests/integration/test_stage08_runtime_postgres.py`：覆盖内存查询、真实 PostgreSQL schema、round-trip、JSONB、workspace 内 trace 唯一性、跨 workspace 相同 trace 以及数据库拒绝过时状态。

## TDD Evidence

### RED

命令：

```powershell
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
```

结果：按预期在 collection 阶段失败：`ModuleNotFoundError: No module named 'app.models.stage08_runtime'`。失败原因是目标 ORM 模型尚未实现。

### GREEN

命令：

```powershell
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
```

结果：`3 passed in 4.30s`。其中 PostgreSQL 相关两项测试使用现有 `stage06_postgres` fixture；该 fixture 经 `classify_local_postgres_url` 门禁确认后会重置 public schema，并从空库升级至 migration head。

## 静态和迁移验证

命令：

```powershell
python -m compileall -q app/models/stage08_runtime.py alembic/versions/20260717_0028_stage08_runtime_foundation.py app/services/stage06_platform.py
alembic heads
python -c "from app.models import metadata; assert 'stage08_execution_tickets' in metadata.tables"
git diff --check -- backend/app/models/stage08_runtime.py backend/alembic/versions/20260717_0028_stage08_runtime_foundation.py backend/app/models/__init__.py backend/app/services/stage06_platform.py backend/tests/integration/test_stage08_runtime_postgres.py
```

结果：编译通过；Alembic 输出唯一 head `20260717_0028 (head)`；模型已在 metadata 注册；`git diff --check` exit 0。

## 外部调用与安全边界

- 未调用 OpenRouter、任何 LLM Provider、Telegram、webhook 或外部 API。
- 未新增 API route、gateway、执行服务、Memory/RAG、向量库或 Milvus。
- 唯一数据库操作是已批准的可抛弃本地 PostgreSQL 集成测试；未展示或修改连接凭据。
- `tool_summary` 仅保存既有 Task 1 `RedactedToolResult` 合同所定义的脱敏结构化摘要；本任务未引入任何原始 input/output 字段。

## Remaining Risks

- 本任务只建立 ticket 的持久化边界和状态集合约束；状态转换、权限/预算策略、幂等和脱敏合同到 ORM 的调用链将由后续 Task 3–4 实现并验收。
- 当前工作树含用户既有的未提交 Stage07 改动；本任务未 stage、commit、reset 或 checkout。

## 审查回修：JSON 形状与 canonical 状态数据库约束

### 回修内容

- 在 ORM 与迁移中增加命名稳定的 `ck_stage08_execution_ticket_budget_object`：`jsonb_typeof(budget) = 'object'`。
- 在 ORM 与迁移中增加命名稳定的 `ck_stage08_execution_ticket_tool_summary_array`：`jsonb_typeof(tool_summary) = 'array'`。
- 集成测试现在检查三个 check 名称、完整 canonical 状态集合，并确认 schema check 不含 `pending_confirmation`、`confirmed`、`rejected`。
- 真实 PostgreSQL 测试现在拒绝上述三个旧状态、任意非白名单状态、list/string 形状的 `budget`，以及 object/string 形状的 `tool_summary`；每次 `IntegrityError` 后均执行 `rollback` 后继续验证。

### 回修 TDD Evidence

先只补测试断言和错误 JSON/status 用例后运行：

```powershell
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
```

RED：`2 failed, 1 passed`。一项失败显示两个 JSON check 名称不存在；另一项显示错误 JSON `budget` 形状未被数据库拒绝。

补齐 ORM/迁移约束后，运行：

```powershell
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
alembic heads
```

GREEN：`3 passed in 5.05s`，唯一 Alembic head 仍为 `20260717_0028 (head)`。这些 PostgreSQL 结果仍仅来自现有受门禁、可抛弃的本地测试库；未调用任何外部系统。

## 审查回修：状态白名单精确集合

`ck_stage08_execution_ticket_status` 的 PostgreSQL inspector SQL 现在通过确定性正则 `r"'([^']+)'"` 提取所有单引号 literal，并将所得集合与 canonical 八项状态做严格相等比较，而非仅做包含/排除断言。这样若未来 check 被额外放宽，测试会失败。

### 回修 TDD Evidence

生产状态 check 已符合 canonical 八项，因此没有生产代码改动。为确认新断言真实捕获差异，先将测试的预期集合设为可控错误值 `{"deliberate-control-mismatch"}`，运行：

```powershell
python -m pytest -q tests/integration/test_stage08_runtime_postgres.py
```

RED：`1 failed, 2 passed`，失败显示 inspector 解析出的真实状态集合与该错误期望不相等。

再将期望恢复为 canonical 八项后运行同一命令：

GREEN：`3 passed in 4.20s`。根目录 scoped `git diff --check` 亦为 exit 0。未发生 Provider、Telegram、API 或其他外部调用，未 stage 或 commit。
