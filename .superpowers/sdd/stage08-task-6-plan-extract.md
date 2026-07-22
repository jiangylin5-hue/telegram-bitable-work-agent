### Task 6：隔离真实 Provider 评测器

**Files：** 修改 `backend/scripts/stage06_live_llm_skill_quality_eval.py`、`backend/tests/unit/test_stage06_live_llm_skill_quality_eval.py`、`project-docs/08-implementation/evidence/stage06-live-llm-skill-quality-2026-07-16.md`。

**Produces：** `run_case_isolated(case, timeout_seconds) -> RedactedCaseResult` 和 `run_batch(cases, max_parallelism, timeout_seconds) -> RedactedBatchResult`。

- [ ] **步骤 1：写失败隔离测试**

```python
def test_timed_out_case_has_static_label_without_raw_content(monkeypatch):
    result = run_case_isolated(case, timeout_seconds=1)
    assert result.failure_labels == ("case_timeout",)
    assert "prompt" not in result.model_dump_json()

def test_batch_continues_after_one_timeout(monkeypatch):
    assert run_batch((slow_case, passing_case), max_parallelism=2,
                     timeout_seconds=1).case_count == 2
```

- [ ] **步骤 2：确认失败；步骤 3：实现进程级隔离**

运行：`python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py -k "timeout or batch"`  
预期：导入或断言失败。  
每个 case 使用子进程硬超时；子进程内部可处理原始 provider 输出，但对外只传固定 allowlist 的布尔、计数、状态和静态错误标签。默认并发最多 2；保留 Telegram dry-run/provider-write disabled；`finally` 清理临时结果。

- [ ] **步骤 4：测试与证据更新**

运行：`python -m pytest -q tests/unit/test_stage06_live_llm_skill_quality_eval.py`  
预期：PASS。  
证据只记录旧串行批次是否被中断/超时、新超时合同及“未保留原始输出”。本任务不得触发新的 Provider 调用，除非另获明确执行授权。

## 计划自检

- 覆盖范围：Package A 实现 Tool Gateway、预算、execution ticket、policy、audit、幂等和 Provider 评测隔离；Memory、群持久化、检索和协调器属于路线图 B-F，不在本包抢先实现。
- 完整性：每个任务都有精确文件、接口、红灯测试、命令和预期结果。
- 类型一致性：`ExecutionBudget`、`ExecutionPlan`、`ToolInvocation`、`RedactedToolResult`、`Stage08ExecutionTicket` 与 gateway 在使用前已定义。
- 范围检查：本包不创建 Memory/vector chunk/Milvus、直接 Telegram 发送或自治 Agent loop。
