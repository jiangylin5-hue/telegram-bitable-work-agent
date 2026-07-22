# Stage08 Package A · Task 2 独立审查包

## 审查范围

仅审查以下绝对路径；不修改任何文件，不运行外部 Provider/Telegram/API，不 stage/commit：

- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\.superpowers\sdd\stage08-task-2-brief.md`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\.superpowers\sdd\stage08-task-2-report.md`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\app\models\stage08_runtime.py`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\alembic\versions\20260717_0028_stage08_runtime_foundation.py`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\app\models\__init__.py`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\app\services\stage06_platform.py`
- `D:\telegram多维表格和工作智能体的开发\.worktrees\stage07-mini-app-ui\backend\tests\integration\test_stage08_runtime_postgres.py`

## 核验重点

1. `Stage08ExecutionTicket` 表、字段类型、外键、JSONB 与 `completed_at` 是否与简报逐项一致；`tool_summary` 是否默认/建模为结构化 JSON 而非自由文本。
2. ticket 状态是否只有 8 个 canonical 值；`pending_confirmation`/`confirmed`/`rejected` 没有进入 ticket 约束。
3. migration revision/down revision 正确、upgrade/downgrade 对称，且约束/索引命名稳定、实质存在。
4. `app.models` registry 确保 Alembic metadata 能看见新表。
5. Protocol、InMemory、SQLAlchemy 三处方法签名一致；内存按 `(workspace_id, trace_id)` 精确匹配，SQL 查询限定 workspace 与 trace。
6. 集成测试是否是受 `STAGE06_LOCAL_DATABASE_URL` 门禁保护的真实 PostgreSQL 测试，实际断言 table/columns/unique/check/index、往返 JSONB、同空间重复失败、跨空间复用、旧状态 DB 拒绝以及 InMemory 查询。
7. 不得把 runtime service、API、gateway、memory/RAG、Provider/Telegram 或 Stage07 无关改动带入。

## 回报格式

请按 `Critical`、`Important`、`Minor`、`Spec compliance verdict`、`Task quality verdict` 返回，尽量指出文件与行号。实现者报告的命令结果可阅读但必须区分“已复跑”和“未复跑”。
