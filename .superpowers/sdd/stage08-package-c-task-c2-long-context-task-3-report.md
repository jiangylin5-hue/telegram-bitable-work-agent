# Stage08 Package C2 Long Context — Task 3 Report

## Status

- Task status: `DONE_WITH_CONCERNS`
- Scope: 仅完成 verified Telegram ingress 的 new/edited 受控 projection、best-effort edit lifecycle、同事务 PostgreSQL 补证和聚焦回归。
- 未开始 Task 4 authority/window/purge service；未增加 public API、route、model、migration、network、Provider、Memory、RAG、Redis 或 LangGraph 行为。

## Changed files

1. `backend/app/schemas/telegram_webhook.py`
   - `TelegramWebhookUpdate` 只接受 `message` / `edited_message` 二选一。
   - 接收 Telegram 现有 `edit_date` 字段，不扩展 webhook request contract。
2. `backend/app/services/telegram_update_parser.py`
   - 内部区分 `new` / `edited`，携带 `chat_type` 和可选 UTC `edited_at`。
   - 既有 safe view 字段未增加 C2 fragment、mapping/source handle。
3. `backend/app/schemas/telegram.py`
   - 为既有内部 `MockTelegramUpdate` 增加 exclude-from-serialization 的 `update_kind`、`chat_type`、`edited_at` carrier；旧调用默认行为保持兼容。
4. `backend/app/services/telegram_ingestion.py`
   - 使用仅含 `Message.id` / `trace_id` 的 receipt/source-identity 查询代替 C2 路径的历史 Message body 读取。
   - 在读取本次 payload body 前，要求 group/supergroup、有效 sender、唯一 active `chat_user` binding、唯一 active same-workspace mapping，以及 active customer/project record relation。
   - new 写 version 1；known edit 写下一 version 并 supersede 当前 active version；500 Unicode code-point 上限；UTC event ordering；30-day retention。
   - exact edit replay（相同受控正文与 edit timestamp）不创建额外版本。
   - SQLAlchemy `Message` source 先在同事务 flush，再写 projection；没有中途 commit。
   - projection 也在同事务内 flush；SQLAlchemy constraint error 被转换为无 cause、无参数正文的稳定内部错误。
5. `backend/app/api/routes/telegram_webhook.py`
   - 仅把 parser 已解析的三个内部 metadata 传给既有 ingestion call。
   - public endpoint、response keys/status、secret policy、chat/user allowlist policy 均未变化。
6. `backend/tests/unit/test_stage08_group_context_ingestion.py`
   - 新增 parser XOR、new/edit、500 字、UTC/30-day、全部 fail-closed gate、重复 update/edit、legacy refusal、carrier privacy 和无 network/route tests。
7. `backend/tests/integration/test_stage08_group_context_postgres.py`
   - 在 Task 2 既有 real-PostgreSQL suite 中增加同 session 可见、同 rollback 消失的 ingress transaction assertion。
8. `.superpowers/sdd/stage08-package-c-task-c2-long-context-task-3-report.md`
   - 本报告。

## TDD evidence

### Initial RED

Command:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py
Pop-Location
```

Result: exit `1`, `17 failed, 1 passed in 1.13s`.

首个失败是 `edited_message` 不能通过既有 schema；其余失败明确来自 C2 ingress UoW/projection 行为尚不存在。不是环境跳过或拼写错误。

### Focused unit GREEN

同一命令在最小实现后结果：exit `0`, `18 passed in 1.17s`。随后加入 ambiguous mapping 与 edit replay 断言，当前文件共有 19 个 tests。

### PostgreSQL transaction RED / GREEN

新增真实事务 test 后首次运行：

```powershell
Push-Location backend
python -m pytest -q tests/integration/test_stage08_group_context_postgres.py
Pop-Location
```

Result: exit `1`, `1 failed, 5 passed`。失败为真实 PostgreSQL FK violation：缺少 ORM relationship 时 projection INSERT 排在 pending Message INSERT 之前。

最小修复是在 SQL ingestion UoW `add_message` 中只 `flush([row])`、不 commit。复跑结果：exit `0`, `6 passed in 9.67s`；新增 test 证明 Message 和 projection 同 session 可见，rollback 后两者都不存在。

### Edit replay RED / GREEN

Command:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py -k edit_creates
Pop-Location
```

