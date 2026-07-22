# Stage09 Native P1-A N4A 独立最终复审

## 结论

- 结果：**HOLD**
- Findings：`0 Critical / 1 Important / 0 Minor`
- 范围：仅复审 N4A release-layout、manifest、固定 revision 离线迁移脚本及其测试；未执行 SSH、网络、Docker、服务、数据库或 Git 写入。`inspect-native-host-readiness.sh` 是未执行的 P0a 草稿，不计作证据。

## 已关闭的复核点

- `verify-fixed-migration-offline.sh` 对两次 Alembic 调用均以 `env -u DATABASE_URL "DATABASE_URL=$offline_database_url"` 显式传入相同的非秘密 `stage09_p1` URL；不会继承父进程的 `DATABASE_URL`，也不会读取 runtime env 或 source 配置。
- 临时 fake-Alembic fixture 实际以父进程的 `DATABASE_URL=fixture-secret-value` 执行 wrapper，并只接受上述固定 URL；private `.env` 拒绝路径不回显 fixture 值。
- manifest 以排序后的相对 regular-file 路径生成 SHA-256，release root、其内容及所需的三项最小文件均拒绝符号链接；两次 fixture 生成的 manifest 字节一致。
- Git Bash 实测：`sh deploy/stage09-native/scripts/test-release-assets.sh` 与 `sh deploy/stage09-native/scripts/verify-release-assets.sh` 均通过；`git diff --check` 无 whitespace error（共享工作树仍有既有 CRLF warning）。

## Important

### I-02：所谓 sealed release layout 仍接受缺少 P1-B 必需部署资产的不完整 artifact

`verify-release-layout.sh` 仅要求 `backend/alembic.ini`、revision `20260720_0032` 和 `validate-runtime-presence.sh`（第 29–35 行）。因此，一个没有 Nginx 模板、PostgreSQL/Redis 配置、五个 systemd unit、迁移 wrapper 或 N1–N3 验证器的最小目录仍可通过 layout、生成 manifest，并被 N4A 视为 sealed。

这与原生计划第 2 节列为 P1-A/P1-B 必需交付的完整 `deploy/stage09-native` bundle 不一致；当前 fixture 也只创建上述三项最小文件（`test-release-assets.sh` 第 48–68 行），未证明删除任何 P1-B 运行资产会被拒绝。P1-B 若据此使用错误 artifact，可能在服务/数据面写入步骤才暴露缺件，破坏 sealed-release 门禁的含义。

**最小修复：** 在 layout validator 中以精确、非符号链接的 allowlisted required path 清单覆盖计划中的 runtime、Nginx、PostgreSQL、Redis、五个 unit 与 P1-B 会实际调用的 validators/wrapper；在 fixture 中先构造完整清单，再逐项删除至少一组代表性 application/data/ingress asset 并断言 layout/manifest/migration 均失败。修复后重新运行同一 Git Bash suite 并进行一次独立复审。

## 未计入完成的事项

- P0a 原生宿主机只读盘点、真实 `nginx -t`、真实固定 venv 的 Alembic `--sql` 输出、静态站点树、任何远程写入或服务启动，均仍是 P1-B 前/中的目标侧证据，不能由本地 fixture 代替。
