# Stage08 Package E / E2 消费期重验与压缩 shape 修复报告

## 触发

第二次 E2 独立复审为 `0 Critical / 2 Important / 0 Minor`。发现：C3 已重验群绑定后，D4 仍可能消费先前由该绑定派生的 scope；以及 compressor 返回 malformed object 时会绕过 safe degradation。

## 修复

1. 新增 invocation-private `_GroupScopeProof`，初次从唯一 active member → chat_user binding → active group mapping 推导时记录 binding id、mapping id/version、customer/project pair。D4 读取前重新推导并严格比对 proof；任何 binding/mapping/status/version/pair 漂移都会跳过 D4，仅写固定 `retrieval_unavailable` outcome。
2. compressor 的 provider input 创建、调用、精确 `CompressionOutcome` type/reconstruction、digest 与 C3 current-state 校验现在在同一个 `try` 内。异常、shape drift、伪造/无效 outcome 或 digest 漂移均映射为 `compression_unavailable`，不抛出、不保存 digest。
3. 对 `general_advice` intent 明确跳过 D4，避免通用建议意外变成无范围检索；最终仅添加受控 general-advice branch。

## 新增负例

- pending compressor 修改 mapping version 后，recording D4 provider 的 `search` 计数必须为 0。
- compressor 返回 `object()`、属性读取异常对象或 forged invalid digest 时，C3 的合法非群材料仍返回、群状态固定为 `compression_unavailable`。
- general advice 的 recording D4 provider 永不被调用。

## 新鲜证据

```text
137 passed in 3.21s
E2 focused unit matrix

17 passed in 9.69s
dedicated disposable pgvector integration matrix
```

三个 E2 生产模块已 `compileall` 成功。集成测试在 loopback disposable pgvector 中使用事务 rollback；未打印 DSN、未进行网络、真实 Provider、Telegram 或外部写入。

## 状态

等待新的 fresh independent review。E2、Package E 与后续 E3/E4 未在此关闭。
