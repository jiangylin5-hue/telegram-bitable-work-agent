# Stage09 Native P1-A N4A-r2 发布包完整性修复记录

## Scope

- 修复独立复审提出的 I-02：sealed release 只校验三个最小文件，不能保证 P1-B 原生部署包完整。
- 仅修改仓库内发布布局校验、离线 fixture 和静态校验；未执行 SSH、网络、Docker、服务、数据库或 Git 写入。

## Root Cause

`verify-release-layout.sh` 原先只要求 `alembic.ini`、固定迁移 revision 和运行时预检脚本。因而即使 Nginx、PostgreSQL/Redis、systemd unit 或其验证工具缺失，artifact 仍可能生成 manifest 并被误判为 sealed。

## Remediation

- 将 P1-B 当前必需的 backend migration、runtime 示例、Nginx、PostgreSQL、Redis、五个 systemd unit 与九个部署脚本写为固定、逐项的 regular-file/non-symlink allowlist。
- 保留对真实 `.env`、`runtime.env`、`.git`、`node_modules`、`secrets` 的拒绝；允许唯一必需的 `runtime/runtime.env.example`。
- fixture 逐项创建完整 allowlist，先证明 deterministic manifest 与固定 revision 离线验证仍可运行，再删除 API unit，断言 layout 与 manifest 都以通用输出拒绝且不泄露 fixture 路径或伪秘密。
- 静态 verifier 对完整 allowlist 与缺失关键 unit 的回归断言进行检查。

## Verification

- `C:\\Program Files\\Git\\bin\\bash.exe deploy/stage09-native/scripts/test-release-assets.sh` → `release-assets: PASS`
- `C:\\Program Files\\Git\\bin\\bash.exe deploy/stage09-native/scripts/verify-release-assets.sh` → `release-assets: pass`
- `git diff --check` → 通过；共享工作树仅报告既有 CRLF 转换 warning，没有 whitespace error。

## Remaining Boundary

- 此修复只提供仓库内、无目标环境的静态与 disposable-fixture 证据。
- P0a/P1-B 的真实 host readiness、Nginx 配置测试、原生 venv Alembic `--sql`、静态站点树、远程写入与服务启动仍未执行。
