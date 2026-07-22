# Stage09 受控真实联调 Runtime Profile 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不放开 Provider、完整 prompt/response 保存或未授权 Telegram 接收人的前提下，让 Stage09 原生 systemd 能运行真实 OpenRouter 与 allowlist 限定的 Telegram `restricted_test`。

**Architecture:** 复用现有 `/etc/stage09-p1/runtime.env` 和 `validate-runtime-presence.sh` 作为唯一 systemd 启动门禁。保留 P1 的数据库、Redis、artifact 与 host 隔离校验；仅将运行时组合从“永远 dry-run/LLM-off”改成两个显式安全组合：`baseline`（现有值）或 `controlled`（真实 LLM，Telegram 可仍 dry-run；若真实发送则必须同时配置 bot token、测试发送 allowlist 与 webhook receive allowlist）。

**Tech Stack:** POSIX `sh`、现有 systemd `ExecStartPre`、Git Bash fixture tests、FastAPI `Settings` 既有字段。

## Global Constraints

- `APP_ENV` 必须继续为 `staging`，`PROVIDER_MODE` 必须为 `disabled`。
- `AGENT_SAVE_FULL_PROMPT=false` 且 `AGENT_SAVE_FULL_RESPONSE=false` 不得放宽。
- `TELEGRAM_SEND_MODE` 只允许 `dry_run` 或 `restricted_test`；不引入 `real`。
- `restricted_test` 必须有 `TELEGRAM_BOT_TOKEN`、非空 `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` 与内容完全相同的非空 `TELEGRAM_ALLOWED_CHAT_IDS`。
- `LLM_ENABLED=true` 只允许与 `AGENT_WORKFLOW_MODE=real_openrouter` 和非空 `OPENROUTER_API_KEY` 同时出现。
- 不打印 token、secret、URL、chat ID、完整 prompt 或 response。

---

### Task 1: 用 fixture 固化受控 profile 合同

**Files:**

- Modify: `deploy/stage09-native/scripts/test-runtime-preflight.sh`
- Test: `deploy/stage09-native/scripts/test-runtime-preflight.sh`

**Interfaces:**

- Consumes: `validate-runtime-presence.sh <runtime.env>`。
- Produces: 三个受控组合的可重复测试：真实 LLM dry-run 通过、真实 LLM + restricted send 通过、缺 OpenRouter key 或 allowlist 不一致失败。

- [ ] **Step 1: 写入 failing fixture 断言**

在现有 `write_fixture` 后新增 `write_controlled_fixture`，其完整安全值为：

```sh
printf '%s\n' \
    'TELEGRAM_BOT_TOKEN=fixture-bot-token' \
    'OPENROUTER_API_KEY=fixture-openrouter-key' \
    'LLM_ENABLED=true' \
    'AGENT_WORKFLOW_MODE=real_openrouter' \
    'TELEGRAM_SEND_MODE=restricted_test' \
    'TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS=fixture-chat' \
    'TELEGRAM_ALLOWED_CHAT_IDS=fixture-chat' >> "$fixture_path"
```

同时添加：

```sh
assert_pass 'controlled-real-llm-and-restricted-send' "$tmpdir/controlled.env"
sed -i 's/^OPENROUTER_API_KEY=.*/OPENROUTER_API_KEY=/' "$tmpdir/missing-key.env"
assert_rejected_without_value_leak 'controlled-llm-missing-key' "$tmpdir/missing-key.env"
sed -i 's/^TELEGRAM_ALLOWED_CHAT_IDS=.*/TELEGRAM_ALLOWED_CHAT_IDS=other-chat/' "$tmpdir/mismatched-allowlist.env"
assert_rejected_without_value_leak 'restricted-send-mismatched-allowlist' "$tmpdir/mismatched-allowlist.env"
```

- [ ] **Step 2: 运行 RED**

Run: `sh deploy/stage09-native/scripts/test-runtime-preflight.sh`

Expected: `controlled-real-llm-and-restricted-send: FAIL`，因为当前 validator 仅接受 dry-run、LLM-off、fake workflow 与空 allowlist。

- [ ] **Step 3: Commit**

```bash
git add deploy/stage09-native/scripts/test-runtime-preflight.sh
git commit -m "test: define controlled Stage09 runtime profiles"
```

### Task 2: 实现受控 profile validator

**Files:**

- Modify: `deploy/stage09-native/scripts/validate-runtime-presence.sh`
- Modify: `deploy/stage09-native/scripts/test-runtime-preflight.sh`
- Test: `deploy/stage09-native/scripts/test-runtime-preflight.sh`