首次结果：exit `1`，exact edit replay 错误地产生第三个 projection。加入受控正文 + edit timestamp 幂等 gate 后纳入最终 scoped GREEN。

### Projection error privacy RED / GREEN

在同一个 PostgreSQL transaction test 中加入 duplicate `(source_message_id, content_version)` constraint failure。首次定向运行 exit `1`：`add_group_message_projection` 没有立即 raise，意味着错误会延迟到 commit，原始 SQLAlchemy exception 可能携带 `content_fragment` parameter。

最小修复为 projection 同事务 `flush([projection])`，捕获 `SQLAlchemyError` 后 `raise TelegramIngestionPersistenceError("group_context_projection_write_failed") from None`。定向复跑：exit `0`, `1 passed, 5 deselected in 3.78s`；test 同时断言 stable message、`__cause__ is None` 且 secret fragment 不在错误字符串。

## Final verification

Command:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage03_telegram_update_parser.py tests/unit/test_telegram_ingestion.py tests/integration/test_stage08_group_context_postgres.py tests/integration/test_stage03_telegram_webhook.py
Pop-Location
```

Result: exit `0`, `37 passed in 10.84s`。

- 其中 Stage08 PostgreSQL 文件为 `6 passed`，fixture 使用 approved `STAGE06_LOCAL_DATABASE_URL` 的 disposable real PostgreSQL schema；本任务未操作默认历史 revision 异常数据库。
- 现有 webhook integration 为 `5 passed`，证明 endpoint/response/secret/allowlist 行为未回归。
- `python -m compileall -q` 对五个 production files 与新 unit test exit `0`。
- 全文件 static scan 只命中 route 文件原有 `APIRouter` import/constructor；`git diff -U0` 的新增行扫描对 `getUpdates|sendMessage|httpx|requests|OpenRouter|APIRouter|add_api_route` 无 match（exit `1`）。
- receipt/source lookup 的 SQL 明确为 `select(Message.id, Message.trace_id)`；C2 writer 不调用 `_to_ingested_message`，known edit 不创建第二个 Message。
- `git diff --check` exit `0`；仅有 shared worktree 既有 LF/CRLF conversion warnings，无 whitespace error。

## Privacy and transaction boundary

- C2 fragment 只进入 `Stage08GroupMessageProjection.content_fragment`；不进入 webhook response、safe parser view、audit、outbox、trace 或 error carrier；数据库 constraint failure 被转换为不带 cause/body 的稳定内部错误。
- 历史 `Message.raw_text`、`raw_caption`、`normalized_text` 不作为 projection source；legacy source identity 的 new re-delivery被判 duplicate，不会回填。
- 既有 Stage03 Message 仍按历史路径存 raw/normalized body，本任务没有迁移、删除或扩展这类历史行为。
- 新 Message source 的 flush 与 projection、outbox、audit 最终 commit 仍使用一个 SQLAlchemy session/transaction；flush 不是外部写入确认点，rollback test 已证明原子撤销。

## Explicit exclusions

- 无 Telegram outgoing call、real Telegram write、Provider/LLM、public API route、Memory/RAG/vector、Redis、LangGraph、deployment 或 secret 变更。
- 无 model/migration/Stage06 platform UoW 修改。
- 无 Task 4 opaque authority、120/60,000 selector、24,000 compression signal、authorized purge 或 retention batch purge。
- 未 stage、commit、reset、checkout 或 clean；保留 shared dirty worktree。

## Remaining risks / next-task boundary

1. 普通 Telegram group delete/revoke 仍无可靠 Bot API event；本任务仅实现 known edit，server-authorized purge/expiry 属 Task 4。
2. edit update 不建立第二个 raw Message，也没有 schema 字段持久化 edit update ID；当前通过相同受控正文 + 相同 `edit_date` 阻止 exact replay。内容相同但 edit timestamp 不同会被视为新的已知 edit version。
3. Task 3 只在 ingress 时验证 current binding/mapping/record relation；消费窗口前的 actor/member/employee/scope drift re-read 属 Task 4 opaque authority service。
4. 默认 `DATABASE_URL` 的历史 orphan revision 风险沿用 Task 2；本任务未修改、stamp 或掩盖该数据库状态。
5. 未运行 full backend suite；本报告只声明上述 37 个 scoped tests、compile/static/privacy checks。

## Temporary cleanup

- 未创建临时脚本、secret dump、Telegram 消息、外部资源或 deployment artifact。
- PostgreSQL fixture 使用 disposable schema；测试数据随 fixture reset/transaction rollback 清理。

## Independent review fixes

### Critical: raw Message flush error redaction

Review 指出 Task 3 为保证 Message/projection FK 顺序新增的 `SqlAlchemyTelegramIngestionUnitOfWork.add_message(...).flush([row])` 尚未清洗 SQLAlchemy exception。真实约束错误可把 `raw_text` / `normalized_text` 带入 traceback parameters。

先增加真实 PostgreSQL test `test_message_constraint_failure_raises_stable_error_without_raw_body`，用第二条相同 `telegram_update_id`、含 `must-not-leak-secret-raw-message` 的 Message 触发 unique constraint。

RED command/result:

```powershell
Push-Location backend
python -m pytest -q tests/integration/test_stage08_group_context_postgres.py -k message_constraint_failure
Pop-Location
```

Result: exit `1`, `1 failed, 6 deselected in 3.72s`；原始 `IntegrityError` 明确包含 secret `raw_text` / `normalized_text` parameters。

Minimal GREEN：仅在现有 SQLAlchemy ingestion UoW 的 Message flush 周围捕获 `SQLAlchemyError`，并以 `raise TelegramIngestionPersistenceError("telegram_message_write_failed") from None` 转换。定向复跑：exit `0`, `1 passed, 6 deselected in 3.38s`。Test 明确断言 exact `str(exc)`、`.args`、`__cause__ is None`、`__suppress_context__ is True`，且 secret 不存在于可见异常字符串/参数中。默认 FastAPI 500 response 不获得原 SQLAlchemy cause/body。

### Important: edited preview before authorization gate

Review 指出 parser 会为 `edited_message` 预先执行 `_text_preview`，这早于 C2 binding/mapping gate。保留普通 `message` 的历史 preview 行为，只将 edited update 的 `text_preview` 固定为 `None`；incoming `text` / `caption` 仍作为 exclude-from-response 的内部 carrier，进入 ingestion 后先完成 C2 binding/mapping gate，再由 writer normalization。

RED command/result:

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py -k parser_distinguishes
Pop-Location
```

Result: exit `1`, `1 failed, 18 deselected in 0.74s`，实际值为 `edited.text_preview == "hello"`。

Minimal GREEN 定向复跑：exit `0`, `1 passed, 18 deselected in 0.62s`；同时断言 edited safe view 中不存在 `hello`。

### Review-fix final regression

```powershell
Push-Location backend
python -m pytest -q tests/unit/test_stage08_group_context_ingestion.py tests/unit/test_stage03_telegram_update_parser.py tests/unit/test_telegram_ingestion.py tests/integration/test_stage08_group_context_postgres.py tests/integration/test_stage03_telegram_webhook.py
Pop-Location
```

Result: exit `0`, `38 passed in 12.21s`。

本轮 review fix 未修改 public endpoint/response/route policy、model/migration、Memory、Provider/network，也未进入 Task 4。
