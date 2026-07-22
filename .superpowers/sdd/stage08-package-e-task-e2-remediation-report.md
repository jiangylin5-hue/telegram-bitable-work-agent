# Stage08 Package E / E2 复审问题修复报告

## 触发与范围

E2 首次独立复审为 `0 Critical / 2 Important / 0 Minor`。本修复仅修改 E2 service 与 E2 unit/PostgreSQL tests；未变更 schema、migration、API、权限矩阵、Docker、Provider、Telegram 或业务持久化边界。

## I-01：target scope 不再回退为 project scope

此前当 current member/chat_user binding/group-business mapping 缺失、撤销、歧义或与 target 不匹配时，`_derive_business_scope_ids` 会返回 `(None, target_record_id)`。现在只在**恰好一个** active binding 和 mapping 存在、且 target 为空或匹配该 mapping 时，才返回该 mapping 的完整 customer/project pair；否则若 command 带 target，立即以固定 `stage08_collaboration_target_scope_denied` 拒绝，safe result 为 `degraded` 且 `read_child_count=0`。

新增覆盖：revoked mapping、ambiguous mapping、inactive binding、无 group mapping 的 PostgreSQL target case；均不会生成 scoped C1/D4 material 或写入 audit/outbox/idempotency。

## I-02：D4 失败限制在 retrieval branch

`search`、`render_private_evidence` 与 `safe_view` 现在被同一个局部异常边界包裹。异常只映射为固定 `retrieval_unavailable` outcome，清空本 branch 的 temporary evidence/citation count；不回显 provider error，且已获准的 C3 material 仍然能形成 safe result。

新增三项注入式负例分别让 `search`、`render`、`safe_view` 抛出含 secret 的运行时异常，断言：调用不抛出、结果仍为 C3 `internal_evidence`、`retrieval_unavailable` 存在、secret 不在 repr/safe JSON，且没有持久副作用。

## 新鲜验证

```text
133 passed in 2.88s
tests/unit/test_stage08_context_composition_service.py
tests/unit/test_stage08_retrieval_provider.py
tests/unit/test_stage08_collaboration_contracts.py
tests/unit/test_stage08_collaboration_graph.py
tests/unit/test_stage08_collaboration_service.py

17 passed in 9.94s
tests/integration/test_stage08_retrieval_pgvector.py
```

`compileall` 已通过。PostgreSQL 使用现有 loopback disposable pgvector 容器和单事务 rollback；没有打印或写入 DSN，没有外部网络、Telegram、LLM 或 provider 调用。

## 状态

等待新的 fresh independent review；本报告不关闭 E2、Package E 或 Stage08。
