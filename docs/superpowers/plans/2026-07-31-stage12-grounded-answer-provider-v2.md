# Stage12 Grounded Answer Provider V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Stage12 final user answer originate from a real grounded model call, reject ungrounded output, prevent fallback from satisfying acceptance, and validate the committed candidate through the existing native server and bounded real Telegram path.

**Architecture:** Build a private fixed-array `GroundedAnswerProviderRequestV2` from `TaskSpecV2`, the authorized schema, sealed `ClaimGraphV1`, typed Specialist findings and pending-only Action status. The real Provider returns model-authored Chinese statements with exact claim/evidence/action references. A deterministic validator enforces schema, reference closure, citation closure, canonical factual atoms, Action status, objective coverage and permission/version binding before rendering. The runtime keeps safe deterministic fallback but records it as `answer_source=deterministic_fallback`, which fails every real-model acceptance gate.

**Tech Stack:** Python 3.12+, Pydantic v2, FastAPI, LangGraph-first runtime, OpenRouter OpenAI-compatible API, Gemini 2.5 Flash baseline, PostgreSQL/pgvector, Redis, pytest, React/Vite/TypeScript, native Nginx/systemd deployment.

## Global Constraints

- Stage11/r76 remains production authority until every local, real-Provider, native-server and Telegram gate passes.
- No Docker image, Docker Compose command or container migration.
- No model/profile replacement in this plan.
- No Provider-authored database fact, join, aggregate, permission, Action target, execution ticket or confirmation.
- Provider-facing response schemas use fixed properties and arrays; no dynamic-key map.
- Fallback is allowed for runtime safety but never counts as a real-model acceptance pass.
- Do not run a full `48 × 3` campaign until the exact 12-call P1 gate and representative P2 gate pass.
- Do not persist raw Provider prompt/output, secrets, Gold payload, raw Telegram identity or unauthorized business data.
- No production-wide Stage12 activation; server tests are isolated and allowlist-bound.
- Use `apply_patch` for edits, TDD for behavior changes, explicit Git staging, and one reviewable commit per task.

---

### Task 1: Update Active Stage12 Truth Documents

**Files:**
- Modify: `project-docs/02-architecture/stage12-quality-v2/05_SPECIALISTS_PROVIDERS_AND_MODELS.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/07_SECURITY_OBSERVABILITY_AND_SLO.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/08_DELIVERY_TEST_AND_ACCEPTANCE.md`
- Modify: `project-docs/02-architecture/stage12-quality-v2/README.md`
- Modify: `project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_ACCEPTANCE.md`
- Modify: `project-docs/08-implementation/STAGE_12_INTEGRATED_SPECIALIST_OBSERVABILITY_COMPLETION_AUDIT.md`

**Interfaces:**
- Consumes: approved design `docs/superpowers/specs/2026-07-31-stage12-grounded-answer-provider-v2-design.md`.
- Produces: active Stage12 truth that explicitly supersedes ordering-only Composer acceptance.

- [x] **Step 1: Record the failed real baseline exactly**

Add the immutable facts `24/144` completed real Composer results, `120/144` fallback cases, `240` schema-invalid attempts, Provider-unavailable mean `0.833333`, and total-latency P95 mean `11636.716667 ms`.

- [x] **Step 2: Freeze the new contract and gates**

Document `GroundedAnswerProviderRequestV2`, `GroundedAnswerPlanV2`, split failure taxonomy, `answer_source`, P0/P1/P2/P3, zero-fallback Stage12 acceptance and native-only deployment.

- [x] **Step 3: Prove no contradictory active wording remains**

Run:

```powershell
rg -n "ordering-only|connector_by_handle|fallback.*PASS|Docker Compose|24/144|GroundedAnswer" project-docs/02-architecture/stage12-quality-v2 project-docs/08-implementation/STAGE_12_*.md
```

Expected: ordering-only material is marked historical/superseded; no document claims fallback proves real-model quality.

- [x] **Step 4: Commit**

