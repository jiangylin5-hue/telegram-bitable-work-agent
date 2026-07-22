# Stage07 TD009 客户端失败关闭与替换证据（2026-07-16）

## Scope

本记录只补 TD009「Home 个人助理上下文发现」既有实现的自动化客户端证据；没有新增 schema、API、权限、LLM、记忆、RAG、Telegram 或部署行为。

## 执行命令与结果

```text
cd mini-app
npm.cmd test -- --run src/test/assistant-context-app-flow.test.tsx

Test Files  1 passed (1)
Tests       4 passed (4)
```

随后执行 Mini App 全量回归与生产构建：

```text
npm.cmd test -- --run
Test Files  63 passed (63)
Tests       230 passed (230)

npm.cmd run build
✓ built
```

## 新增的可复现断言

| 验收点 | 覆盖的实际状态 | 可观察断言 | 边界 |
| --- | --- | --- | --- |
| `ACD-A06` | 拉取个人助理 context 时网络异常 | 显示固定中文错误和「重试」；不显示底层错误文本或拓扑信息 | 客户端错误状态，不替代浏览器视觉验收 |
| `ACD-A07` | 已选 view 在读取时返回 `404` | 清空失效 view，显示固定错误；不渲染服务端 `detail` | 客户端 fail-closed，服务端权限交集仍由既有 API/PostgreSQL 证据承担 |
| `ACD-A08` | 先点旧员工、再点新员工，旧请求后返回 | 旧 context 不能覆盖新员工的 view 列表 | 仅证明单客户端的异步替换，不替代跨设备/浏览器人工观察 |

原有同文件的流程断言继续验证：选中 view 后必须服务端 reread，Home 只调用既有 `summarize`，并且只有用户明确点击时才打开 Base。

## 结论与非结论

- 三个行可从「缺少专用自动化测试」提升为 `evidenced-pending`，仍需按原 BDD 进行独立逐项验收。
- `ACD-A10` 仍为 `blocked`：没有保留的、使用 Codex 内置浏览器完成的 built Mini App 全流程视觉/焦点观察。
- 本证据不把单元/Testing Library 结果伪装成真实 Provider、真实 Telegram 或生产环境验收。
