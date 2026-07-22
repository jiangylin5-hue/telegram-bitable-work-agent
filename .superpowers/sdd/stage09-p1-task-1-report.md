# Stage09 P1 Task 1 Report

## Status

- Result: `completed-local-documentation-only`
- Scope: 细化 Stage09 P1 的可执行本地部署包计划；未创建部署资产、未连接服务器、未写入远端、未执行迁移、未修改 Stage03 资产。
- Date: 2026-07-22

## Changed Files

| File | Change |
| --- | --- |
| `project-docs/08-implementation/STAGE_09_PRODUCTION_READINESS_AND_DEPLOYMENT_PLAN.md` | 将 P1 扩展为带本地包边界、隔离命名、runtime key-presence、migration dry-run、Caddy host、只读/写入边界、观察、回滚与 ledger 规则的逐步 runbook。 |
| `.superpowers/sdd/stage09-p1-task-1-report.md` | 本任务报告。 |

## Key Decisions

1. P0 已证明远端运行的是历史 Stage03（`20260707_0016` 且没有 `vector` extension）；P1 必须在新建的 `stage09-p1` Compose project、空 PostgreSQL/Redis 数据面和独立 runtime 下运行，绝不原地升级或读取 Stage03 数据。
2. `deploy/stage07-acceptance/` 是 Stage07 S6 的历史验收资产与测试依赖，只能作为只读结构参考。P1-A 以后必须新建 `deploy/stage09-p1/`，本任务不改写 Stage07 文件或其资产。
3. P1 migration 目标显式固定为当前唯一 Alembic revision `20260720_0032`。先离线 `--sql` dry-run，再只对 P1 空库执行实际 upgrade；不使用未记录的 `head`/`latest`。
4. P1 的运行态强制 `TELEGRAM_SEND_MODE=dry_run`、`LLM_ENABLED=false`、`AGENT_WORKFLOW_MODE=fake`、`PROVIDER_MODE=disabled`，且 Telegram allowlist 为空；P2 的 token、目标和 `restricted_test` 都不进入 P1。
5. Caddy 只允许一个新 hostname host block，静态路径到 P1 Web、其他路径到 P1 API，并以候选验证、备份、追加、回读 Stage03 健康和精确移除构成回滚证据。
6. Stage07 Browser/UI acceptance 保持 P3 的独立门禁；P1 通过不能替代或隐含该验收。

## Verification

- 已读取并对齐：`AGENTS.md`、Stage09 计划、P0 readiness inventory、Stage07 S6 isolated deployment SDD、`deploy/stage07-acceptance/*`。
- 已核对当前 Alembic 链：`20260720_0032` 为当前文件链末端，且其 migration 创建 `vector` extension。
- 已核对现有 runtime validator、Compose/Caddy 模板、`/health` 与 webhook 拒绝路径，以避免在计划中虚构运行时行为。
- `git diff --check` 已在文档写入后通过（exit code `0`）；只有工作树既有文件的 CRLF 提示，无 whitespace error。

## External Prerequisites / Blocked Conditions

| Condition | Status | Effect |
| --- | --- | --- |
| 用户明确授权 P1-B 的服务器、固定 artifact、维护窗和可写资源 | `blocked-external` | 不得传输 artifact、创建远端目录/runtime/volume、迁移或启动服务。 |
| 一个新的、授权提供且解析到目标服务器的独立 HTTPS hostname | `blocked-external` | 不得渲染/激活 P1 Caddy host，也不能取得 HTTPS 证据。 |
| 已盘点并允许接入的 Caddy ingress Docker network | `blocked-external` | P1 API/Web 不能加入 ingress，不能启动 HTTPS 暴露。 |
| P2 的单次 Telegram chat、授权与时间窗 | `not-requested` | P1 不等待、不配置且不执行；仅在 P1 完成后单独申请。 |

## Remaining Risks

- 当前工作树有其他代理的未提交修改；本任务只改 Stage09 计划及本报告，未清理、暂存、提交或覆盖任何既有工作。
- P1-A 所需 `deploy/stage09-p1/` 独立资产尚未创建，必须在后续经审阅的本地配置变更中实现并按文档验证。
- P1 所需独立 hostname 是外部阻断条件；没有它只能保持 `blocked`，不能用 Stage03 host、临时 IP 或真实域名猜测替代。

## Temporary Cleanup

- 未创建临时部署文件、runtime env、离线 SQL、容器、卷、远端目录或外部消息；无需清理。