```powershell
git add -- project-docs/02-architecture/stage12-quality-v2 project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_SOURCE_OF_TRUTH.md project-docs/08-implementation/STAGE_12_E_TYPED_SPECIALIST_PROVIDER_ACCEPTANCE.md project-docs/08-implementation/STAGE_12_INTEGRATED_SPECIALIST_OBSERVABILITY_COMPLETION_AUDIT.md
git commit -m "docs: freeze grounded Stage12 provider contract"
```

### Task 2: Add Fixed-Array Grounded Answer Contracts

**Files:**
- Create: `backend/app/schemas/agent_grounded_answer_v2.py`
- Modify: `backend/app/schemas/agent_specialist_results.py`
- Create: `backend/tests/unit/test_agent_grounded_answer_contracts.py`

**Interfaces:**
- Consumes: `ClaimGraphV1`, `ActionStatusV1`, `FinalAnswerRenderReceiptV1`, `specialist_payload_sha256`.
- Produces: `GroundedAnswerProviderRequestV2`, `GroundedClaimCandidateV2`, `GroundedEvidenceCandidateV2`, `GroundedActionCandidateV2`, `GroundedAnswerStatementV2`, `GroundedAnswerSectionV2`, `GroundedAnswerPlanV2`, `GroundedComposerResultV2`, `ProviderResponseFingerprintV1`, `AnswerSource`, `ProviderResultStatus`.

- [x] **Step 1: Write the fixed-schema RED tests**

```python
def test_provider_response_schema_contains_no_dynamic_object_map() -> None:
    schema = GroundedAnswerPlanV2.model_json_schema()
    encoded = json.dumps(schema, sort_keys=True)
    assert '"additionalProperties": {' not in encoded
    assert schema["additionalProperties"] is False


def test_grounded_statement_requires_reference_by_kind() -> None:
    with pytest.raises(ValidationError, match="grounded_fact_claim_required"):
        GroundedAnswerStatementV2(
            statement_kind="fact",
            text="Atlas 有 2 个任务。",
            claim_handles=(),
            evidence_handles=(),
            action_handles=(),
        )
```

- [x] **Step 2: Run RED**

Run: `cd backend; pytest -q tests/unit/test_agent_grounded_answer_contracts.py`

Expected: collection/import failure because the new module does not exist.

- [x] **Step 3: Implement minimal strict contracts**

Use `ConfigDict(extra="forbid", frozen=True, strict=True)`, bounded tuples, fixed enums and canonical `content_hash` validation. Add `provider_grounding_invalid` and `deterministic_fallback_used` to the Stage12 failure taxonomy without deleting existing V1 codes.

- [x] **Step 4: Verify provider-schema portability**

Add assertions that every object node has boolean `additionalProperties`, no `dict[str, T]` response field exists, nesting is bounded, and all output properties have descriptions.

- [x] **Step 5: Run GREEN and adjacent contracts**

```powershell
cd backend
pytest -q tests/unit/test_agent_grounded_answer_contracts.py tests/unit/test_agent_specialist_results.py tests/unit/test_agent_model_gateway.py
```

- [x] **Step 6: Commit**

```powershell
git add -- backend/app/schemas/agent_grounded_answer_v2.py backend/app/schemas/agent_specialist_results.py backend/tests/unit/test_agent_grounded_answer_contracts.py
git commit -m "feat: add grounded answer contracts"
```

### Task 3: Build Permission-Filtered Provider Requests

**Files:**
- Create: `backend/app/services/agent_grounded_answer_request.py`
- Create: `backend/tests/unit/test_agent_grounded_answer_request.py`

**Interfaces:**
- Consumes: raw authorized query, `TaskSpecV2`, `AuthorizedSchemaSnapshot`, `ClaimGraphV1`, typed Risk/Daily/Tabular artifacts and safe citation labels.
- Produces: `build_grounded_answer_request(*, query: str, task_spec: TaskSpecV2, graph: ClaimGraphV1, authorized_schema: AuthorizedSchemaSnapshot, presentation: ComposerPresentationContextV1, specialist_findings: Sequence[StructuredFactSetV1 | RiskAssessmentSetV1 | DailyBriefV1]) -> GroundedAnswerProviderRequestV2`.

