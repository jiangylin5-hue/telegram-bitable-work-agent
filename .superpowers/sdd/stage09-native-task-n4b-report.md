# Stage09 N4B：离线迁移 Python 软链接兼容修复报告

## Scope

- 任务：修复 `verify-fixed-migration-offline.sh` 对正常 Python venv
  `bin/python` 软链接的无差别拒绝。
- 边界：仅修改本地离线发布校验器及其静态/fixture 测试；未执行 SSH、网络、Docker、服务操作、Git 提交或任何远程写入。

## Root Cause

生产常规 venv 的 `bin/python` 可以是软链接。原校验器要求
`[ ! -L "$python_bin" ]`，因此在运行离线 Alembic SQL 之前即失败，即使其
最终解释器是允许的系统 Python。

## RED

先只修改 `test-release-assets.sh`：fixture 将 `venv/<artifact>/bin/python`
设为指向已在复制校验器中列入允许范围的 fixture system Python 的软链接，并断言
生产脚本不再包含无差别的软链接拒绝。

执行：

```text
sh deploy/stage09-native/scripts/test-release-assets.sh
```

结果（预期失败）：

```text
migration-python-symlink-rejected: FAIL
```

该失败直接对应旧条件 `[ ! -L "$python_bin" ]`，而不是 fixture 或工具缺失。

## GREEN

最小修复：

1. 解析固定 venv Python 到 `resolved_python`。
2. 仅接受解析结果位于该 artifact venv 内，或精确为
   `/usr/bin/python3`、`/usr/bin/python3.12`。
3. 拒绝所有其他外部目标；仍要求最终目标为可执行普通文件。
4. 静态验证器检查此固定允许集、`realpath` 解析和旧拒绝条件不存在。
5. fixture 测试加入外部软链接目标拒绝断言。当前 Windows Git Bash 无原生软链接权限时，动态外部案例以 `[ -L ... ]` 为门，只在真实软链接环境执行；生产静态契约仍被验证。Linux/服务器环境会执行该拒绝案例。

## Verification

```text
sh -n deploy/stage09-native/scripts/verify-fixed-migration-offline.sh
sh -n deploy/stage09-native/scripts/verify-release-assets.sh
sh -n deploy/stage09-native/scripts/test-release-assets.sh
sh deploy/stage09-native/scripts/test-release-assets.sh
release-assets: PASS
sh deploy/stage09-native/scripts/verify-release-assets.sh
release-assets: pass
git diff --check
exit 0
```

`git diff --check` 对当前已跟踪差异返回 0；本任务涉及的 Stage09 文件是工作树中尚未跟踪的发布资产，因此还由上述 shell 语法和完整 fixture 测试覆盖。

## Changed Files

- `deploy/stage09-native/scripts/verify-fixed-migration-offline.sh`
- `deploy/stage09-native/scripts/test-release-assets.sh`
- `deploy/stage09-native/scripts/verify-release-assets.sh`

## Remaining Evidence Gate

尚未在服务器执行；P1 远程部署/离线 SQL 前，需在目标 Linux 主机上运行同一 fixture 测试及实际固定 release 校验器，取得真实 venv 软链接的执行证据。
