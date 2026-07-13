# Stage07 S5.3 Team Bot Knowledge Entry Design

## Status

- Design status: proposed after user confirmation of the A+B product direction on 2026-07-14; requires written-spec review before an implementation plan or code.
- Scope: a shared Team Bot Home surface using existing active digital employees and one authorized saved view as a bounded knowledge window.

## User Outcome

A workspace member can open `团队 Bot`, select a team-available employee, select a saved view that the employee and member may both read, ask one bounded question, receive a safe summary with opaque citations and open the corresponding Base for further work. The flow does not retain chat history or write a record.

## Interaction Design

```text
Home
-> 团队 Bot
-> 联系人列表
-> 知识视图列表
-> 一次性问题 + 生成摘要
-> 摘要 / 无可用数据 / 固定重试状态
-> 打开 Base 继续处理
```

Desktop uses a right workbench consistent with the existing assistant/draft grammar. Mobile uses the existing full-screen sheet grammar. The surface visibly says `团队共享知识，不保存个人记忆` and never shows a conversation transcript.

## Safe Interaction States

| State | Display | Action availability |
| --- | --- | --- |
| contacts loading / empty / denied | fixed loading/empty/denied copy | no inferred selection |
| contact selected, catalog loading | selected safe name only | no summarize until view revalidated |
| catalog empty or selection revoked | fixed no-permitted-view/reselect copy | summary disabled |
| ready | safe view name and bounded instruction | one summary submit |
| running | fixed progress | submit/close behavior follows existing pending-control grammar; no duplicate request |
| empty context | fixed no-permitted-record result | explicit reselect/open Base |
| success | safe answer, opaque citations, truncation notice when applicable | explicit Base handoff only |
| error/conflict | fixed retry/reselect copy | no raw error or stale answer |

## Separation From Personal Assistant

Personal Assistant remains opt-in and personal-context-oriented under TD009. Team Bot has a separate Home entry, distinct server context/summary contract and separate protected-query key subtree. Both may invoke the same employee only after their own server authorization. Neither receives memory or a transcript, and neither can make a direct write.

## Data Flow And Privacy

The server, not the browser, resolves the employee/Base/view intersection and produces the first 100 field-filtered saved-view rows. The runtime receives this bounded internal context. The UI receives only answer text, opaque citations, truncation state and audit reference. Hidden field values, record labels, policies, runtime traces, provider details and raw errors never enter the workbench.

## Acceptance Direction

The package is locally acceptable only when every TBK-A01--TBK-A11 scenario has automated evidence, the no-index decision has a sanitized local measurement, the Team/Personal state separation is proven and the UI has user-controlled desktop/mobile review. Real OpenRouter and Telegram evidence remain separate Stage07 gates.

## Explicit Boundaries

No new persistence, vector retrieval, file indexing, memory, record picker, direct draft/update, Telegram operation or external action belongs to this design. Those capabilities remain separate future contracts.