- [x] **Step 1: Write request-boundary RED tests**

```python
def test_request_contains_authorized_claims_but_no_gold_or_hidden_fields() -> None:
    query, task_spec, graph, schema, presentation, findings = _authorized_fixture()
    request = build_grounded_answer_request(
        query=query,
        task_spec=task_spec,
        graph=graph,
        authorized_schema=schema,
        presentation=presentation,
        specialist_findings=findings,
    )
    payload = request.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False)
    assert request.query == "列出 Atlas 未完成任务并说明风险"
    assert "customer_secret" not in encoded
    assert "expected_answer" not in encoded
    assert "case_id" not in encoded
    assert request.content_hash == specialist_payload_sha256(
        request.model_dump(mode="json", exclude={"content_hash"})
    )
```

- [x] **Step 2: Run RED**

Run: `cd backend; pytest -q tests/unit/test_agent_grounded_answer_request.py`

Expected: import failure for the missing builder.

- [x] **Step 3: Implement deterministic projection**

Map claims to safe subject/predicate/value labels, exact evidence closure and source versions. Include only pending/denied/deferred Action summaries already present in the sealed graph. Bind `scope_hash`, `field_policy_version`, `field_policy_hash`, `schema_hash` and `content_hash`.

- [x] **Step 4: Add tamper and scope tests**

Reject missing field-policy proof, scope mismatch, hidden labels, unknown evidence, duplicate handles, stale/conflicted facts presented as valid and content-hash tampering.

- [x] **Step 5: Run GREEN**

```powershell
cd backend
pytest -q tests/unit/test_agent_grounded_answer_request.py tests/unit/test_agent_claim_graph.py tests/unit/test_agent_schema_binding.py
```

- [x] **Step 6: Commit**

```powershell
git add -- backend/app/services/agent_grounded_answer_request.py backend/tests/unit/test_agent_grounded_answer_request.py
git commit -m "feat: project grounded answer requests"
```

### Task 4: Implement Deterministic Grounding Validation and Rendering

**Files:**
- Create: `backend/app/services/agent_grounded_answer_validation.py`
- Create: `backend/tests/unit/test_agent_grounded_answer_validation.py`

**Interfaces:**
- Consumes: sealed `GroundedAnswerProviderRequestV2` and Provider `GroundedAnswerPlanV2`.
- Produces: `validate_grounded_answer_plan(request: GroundedAnswerProviderRequestV2, plan: GroundedAnswerPlanV2) -> None`, `render_grounded_answer(request: GroundedAnswerProviderRequestV2, plan: GroundedAnswerPlanV2, graph: ClaimGraphV1, presentation: ComposerPresentationContextV1) -> GroundedComposerResultV2`.

- [x] **Step 1: Write one RED test per invariant**

Cover unknown/duplicate references, citation under/over-claim, invented entity/code/number/date/currency/percentage/status atoms, executed-Action wording against pending status, missing required objective, invalid limitation, non-Chinese output, scope/policy/version drift and prohibited internal handles in visible text.

```python
def test_valid_claim_ids_cannot_cover_invented_budget_text() -> None:
    plan = _plan(text="Atlas 已批准九亿元预算。", claims=(ATLAS_COUNT_CLAIM,))
    with pytest.raises(ProviderValidationError) as captured:
        validate_grounded_answer_plan(_request(), plan)
    assert captured.value.code == "provider_grounding_invalid"
```

- [x] **Step 2: Run RED**

Run: `cd backend; pytest -q tests/unit/test_agent_grounded_answer_validation.py`

- [x] **Step 3: Implement ordered validators**

Validate schema, reference closure, exact citation union, canonical atom allowlist, Action status language, permission/version binding, objective coverage and language. Do not use only ID-subset checks or completion-verb regex.

- [x] **Step 4: Implement exact receipt rendering**

Render Provider-authored statement text in Provider section order, calculate answer/receipt hashes, preserve claim/evidence/action edges, and set `answer_source="real_provider"`, `provider_result_status="completed"`.

- [x] **Step 5: Run GREEN and historical exploit regression**

