# Stage09 N4B R2：离线迁移虚拟环境执行路径修复报告

## Scope

- 仅修复 `verify-fixed-migration-offline.sh` 将已解析的系统 Python 覆盖为实际执行路径的问题。
- 未执行 SSH、远程操作、Docker、安装、数据库或 Redis 命令；未改动 N4B R1 文件。

## RED

先只修改 `deploy/stage09-native/scripts/test-release-assets.sh`：假的 Python 要求其 `$0` 必须是 fixture 的 `venv/<artifact>/bin/python`；同时 fixture 的受控 `realpath` 断言该入口解析至允许的 fixture system Python。Git for Windows 不一定能创建 POSIX symlink，因此 fixture 仅在本地兼容层中模拟该解析结果；Linux 目标上的实际 symlink 仍由生产校验的 `realpath` allowlist 验证。

命令（Git for Windows `sh`，其工具目录已放入 `PATH`）：

```text
sh deploy/stage09-native/scripts/test-release-assets.sh
```

结果：退出码 `1`，输出 `migration-fixture: FAIL`。失败原因正确：旧实现将 `python_bin` 改写为 `resolved_python`，因此 fake Python 的 `$0` 是 system Python 而非 venv 入口。

## GREEN

最小生产修复：仅保留 `resolved_python` 用于安全 allowlist 校验；不再给 `python_bin` 赋值。两个 Alembic 调用继续执行原始 `$venv_root/bin/python`。

静态校验同步拒绝 `python_bin="$resolved_python"`，并要求回归测试保留 `$0` 与允许解析目标断言。

验证结果：

```text
sh -n deploy/stage09-native/scripts/test-release-assets.sh                         PASS
sh -n deploy/stage09-native/scripts/verify-fixed-migration-offline.sh              PASS
sh -n deploy/stage09-native/scripts/verify-release-assets.sh                        PASS
sh deploy/stage09-native/scripts/test-release-assets.sh                             PASS (release-assets: PASS)
sh deploy/stage09-native/scripts/verify-release-assets.sh                           PASS (release-assets: pass)
git diff --check                                                                     PASS
```

`git diff --check` 仅输出共享工作树既有的 LF/CRLF 提示，退出码为 0；本任务范围没有空白错误。

## Changed files

- `deploy/stage09-native/scripts/test-release-assets.sh`
- `deploy/stage09-native/scripts/verify-fixed-migration-offline.sh`
- `deploy/stage09-native/scripts/verify-release-assets.sh`