**Interfaces:**

- `validate-runtime-presence.sh` 继续输出脱敏状态，exit 0 代表 baseline 或受控 profile 都可供 systemd `ExecStartPre` 使用。
- `verify-native-isolation.sh` 无需修改，继续只调用该 validator 并拒绝历史/容器 marker。

- [ ] **Step 1: 最小实现 profile 判定**

将现有强制 mode 判断替换为：

```sh
case "$telegram_send_mode" in
    dry_run|restricted_test) ;;
    *) fail "unsafe-TELEGRAM_SEND_MODE" ;;
esac

case "$llm_enabled:$agent_workflow_mode" in
    false:fake|true:real_openrouter) ;;
    *) fail "unsafe-LLM-workflow-combination" ;;
esac

if [ "$llm_enabled" = "true" ]; then
    require_value OPENROUTER_API_KEY
fi
```

读取 `TELEGRAM_TEST_SEND_ALLOWED_CHAT_IDS` 和 `TELEGRAM_ALLOWED_CHAT_IDS`；当 mode 为 `restricted_test` 时要求 bot token、两者非空且字节相同；当 mode 为 `dry_run` 时两者都必须为空。`TELEGRAM_ALLOWED_USER_IDS` 和 Stage06 notification allowlist 继续必须为空。

- [ ] **Step 2: 运行 GREEN**

Run:

```bash
sh deploy/stage09-native/scripts/test-runtime-preflight.sh
sh deploy/stage09-native/scripts/test-release-assets.sh
sh deploy/stage09-native/scripts/test-public-ingress-assets.sh
```

Expected: 受控 fixture 与原有 baseline fixture 均 PASS；反例仍被拒绝。

- [ ] **Step 3: 更新运行时输出**

输出只包含下列状态，不回显值：

```text
TELEGRAM_SEND_MODE: dry_run|restricted_test
LLM_ENABLED: false|true
AGENT_WORKFLOW_MODE: fake|real_openrouter
TELEGRAM_ALLOWLISTS: empty|matched-controlled
```

- [ ] **Step 4: Commit**

```bash
git add deploy/stage09-native/scripts/validate-runtime-presence.sh deploy/stage09-native/scripts/test-runtime-preflight.sh
git commit -m "feat: permit controlled Stage09 real runtime profile"
```

### Task 3: 服务器受控激活与回滚

**Files:**

- Modify: `project-docs/08-implementation/2026-07-23-stage09-telegram-llm-real-smoke.md`
- Create: `project-docs/08-implementation/evidence/stage09-controlled-runtime-smoke-2026-07-23.md`

**Interfaces:**

- Server runtime 从本机受保护 env 以 stdin 传入，且仅更新本计划列出的 keys。
- 运行时修改前创建 root-only backup；systemd preflight、health 或 Telegram/OpenRouter smoke 失败时恢复 backup。

- [ ] **Step 1: 部署包含 Task 2 的 sealed release**

执行与 r11 相同的 checksum → release-layout → asset tests → 原子 symlink switch 顺序；不触碰历史 Caddy container、80/443 或数据库/Redis 暴露。

- [ ] **Step 2: 启用真实 LLM dry-run profile**

写入 `OPENROUTER_*`、`LLM_ENABLED=true`、`AGENT_WORKFLOW_MODE=real_openrouter`，保持 `TELEGRAM_SEND_MODE=dry_run`，重启 Stage09 units 并验证 `ExecStartPre` 与 loopback health。

- [ ] **Step 3: 等待用户真实入站消息后启用 restricted send**

当 webhook 到达并取得事实 chat ID 后，把该 ID 同时写入两个 Telegram allowlist，设置 `TELEGRAM_SEND_MODE=restricted_test`，再执行 send-request → confirm → worker 的单条测试回包。

- [ ] **Step 4: 写入证据和 commit**

记录命令类别、exit/status、消息/LLM trace 与审计结果，不记录机密、chat ID、原文、完整 prompt/response。

## Plan Self-Review

- Spec coverage: 覆盖 P1 preflight 的阻塞原因、真实 LLM、Telegram restricted send、allowlist 一致性、systemd 启动与回滚。
- Placeholder scan: 无 `TODO`、`TBD` 或未定义的安全行为。
- Interface consistency: systemd 继续只依赖 `verify-native-isolation.sh` → `validate-runtime-presence.sh`，未增加第二套入口。