```powershell
cd backend
pytest -q tests/unit/test_agent_grounded_answer_validation.py tests/unit/test_agent_composer_v2.py -k "unsupported or bankruptcy or grounded or provider"
```

- [x] **Step 6: Commit**

```powershell
git add -- backend/app/services/agent_grounded_answer_validation.py backend/tests/unit/test_agent_grounded_answer_validation.py
git commit -m "feat: validate grounded answer output"
```

### Task 5: Add Real Provider Adapter and Sanitized Diagnostics

**Files:**
- Create: `backend/app/services/agent_grounded_answer_provider.py`
- Create: `backend/tests/unit/test_agent_grounded_answer_provider.py`
- Modify: `backend/app/services/agent_model_gateway.py`
- Modify: `backend/tests/unit/test_agent_model_gateway.py`

**Interfaces:**
- Consumes: `ModelGatewayV1`, `GroundedAnswerProviderRequestV2`, strict response schema and validator.
- Produces: `GroundedAnswerProviderAdapterV2`, exact attempt observations, sanitized `ProviderResponseFingerprintV1` records.

- [x] **Step 1: Write RED tests for request shape and diagnostics**

Assert `response_format.type=json_schema`, `strict=true`, `provider.require_parameters=true`, model-authored answer instructions, no dynamic response map, and no Gold/hidden fields.

```python
def test_schema_failure_records_shape_without_raw_output() -> None:
    adapter = _adapter_with_response('{"wrong":true}')
    with pytest.raises(GroundedAnswerProviderInvocationError):
        adapter(_request())
    fingerprint = adapter.diagnostics[0]
    assert fingerprint.top_level_type == "object"
    assert fingerprint.top_level_keys == ("wrong",)
    assert fingerprint.response_sha256
    assert "wrong" not in fingerprint.model_dump_json()
```

- [x] **Step 2: Run RED**

Run: `cd backend; pytest -q tests/unit/test_agent_grounded_answer_provider.py`

- [x] **Step 3: Implement adapter and in-memory repair**

Allow at most two attempts under the existing UTC deadline. Raw synthetic output may exist only inside the validation/repair call stack; persisted diagnostics contain paths/types/keys/counts/length/hash/tokens only.

- [x] **Step 4: Split failure taxonomy**

Preserve transport codes. Map Pydantic failure to `provider_schema_invalid`, grounding/reference/atom failure to `provider_grounding_invalid`, and Chinese policy failure to `provider_language_invalid`.

- [x] **Step 5: Run GREEN and gateway regression**

```powershell
cd backend
pytest -q tests/unit/test_agent_grounded_answer_provider.py tests/unit/test_agent_model_gateway.py tests/unit/test_agent_provider_validation.py
```

- [x] **Step 6: Commit**

```powershell
git add -- backend/app/services/agent_grounded_answer_provider.py backend/app/services/agent_model_gateway.py backend/tests/unit/test_agent_grounded_answer_provider.py backend/tests/unit/test_agent_model_gateway.py
git commit -m "feat: call grounded answer provider"
```

### Task 6: Integrate Provider-Origin Answers and Fail-Visible Fallback

**Files:**
- Modify: `backend/scripts/stage12_isolated_af_runner.py`
- Modify: `backend/scripts/stage12_quality_evaluation.py`
- Modify: `backend/tests/unit/test_stage12_isolated_af_runner.py`
- Modify: `backend/tests/unit/test_stage12_quality_evaluation_contracts.py`
- Modify: `backend/tests/unit/test_stage12_quality_answer_action_safety_scores.py`

**Interfaces:**
- Consumes: request builder, V2 adapter, validator/renderer and existing deterministic Composer.
- Produces: runtime trace with `answer_source`, `provider_result_status`, provider/validation latency and exact fallback code.

- [ ] **Step 1: Write RED trace tests**

