# Stage09 N4B：离线迁移 venv 软链接复核

## Scope

- 复核对象：`deploy/stage09-native/scripts/verify-fixed-migration-offline.sh` 的 Python venv 软链接兼容逻辑，以及其 `test-release-assets.sh` 覆盖。
- 边界：只读、本地；未执行 SSH、网络、Docker、数据库、Redis、systemd、Nginx 或任何远程写入；本复核未修改实现。

## 结论

`HOLD`。存在 1 个 Critical 和 1 个 Important；在修复并复审前，不能把 N4B 当作可在目标主机执行离线 Alembic SQL 的证据。

## Critical

### C-01：通过 `realpath` 验证后改用解析后的系统 Python 执行，绕过了 venv

当前脚本先保存 venv 入口：

```sh
python_bin="$venv_root/bin/python"
resolved_python=$(realpath "$python_bin") || fail
```

随后在允许 `/usr/bin/python3` 或 `/usr/bin/python3.12` 时执行：

```sh
python_bin="$resolved_python"
```

常规 Linux venv 的 `bin/python` 正是到基础解释器的软链接。Python 只有以 venv 内的入口路径启动时，才会从相邻的 `pyvenv.cfg` 建立 venv 的 `sys.prefix` 与 site-packages；若改以 `/usr/bin/python3` 的真实路径启动，则会使用基础解释器环境。于是 `-m alembic` 可能找不到部署 venv 内的 Alembic/SQLAlchemy/psycopg，或者更糟地误用系统级安装的版本。

这不是“软链接拒绝”问题，而是“验证用的解析路径被错误地复用于执行”问题。N4B 报告的 fixture 仅以一个伪解释器响应固定参数，无法证明真实 Python 的 `sys.prefix`、`sys.base_prefix` 和 venv site-packages 保持正确，因此未暴露该缺陷。

**精确修复：**保留 `python_bin="$venv_root/bin/python"` 作为唯一执行路径；`resolved_python` 仅用于允许列表/常规文件校验，绝不可赋回 `python_bin`。两处 Alembic 调用必须继续使用原 venv 入口：

```sh
env ... "$python_bin" -m alembic ...
```

修复后仍允许 `realpath "$python_bin"` 恰好是 venv 内路径或受控基础 Python 路径，但它只证明入口链路可接受，不改变启动路径。

## Important

### I-01：现有 fixture 把“解析后路径执行”当作成功条件，没有验证 venv 语义

`test-release-assets.sh` 创建 `venv/<artifact>/bin/python -> fixture_system_python`，而伪解释器只检查 Alembic 参数和 `DATABASE_URL`。在当前缺陷实现里，它仍会通过，因为脚本实际调用的就是 `fixture_system_python`。测试因此没有区分“通过 venv 入口执行”与“通过真实系统路径执行”。

**精确修复：**保留现有无秘密 fixture，并加入一个可在 POSIX 主机运行的回归断言：伪解释器必须收到的 `$0` 是 `venv/<artifact>/bin/python` 入口路径（而非解析后的 `fixture_system_python`）；或使用真实临时 venv，断言 `sys.prefix != sys.base_prefix` 且 `python -m alembic` 从该 venv 解析。前者可在既有无网络 fixture 内稳定执行，后者应在 P0a 的目标 Linux 主机再次验证。静态验证同时应拒绝 `python_bin="$resolved_python"` 之类的重新赋值。

## Minor

无。

## 本地证据与限制

- 已完整阅读目标脚本、N4B 实现报告和 release fixture；缺陷由 venv 入口路径到两处 `-m alembic` 的数据流直接确认。
- 当前 Windows 工作站没有 POSIX `sh`，因此无法在此处执行原 `.sh` fixture；这不影响上述静态根因判定。目标 Linux P0a/P1-B 仍需执行修复后的 fixture 与实际固定 venv 的 `--sql` 验证。