```python
def test_real_provider_answer_is_the_scored_runtime_answer() -> None:
    trace = _run_with_grounded_provider("模型生成的受约束中文回答")
    assert trace.answer.answer_source == "real_provider"
    assert trace.answer.rendered_answer == "模型生成的受约束中文回答"


def test_fallback_is_safe_but_fails_real_model_gate() -> None:
    trace = _run_with_schema_failure()
    assert trace.answer.rendered_answer
    assert trace.answer.answer_source == "deterministic_fallback"
    assert trace.answer.provider_result_status == "schema_failed"
    assert score_final_answer(trace).real_provider_gate_pass is False
```

- [ ] **Step 2: Run RED**

Run: `cd backend; pytest -q tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_quality_evaluation_contracts.py`

- [ ] **Step 3: Replace ordering-only call in the isolated runner**

Build the grounded request after ClaimGraph creation, invoke V2 Provider, validate/render the actual model text, and use deterministic Composer only inside an explicit fallback branch.

- [ ] **Step 4: Update scoring**

Score the actual returned answer, retain final-answer quality metrics, and add a non-compensable real-Provider-origin gate. Do not give fallback a passing Provider score.

- [ ] **Step 5: Run GREEN and all 48 deterministic traces**

```powershell
cd backend
pytest -q tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_quality_evaluation_contracts.py tests/unit/test_stage12_quality_answer_action_safety_scores.py
```

- [ ] **Step 6: Commit**

```powershell
git add -- backend/scripts/stage12_isolated_af_runner.py backend/scripts/stage12_quality_evaluation.py backend/tests/unit/test_stage12_isolated_af_runner.py backend/tests/unit/test_stage12_quality_evaluation_contracts.py backend/tests/unit/test_stage12_quality_answer_action_safety_scores.py
git commit -m "feat: score real grounded answers"
```

### Task 7: Implement and Run the 12-Call P1 Gate

**Files:**
- Create: `backend/scripts/stage12_grounded_answer_preflight.py`
- Create: `backend/tests/unit/test_stage12_grounded_answer_preflight.py`
- Create after real execution: `project-docs/08-implementation/evidence/stage12-grounded-answer-p1-2026-07-31.json`
- Create after real execution: `project-docs/08-implementation/evidence/stage12-grounded-answer-p1-2026-07-31.md`

**Interfaces:**
- Consumes: local protected OpenRouter env, frozen baseline profile, four synthetic authorized shapes.
- Produces: exactly 12 real calls and a sanitized immutable P1 report.

- [ ] **Step 1: Write RED campaign-shape tests**

Assert shapes `(1, 2, 4, 7) × 3`, exact call count 12, abort-before-call on missing capability/config, zero fallback requirement, atomic output directory creation and no raw prompt/output fields.

- [ ] **Step 2: Run RED**

Run: `cd backend; pytest -q tests/unit/test_stage12_grounded_answer_preflight.py`

- [ ] **Step 3: Implement P0/P1 runner**

Query the OpenRouter model metadata endpoint for `structured_outputs` and `response_format`, then execute the 12 calls through the production adapter. Retain only diagnostics, hashes, latency/tokens and pass/fail.

- [ ] **Step 4: Run unit GREEN**

```powershell
cd backend
pytest -q tests/unit/test_stage12_grounded_answer_preflight.py tests/unit/test_agent_grounded_answer_provider.py tests/unit/test_agent_grounded_answer_validation.py
```

- [ ] **Step 5: Execute one real P1 command**

Run with the ignored local env and a previously absent output directory. Do not retry selected failures or add a fourth shape round.

Expected hard gate:

```text
http_completed=12/12
schema_valid=12/12
grounding_valid=12/12
answer_source_real_provider=12/12
fallback_count=0
raw_output_retained=0
```

If any count fails, stop before P2 and fix from the sanitized error path/shape evidence.

- [ ] **Step 6: Validate and commit P1 evidence**

```powershell
git add -- backend/scripts/stage12_grounded_answer_preflight.py backend/tests/unit/test_stage12_grounded_answer_preflight.py project-docs/08-implementation/evidence/stage12-grounded-answer-p1-2026-07-31.json project-docs/08-implementation/evidence/stage12-grounded-answer-p1-2026-07-31.md
git commit -m "test: prove grounded provider compatibility"
```

### Task 8: Run Representative P2 Before Full Campaign

**Files:**
- Modify: `backend/scripts/stage12_final_provider_campaign.py`
- Modify: `backend/tests/unit/test_stage12_final_provider_campaign.py`
- Create after real execution: `project-docs/08-implementation/evidence/stage12-grounded-answer-p2-2026-07-31/`

**Interfaces:**
- Consumes: frozen Case fixture and P1-passing adapter.
- Produces: three real rounds for the exact representative set and a zero-fallback P2 decision.

- [ ] **Step 1: Freeze the representative case set**

Use exactly:

```text
join_01, join_07, risk_02, daily_03,
draft_02, task_01, reminder_01,
permission_01, permission_04, fault_01,
mixed_02, mixed_08
```

- [ ] **Step 2: Write RED gates**

Assert `12 cases × 3 rounds = 36`, no selective retry, every result `answer_source=real_provider`, zero fallback, actual model answer scoring, zero unauthorized effects/writes/sends and atomic evidence.

- [ ] **Step 3: Run RED, implement minimal P2 mode, then GREEN**

```powershell
cd backend
pytest -q tests/unit/test_stage12_final_provider_campaign.py
```

- [ ] **Step 4: Execute exactly one real P2 campaign**

If any Case falls back or violates final-answer/safety gates, stop before P3 and diagnose that exact case class.

- [ ] **Step 5: Commit P2 evidence**

```powershell
git add -- backend/scripts/stage12_final_provider_campaign.py backend/tests/unit/test_stage12_final_provider_campaign.py project-docs/08-implementation/evidence/stage12-grounded-answer-p2-2026-07-31
git commit -m "test: verify grounded answer preflight"
```

### Task 9: Full Regression and Native Release Candidate Gate

**Files:**
- Modify: `backend/scripts/stage12_real_quality_report.py`
- Modify: `backend/tests/unit/test_stage12_real_quality_report.py`
- Modify: active Stage12 acceptance/audit/handoff documents.

**Interfaces:**
- Consumes: P2-passing revision, disposable PostgreSQL/pgvector and real Redis fixtures.
- Produces: full local regression evidence and a committed native release candidate; it does not claim final P3 acceptance.

- [ ] **Step 1: Add future P3 report gates in RED/GREEN**

Require any later P3 bundle to contain `144/144 answer_source=real_provider`, `fallback_count=0`, separate transport/schema/grounding/language rates, unchanged final-answer/safety metrics and total P95 `<= 8000 ms`.

- [ ] **Step 2: Run focused and full backend verification**

Run Stage12 focused tests, full backend pytest with at least a 10-minute budget, disposable PostgreSQL/pgvector, real Redis recovery/ack-once, Alembic current/head, compileall, Black and `git diff --check`. Classify every skip.

- [ ] **Step 3: Run Mini App and production build**

Run the full Mini App suite, TypeScript/build and relevant Action/SSE UI tests. Do not infer visual acceptance from unit tests.

- [ ] **Step 4: Run native release asset preflight locally**

Verify sealed-source layout, shell LF/CRLF, runtime-presence assets, migration head, static parity inputs and rollback assets without connecting to the server.

- [ ] **Step 5: Update candidate evidence and commit**

Record changed files, verification, skipped tests, remaining risks and temporary cleanup. Explicitly state that P3/server/Telegram remain pending. Commit only if P1/P2 bundles validate and secret/raw-output scans pass.

### Task 10: Publish the Audited Branch

**Files:**
- Modify as evidence requires: `AGENTS.md`, `HANDOFF.md`, `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`, `project-docs/08-implementation/README.md`.

**Interfaces:**
- Consumes: P1/P2-passing, full-regression-passing native release candidate and clean worktree; server P3 remains pending.
- Produces: pushed `codex/stage09-ai-conversation-sse` branch.

- [ ] **Step 1: Audit Git scope**

Verify clean status, commit list since `09b9d5f`, no secret/raw Provider/Telegram identity, no temp files, no untracked files and no oversized accidental artifact.

- [ ] **Step 2: Verify GitHub prerequisites**

Run `gh --version`, `gh auth status`, remote identity and branch tracking checks without printing credential values.

- [ ] **Step 3: Push**

```powershell
git push -u origin codex/stage09-ai-conversation-sse
```

Do not merge to the production/default branch in this task.

- [ ] **Step 4: Record pushed commit and remote parity**

Verify local HEAD equals the remote branch SHA and update the deployment evidence source revision.

### Task 11: Native Server Deployment and Real Backend Validation

**Files:**
- Reuse: `deploy/stage09-native/**`
- Create: `project-docs/08-implementation/evidence/stage12-native-server-validation-2026-07-31.md`

**Interfaces:**
- Consumes: pushed immutable commit and existing native Stage09 release scripts.
- Produces: default-off native server candidate, isolated Stage12 allowlist and real backend P2-equivalent evidence.

- [ ] **Step 1: Build sealed artifacts from the pushed commit**

Include committed `backend`, `mini-app` and `deploy/stage09-native` assets only. Verify archive/static hashes and LF/CRLF gates locally and on the server.

- [ ] **Step 2: Run server preflight**

Verify native release layout, Python environment, PostgreSQL 18/pgvector, Redis, migration plan, systemd unit assets, Nginx config, disk space, rollback release and runtime presence. Do not invoke Docker/Compose.

- [ ] **Step 3: Install and activate default-off candidate**

Run additive migration only after backup/current-head checks. Keep Stage12 globally off and enable it only for the isolated evaluation workspace.

- [ ] **Step 4: Run real deployed backend tests**

Exercise public/loopback health, FastAPI identity, LangGraph, PostgreSQL/pgvector, Redis Specialist workers, real OpenRouter and SSE. Re-run the frozen representative P2 set through the deployed backend. Every accepted answer must be `real_provider`; fallback fails server validation.

- [ ] **Step 5: Verify rollback**

Prove Stage12 flags can be disabled and Stage11/r76 answer authority restored without data deletion. If activation or health fails, roll back immediately.

### Task 12: Server P3, Bounded Real Telegram Test and Final Audit

**Files:**
- Create after real execution: `project-docs/08-implementation/evidence/stage12-grounded-answer-p3-2026-07-31/`
- Create: `project-docs/08-implementation/evidence/stage12-real-telegram-validation-2026-07-31.md`
- Modify: final Stage12 acceptance/handoff documents.

**Interfaces:**
- Consumes: server-backend-P2-passing candidate, frozen 48-case Human Gold, existing verified webhook and one factual allowlisted test chat.
- Produces: exactly one server `48 × 3` P3 campaign, real inbound Telegram → Stage12 real Provider → safe answer evidence, optional same-chat restricted reply receipt, and cleanup audit.

- [ ] **Step 1: Execute exactly one P3 campaign on the deployed native candidate**

Run frozen 48 Human-Gold cases for exactly three independent real rounds through the server-side FastAPI/LangGraph/PostgreSQL/pgvector/Redis/OpenRouter path. Require `144/144 answer_source=real_provider`, zero fallback, all final-answer/safety gates and total P95 `<= 8000 ms`. No selective retry, extra round or merged output.

- [ ] **Step 2: Verify bounded Telegram state**

Use the existing bot/webhook, one factual test chat and exact allowlists. Record only booleans/hashes/status counts; never retain raw chat/user/message IDs or original message text.

- [ ] **Step 3: Receive one unique nonce and execute one read-only query**

Verify webhook ingestion, authorized workspace resolution, Stage12 trace, `answer_source=real_provider`, citations, audit and terminal SSE.

- [ ] **Step 4: Test optional outbound reply only within existing authorization**

If the approved Telegram test includes outbound delivery, use the same allowlisted chat and controlled send path. Do not confirm an Action or mutate business records.

- [ ] **Step 5: Cleanup and final requirement-by-requirement audit**

Remove temporary session/release/upload/test artifacts, restore the documented safe runtime profile, verify zero unauthorized writes/sends, and audit every design Acceptance Criterion against direct evidence.

- [ ] **Step 6: Keep production activation separate**

Report the candidate result. Do not enable Stage12 for all production workspaces until the user reviews the evidence and explicitly approves final activation.
