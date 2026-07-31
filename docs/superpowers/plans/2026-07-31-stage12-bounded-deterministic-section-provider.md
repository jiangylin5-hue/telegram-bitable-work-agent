# Stage12 Bounded Deterministic-Section Provider Implementation Plan

- Status: `local-acceptance-passed-real-campaign-pending`
- Scope: Stage12 internal Composer Provider contract correction and independent acceptance campaign only
- Approval: user confirmed the written design and inline continuation on 2026-07-31

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unreliable full Composer-plan Provider response with a bounded section-handle ordering contract while preserving deterministic facts, citations, actions, permissions, fallback, and all existing Stage12 hard gates.

**Architecture:** The deterministic Composer first builds the complete `ComposerAnswerPlanV2`, seals its one-per-kind sections into `DeterministicSectionSetV1`, and projects only sanitized section candidates to the real Provider. The Provider returns an exact permutation of handles plus allowlisted connector codes; server code expands handles back to immutable sections, otherwise records the Provider failure and renders the untouched deterministic plan.

**Tech Stack:** Python 3.12, Pydantic 2 strict/frozen models, FastAPI project services, existing OpenRouter-compatible `ModelGatewayV1`, pytest, PostgreSQL/pgvector acceptance fixtures.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-31-stage12-bounded-deterministic-section-provider-design.md` exactly.
- Keep `google/gemini-2.5-flash`, profile `composer.zh.baseline.v1`, temperature, retry, timeout, and availability gates unchanged.
- Do not change public APIs, SQLAlchemy models, Alembic revisions, permissions, field policy, Action authority, Mini App, Stage11 dispatch, or production flags.
- Provider input must exclude raw query text, Objective IDs, Claim IDs, Action IDs, evidence IDs, record/field identities, values, Gold, secrets, and private section contents.
- Provider output may change only section order and an allowlisted connector code; exact section coverage is mandatory.
- Provider failure must return the complete deterministic answer and must never create an empty Case trace.
- The failed bundle `1642b7ff5124f710477033b6d29c76a2328f0b57d976971723f2d9f515cb13e6` is immutable and must not be overwritten or merged.
- No confirmed action, production write, notification delivery, or Telegram send is authorized.
- Use TDD for every behavior change; run the named RED command before implementation and record the actual failure.

---

## File Responsibility Map

| File | Responsibility in this correction |
| --- | --- |
| `backend/app/services/agent_composer_v2.py` | Strict ordering contracts, deterministic section sealing, sanitized request projection, exact expansion, connector rendering, fallback integration |
| `backend/app/services/agent_composer_provider.py` | Real Gateway adapter for ordering request/response and exact semantic validation |
| `backend/scripts/stage12_isolated_af_runner.py` | Use the ordering Provider port and prove Provider failures stay inside a complete trace |
| `backend/scripts/stage12_final_provider_campaign.py` | Use the corrected real adapter, preserve exact three-round accounting, validate bundle identity and sanitized failure observations |
| `backend/tests/unit/test_agent_composer_v2.py` | Contract, hash, sanitization, expansion, rendering, and fallback tests |
| `backend/tests/unit/test_agent_composer_provider.py` | Adapter request/response, repair, exact coverage, and failure-taxonomy tests |
| `backend/tests/unit/test_stage12_isolated_af_runner.py` | Raw-query integrated trace and 48-Case hard-gate tests |
| `backend/tests/unit/test_stage12_final_provider_campaign.py` | Fake 144-call campaign, observation, atomic output, and safety tests |
| Stage12 status/evidence docs | Actual commands, results, skips, hashes, remaining risks, and cleanup |

### Task 1: Add strict deterministic section and ordering contracts

**Files:**
- Modify: `backend/app/services/agent_composer_v2.py:42-105`
- Modify: `backend/tests/unit/test_agent_composer_v2.py:1-360`

**Interfaces:**
- Consumes: existing `ComposerAnswerSectionPlanV2`, `ComposerAnswerPlanV2`, `ClaimGraphV1`, `AuthorizedSchemaSnapshot`, `specialist_payload_sha256`.
- Produces: `DeterministicComposerSectionV1`, `DeterministicSectionSetV1`, `ComposerSectionCandidateV1`, `ComposerSectionOrderingRequestV1`, `ComposerSectionOrderingPlanV1`, `build_deterministic_section_set()`, `build_section_ordering_request()`.

- [x] **Step 1: Write RED strict-model and hash tests**

Add tests that construct a two-section deterministic plan and assert:

```python
section_set = build_deterministic_section_set(plan, graph)
assert tuple(item.default_rank for item in section_set.sections) == (0, 1)
assert all(item.section_handle.startswith("section:sha256:") for item in section_set.sections)
assert section_set == build_deterministic_section_set(plan, graph)
duplicate_payload = section_set.model_dump(mode="python")
duplicate_payload["sections"][1]["section_handle"] = duplicate_payload["sections"][0]["section_handle"]
with pytest.raises(ValidationError, match="deterministic_section_handle_duplicate"):
    DeterministicSectionSetV1.model_validate(duplicate_payload)
rank_payload = section_set.model_dump(mode="python")
rank_payload["sections"][1]["default_rank"] = 3
with pytest.raises(ValidationError, match="deterministic_section_rank_invalid"):
    DeterministicSectionSetV1.model_validate(rank_payload)
```

Also assert mutation raises Pydantic's frozen-instance error and unknown fields are rejected.

- [x] **Step 2: Run the focused RED test**

Run:

```powershell
cd backend
python -m pytest tests/unit/test_agent_composer_v2.py -k "deterministic_section or ordering_contract" -q
```

Expected: FAIL because the new contracts and builders do not exist.

- [x] **Step 3: Implement strict models and canonical hashes**

Add `ConnectorCode` and the five approved models. Use these exact patterns:

```python
ConnectorCode = Literal["direct", "next", "however", "safety_boundary"]

def _section_handle(values: Mapping[str, object]) -> str:
    return "section:sha256:" + specialist_payload_sha256(values)
```

Implement `build_deterministic_section_set(plan: ComposerAnswerPlanV2, graph: ClaimGraphV1) -> DeterministicSectionSetV1` by enumerating `plan.sections`, deriving the kind-specific connector allowlist, hashing each canonical private section payload, validating referenced Objective statuses against `graph`, then hashing the ordered child projections. Implement `build_section_ordering_request(section_set: DeterministicSectionSetV1, *, graph: ClaimGraphV1, authorized_schema: AuthorizedSchemaSnapshot) -> ComposerSectionOrderingRequestV1` by projecting only the approved public candidate fields and the four authority proofs.

Map Objective statuses through the section's private Objective IDs, deduplicate them, and sort them by:

```text
completed, proposed, degraded, denied, failed
```

Use the connector allowlist table from the approved spec. Reject section kinds, handles, hashes, ranks, or proof hashes that do not validate.

- [x] **Step 4: Write and run RED sanitization tests**

Serialize `ComposerSectionOrderingRequestV1` and assert it contains section handles/kinds/statuses but none of:

```python
for forbidden in (
    "objective_id", "claim_id", "action_slot_id", "evidence_id",
    "record:", "field:", "expected_", "gold_", "query",
):
    assert forbidden not in serialized
```

Run the same focused command; expected first run: FAIL until the projection excludes every private field.

- [x] **Step 5: Complete the sanitized projection and make Task 1 green**

Run:

```powershell
python -m pytest tests/unit/test_agent_composer_v2.py -k "deterministic_section or ordering_contract or ordering_request" -q
```

Expected: PASS.

- [x] **Step 6: Commit Task 1**

```powershell
git add backend/app/services/agent_composer_v2.py backend/tests/unit/test_agent_composer_v2.py
git commit -m "feat: seal Stage12 composer sections"
```

### Task 2: Replace the real Provider boundary with exact handle ordering

**Files:**
- Modify: `backend/app/services/agent_composer_provider.py:1-140`
- Modify: `backend/tests/unit/test_agent_composer_provider.py:1-180`

**Interfaces:**
- Consumes: `ComposerSectionOrderingRequestV1`, `ComposerSectionOrderingPlanV1`, `ModelGatewayV1.invoke()`.
- Produces: `ComposerProviderAdapterV1.__call__(request: ComposerSectionOrderingRequestV1) -> ComposerSectionOrderingPlanV1` and exact semantic validation before a Provider attempt is marked completed.

- [x] **Step 1: Replace the happy-path adapter test with the bounded payload**

Build a request with handles `section:sha256:` plus 64 `a` characters and `section:sha256:` plus 64 `b` characters. Make the fake Gateway return the corresponding complete literals:

```json
{
  "version": "composer-section-ordering-plan.v1",
  "ordered_section_handles": [
    "section:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "section:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  ],
  "connector_by_handle": {
    "section:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": "direct",
    "section:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": "next"
  }
}
```

Assert the outbound Provider messages contain no Objective/Claim/Action IDs, facts, evidence, query, or values, and the response schema is strict.

- [x] **Step 2: Run RED**

```powershell
python -m pytest tests/unit/test_agent_composer_provider.py -q
```

Expected: FAIL because the adapter still accepts `ComposerProviderRequestV2` and returns `ComposerAnswerPlanV2`.

- [x] **Step 3: Implement exact ordering validation**

Replace `_validate_plan_references` with:

```python
def _validate_ordering_plan(
    request: ComposerSectionOrderingRequestV1,
    plan: ComposerSectionOrderingPlanV1,
) -> None:
    expected = tuple(item.section_handle for item in request.candidates)
    if len(set(plan.ordered_section_handles)) != len(expected):
        raise ProviderValidationError("provider_semantic_invalid", "$.ordered_section_handles")
    if set(plan.ordered_section_handles) != set(expected):
        raise ProviderValidationError("provider_semantic_invalid", "$.ordered_section_handles")
    if set(plan.connector_by_handle) != set(expected):
        raise ProviderValidationError("provider_semantic_invalid", "$.connector_by_handle")
    # validate first/direct, later/non-direct, and per-candidate allowlists
```

The Gateway `validate` callback must parse `ComposerSectionOrderingPlanV1`, run this function, and only then return the payload.

- [x] **Step 4: Add adversarial RED/GREEN cases**

Cover, as separate tests:

- missing handle;
- duplicate handle;
- unknown handle;
- missing/extra connector-map key;
- connector outside candidate allowlist;
- first connector not `direct`;
- later connector equal to `direct`;
- first invalid response followed by a valid repair;
- repair exhaustion preserving `provider_schema_invalid` or `provider_semantic_invalid`.

Run the full adapter file after each minimal implementation slice.

- [x] **Step 5: Verify the prompt and token boundary**

Assert the system prompt says the model may only permute supplied handles and choose supplied connectors. Assert the user payload equals the ordering request projection, not `ClaimGraphV1` or presentation content. Keep response `max_tokens` under the existing profile limit; do not change the profile.

- [x] **Step 6: Run Task 2 green**

```powershell
python -m pytest tests/unit/test_agent_composer_provider.py tests/unit/test_agent_model_gateway.py -q
```

Expected: PASS with existing Gateway retry/taxonomy tests unchanged.

- [x] **Step 7: Commit Task 2**

```powershell
git add backend/app/services/agent_composer_provider.py backend/tests/unit/test_agent_composer_provider.py
git commit -m "feat: bound Stage12 provider ordering"
```

### Task 3: Expand validated handles and preserve deterministic fallback

**Files:**
- Modify: `backend/app/services/agent_composer_v2.py:168-550`
- Modify: `backend/tests/unit/test_agent_composer_v2.py:100-700`

**Interfaces:**
- Consumes: Task 1 section set/request models and Task 2 ordering Provider callable.
- Produces: `expand_ordering_plan(section_set, ordering) -> ComposerAnswerPlanV2`, connector rendering, and `compose_claim_graph()` with complete fallback.

- [x] **Step 1: Write RED expansion tests**

Assert a reversed valid ordering returns the exact original private IDs in reversed section order:

```python
expanded = expand_ordering_plan(section_set, ordering)
assert tuple(item.section_kind for item in expanded.sections) == ("actions", "facts")
assert expanded.sections[0].action_slot_ids == original_actions.action_slot_ids
assert expanded.sections[1].claim_ids == original_facts.claim_ids
```

Add direct calls that forge an unknown handle or invalid connector and assert fail-closed exceptions even if model construction was bypassed with `model_construct`.

- [x] **Step 2: Run RED and implement pure expansion**

```powershell
python -m pytest tests/unit/test_agent_composer_v2.py -k "expand_ordering" -q
```

Expected RED: function absent. Implement lookup-only expansion and revalidate the resulting `ComposerAnswerPlanV2`.

- [x] **Step 3: Write RED connector-rendering tests**

Build four sections with `direct`, `next`, `however`, and `safety_boundary`; assert exact prefixes:

```text
direct -> ""
接下来，
不过，
安全边界：
```

Assert Provider output never contributes arbitrary prose.

- [x] **Step 4: Implement fixed connector rendering**

Add a constant mapping and prefix the existing fixed section title/rendered sentences. Do not allow connector text from Provider input.

- [x] **Step 5: Write RED complete-fallback tests**

Inject providers that raise each existing failure class and one provider that returns a plan with an unknown handle. For every case assert:

```python
assert result.render_receipt.covered_objective_ids == deterministic.render_receipt.covered_objective_ids
assert result.render_receipt.covered_claim_ids == deterministic.render_receipt.covered_claim_ids
assert result.render_receipt.covered_action_slot_ids == deterministic.render_receipt.covered_action_slot_ids
assert result.provider_call_count == 1
assert failure_code in result.degradation_codes
assert result.answer
```

- [x] **Step 6: Change `compose_claim_graph` to the ordering port**

Inside the existing authorized-field-policy gate:

```python
deterministic_plan = _default_plan(graph, presentation)
section_set = build_deterministic_section_set(deterministic_plan, graph)
request = build_section_ordering_request(
    section_set,
    graph=graph,
    authorized_schema=authorized_schema,
)
try:
    ordering = provider(request)
    plan = expand_ordering_plan(section_set, ordering)
except Exception as exc:
    # preserve existing safe taxonomy and deterministic_plan
else:
    # render expanded plan
```

Do not call Provider when field-policy proof is absent or mismatched.

- [x] **Step 7: Run the full Composer matrix**

```powershell
python -m pytest tests/unit/test_agent_composer_v2.py tests/unit/test_agent_composer_provider.py tests/unit/test_agent_claim_graph.py tests/unit/test_agent_specialist_results.py -q
```

Expected: PASS; deterministic receipt hashes may change only where fixed connector text changes, and tests must assert the new actual hashes rather than bypass validation.

- [x] **Step 8: Commit Task 3**

```powershell
git add backend/app/services/agent_composer_v2.py backend/tests/unit/test_agent_composer_v2.py
git commit -m "fix: preserve deterministic composer fallback"
```

### Task 4: Integrate the ordering contract into isolated and final runners

**Files:**
- Modify: `backend/scripts/stage12_isolated_af_runner.py:237-420,2384-2435`
- Modify: `backend/scripts/stage12_final_provider_campaign.py:64-460`
- Modify: `backend/tests/unit/test_stage12_isolated_af_runner.py:1-880`
- Modify: `backend/tests/unit/test_stage12_final_provider_campaign.py:1-270`

**Interfaces:**
- Consumes: corrected `ComposerProviderAdapterV1` and ordering port.
- Produces: complete raw-query traces for every Provider failure, exact fake `48 × 3` accounting, and sanitized per-round execution/Provider failure counts.

- [x] **Step 1: Migrate fake Providers in RED**

Change `_ObservedComposerProvider` and `_ValidComposerProvider` to read ordering candidates and return an identity permutation with `direct` for the first handle and the first allowed non-direct connector for later handles. Before implementation, run:

```powershell
python -m pytest tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_final_provider_campaign.py -q
```

Expected: RED because runtime still expects full `ComposerAnswerPlanV2` responses.

- [x] **Step 2: Update isolated runner typing and Provider trace projection**

Keep observation extraction from `ComposerProviderAdapterV1.observations`. Do not add raw ordering content to `IsolatedAFRunObservationV1`. Ensure a Provider semantic failure produces a completed/degraded runtime trace with Planner, Query, Retrieval, Specialist, ClaimGraph, Composer, Action, total latency, and safe final receipt all observed.

- [x] **Step 3: Add explicit regression for the two collapsed Cases**

For `mixed_02` and `mixed_08`, inject an invalid ordering Provider and assert:

```python
assert observation.status == "completed"
assert trace.planner is not None
assert trace.query.observation_status == "observed"
assert trace.answer.observation_status == "observed"
assert trace.answer.render_receipt is not None
assert trace.safety.unauthorized_effect_count == 0
assert trace.safety.external_send_count == 0
```

`RuntimeTraceV2` owns the receipt only at `trace.answer.render_receipt`; do not add a parallel receipt field.

- [x] **Step 4: Prove fake valid campaign shape**

The final-campaign test must assert:

```python
assert provider.call_count == 144
assert len(bundle.report.results) == 144
assert [item.required_count for item in bundle.provider_rounds] == [48, 48, 48]
assert [item.unavailable_count for item in bundle.provider_rounds] == [0, 0, 0]
assert bundle.summary.release_gate_pass is True
```

Also assert exact retrieval calls `[1, 2, 3]`, no temporary files, no secrets, and zero confirmation/write/send counts.

- [x] **Step 5: Prove fake invalid campaign remains auditable**

Inject schema-invalid and semantic-invalid attempts for selected Cases. Assert fallback answers remain quality-valid while Provider unavailable and failure counts make the aggregate release gate fail. The result must still contain 144 complete traces.

- [x] **Step 6: Run Task 4 green**

```powershell
python -m pytest tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_final_provider_campaign.py -q
```

Expected: PASS, with the 48-Case full hard-gate regression still `48/48` and effects `0/0/0`.

- [x] **Step 7: Commit Task 4**

```powershell
git add backend/scripts/stage12_isolated_af_runner.py backend/scripts/stage12_final_provider_campaign.py backend/tests/unit/test_stage12_isolated_af_runner.py backend/tests/unit/test_stage12_final_provider_campaign.py
git commit -m "test: integrate bounded composer campaign"
```

### Task 5: Execute local technical acceptance without real Provider calls

**Files:**
- Modify after actual results: `docs/superpowers/plans/2026-07-31-stage12-bounded-deterministic-section-provider.md`
- Modify after actual results: `project-docs/08-implementation/evidence/stage12-final-provider-campaign-2026-07-31/AUDIT.md`

**Interfaces:**
- Consumes: Tasks 1–4 implementation.
- Produces: current local evidence proving the corrected code is eligible for a new real campaign.

- [x] **Step 1: Run focused affected tests**

```powershell
cd backend
python -m pytest -q tests/unit/test_agent_composer_v2.py tests/unit/test_agent_composer_provider.py tests/unit/test_agent_model_gateway.py tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_final_provider_campaign.py
```

Record exact passed/failed counts and duration.

- [x] **Step 2: Run expanded Stage12/Planner/Query/Specialist regression**

```powershell
python -m pytest tests/unit -q -k "stage12 or agent_task_planner_v2 or agent_query_lexical or authorized_query or authorized_table_query or agent_specialist or agent_composer_v2 or agent_claim_graph"
```

Record exact passed and deselected counts. Any failure blocks the real campaign.

- [x] **Step 3: Recompute the deterministic 48-Case hard gates**

Run the existing full-set test:

```powershell
python -m pytest tests/unit/test_stage12_isolated_af_runner.py -q -k full_final_answer_gate
```

Require every Planner/Query/Retrieval/Answer/final-answer/Action/Safety/Durability and complete release gate `48/48`, total latency observed `48/48`, and confirmed/write/send `0/0/0`.

- [x] **Step 4: Run full backend from the correct working directory**

```powershell
cd backend
python -m pytest tests -q
```

Do not run `python -m pytest backend/tests` from the repository root because historical migration tests resolve `alembic/` relative to `backend/`. Classify every skip; do not count skips as passes.

- [x] **Step 5: Run the real disposable PostgreSQL/pgvector Stage12 matrix**

Use only the existing disposable database whose name contains `stage06`, `test`, or `smoke`:

```powershell
$env:STAGE06_LOCAL_DATABASE_URL='postgresql+psycopg://ads_agent:ads_agent@127.0.0.1:5432/ads_agent_stage12_test?connect_timeout=3'
python -m pytest -q tests/integration/test_stage12_authorized_query_postgres.py tests/integration/test_stage12_retrieval_v2_postgres.py tests/integration/test_stage12_typed_specialist_runtime_postgres.py tests/integration/test_stage12_action_runtime_postgres.py
```

Require `7 passed`, Alembic current/head `20260730_0039`, pgvector present, and zero `stage12_%` temporary schemas. Never point this suite at the primary `ads_agent` database.

- [x] **Step 6: Run hygiene and static verification**

```powershell
python -m black --check app/services/agent_composer_v2.py app/services/agent_composer_provider.py scripts/stage12_isolated_af_runner.py scripts/stage12_final_provider_campaign.py tests/unit/test_agent_composer_v2.py tests/unit/test_agent_composer_provider.py tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_final_provider_campaign.py
python -m compileall -q app/services/agent_composer_v2.py app/services/agent_composer_provider.py scripts/stage12_isolated_af_runner.py scripts/stage12_final_provider_campaign.py tests/unit/test_agent_composer_v2.py tests/unit/test_agent_composer_provider.py tests/unit/test_stage12_isolated_af_runner.py tests/unit/test_stage12_final_provider_campaign.py
git diff --check
rg -n "mixed_02|mixed_08|expected_query_result|gold_audit" app
rg -n "OPENROUTER_API_KEY|sk-or-|Bearer " ../project-docs/08-implementation/evidence
```

Production Case-ID/Gold-key and evidence secret scans must be empty. Black, compileall, and diff check must pass.

- [x] **Step 7: Clean generated temporary files**

List exact contents under `backend/.tmp`. Delete only directories created by this correction, verify their resolved paths remain under `backend/.tmp`, and preserve pre-existing retained artifacts such as `stage12-task9b-20260731` unless the active retention document says otherwise.

- [x] **Step 8: Record local acceptance and commit**

Update this plan and audit evidence with changed files, actual verification, skips, remaining risks, and cleanup. Do not claim Stage12 acceptance or Provider improvement yet.

```powershell
git add docs/superpowers/plans/2026-07-31-stage12-bounded-deterministic-section-provider.md project-docs/08-implementation/evidence/stage12-final-provider-campaign-2026-07-31/AUDIT.md
git commit -m "docs: record bounded composer local audit"
```

#### Task 5 execution evidence

- Implementation commits: `db5ff5c`, `76130b6`, `ab069df`, `b6338f8`, `622784e`.
- Focused affected matrix: `113 passed in 35.14s`.
- Expanded Stage12/Planner/Query/Specialist regression: `446 passed, 1627 deselected in 40.32s`.
- Deterministic Human-Gold gate: `1 passed, 52 deselected`; the test iterated all 48 Cases, every Planner/Query/Retrieval/Answer/final-answer/Action/Safety/Durability/release gate passed, every trace contained total latency, and confirmed/write/send totals were `0/0/0`.
- Full backend from `backend/`: `2411 passed, 40 skipped in 434.80s`. Skips were 3 Stage10 Redis, 17 Stage02 online PostgreSQL, 3 Stage08 collaboration PostgreSQL, and 17 Stage08 pgvector tests; none are counted as passed.
- Disposable `ads_agent_stage12_test` PostgreSQL matrix: `7 passed in 8.09s`; PostgreSQL `18.4`, pgvector `0.8.3`, Alembic current/head `20260730_0039`, retained `stage12_%` schemas `0`.
- Black check for the eight affected implementation/test files, compileall, target/global diff checks, and production Gold/Case scan passed. Precise evidence secret-value scan was empty; the broader scan found only a historical Stage07 mention of the environment-variable name `OPENROUTER_API_KEY`, with no value.
- Temporary cleanup: this correction created no retained directory under `backend/.tmp`. Existing `pytest-of-29230`, `stage12-task2-a`, and `stage12-task9b-20260731` directories were preserved.
- Production status: unchanged. No deployment, production migration, confirmed Action, business write, notification, or Telegram send occurred.
- Remaining risk: local gates prove contract integrity and deterministic fallback, but do not prove real Provider availability or latency. Stage12 remains `FAIL` on the immutable pre-correction bundle until Task 6 produces one new independent real `48 × 3` bundle.

### Task 6: Run one new independent real campaign and close or retain the gate

**Files:**
- Create on successful runner execution: `project-docs/08-implementation/evidence/stage12-final-provider-campaign-v2-2026-07-31/stage12-final-provider-campaign.json`
- Create on successful runner execution: `project-docs/08-implementation/evidence/stage12-final-provider-campaign-v2-2026-07-31/stage12-final-provider-campaign.md`
- Create: `project-docs/08-implementation/evidence/stage12-final-provider-campaign-v2-2026-07-31/AUDIT.md`
- Modify: `AGENTS.md`
- Modify: `HANDOFF.md`
- Modify: `project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md`
- Modify: `project-docs/08-implementation/README.md`
- Modify: active Stage12 source/acceptance documents

**Interfaces:**
- Consumes: green Task 5 evidence, ignored local env file, frozen Human Gold `48/48`.
- Produces: one immutable post-correction `48 × 3` real bundle and an honest release decision.

- [ ] **Step 1: Run non-network preflight**

Verify without printing values:

```text
OPENROUTER_API_KEY present
OPENROUTER_BASE_URL present
OPENROUTER_MODEL present (runner still binds the frozen Composer profile)
Human Gold status human_approved for exactly 48 unique Cases
manifest hash 5b959d049c4f46f9dbd92e65c1dfe17a81a357f394f2f9a33b34da4e6ee28114
output directory absent or empty
```

Validate the runner with fake Provider once more. Do not start network if any preflight fails.

- [ ] **Step 2: Execute exactly one new auditable campaign**

```powershell
cd backend
python -m scripts.stage12_final_provider_campaign `
  --env-file "D:\telegram多维表格和工作智能体的开发\.local\stage05-real-workflow.env" `
  --output-dir "..\project-docs\08-implementation\evidence\stage12-final-provider-campaign-v2-2026-07-31"
```

The CLI must still hard-code three rounds and `materialize_actions=True`. Do not add a rounds override or selective Case retry.

- [ ] **Step 3: Validate the immutable bundle offline**

Load it through `FinalProviderCampaignBundleV1.model_validate_json` and require:

```text
case_count = 48
rounds = 3
results = 144
retrieval rounds = round-01, round-02, round-03
provider rounds = round-01, round-02, round-03
Human Gold = 48
confirmed/write/send = 0/0/0 for every round
content hash valid
```

Scan evidence for secrets, raw prompt/response, query, Gold, and temporary files.

- [ ] **Step 4: Evaluate every unchanged hard gate**

Report mean, worst, population variance, observed/expected counts, and gate status for every metric. Pay special attention to:

```text
provider_unavailable_rate <= 0.02
p95_total_latency_ms <= 8000
permission_safety = 1.00
external_send_safety = 1.00
all final-answer gates
```

If any gate fails, retain the bundle, mark Stage12 `FAIL`, list exact dimensions/Cases/failure taxonomy, and do not rerun or average it away.

- [ ] **Step 5: Update all active truth and handoff documents**

Replace stale pre-correction status in active top-level documents. Preserve old bundles and historical evidence as explicitly superseded snapshots. Include changed files, verification, skipped tests, remaining risks, temporary cleanup, deployment status, and the exact bundle/manifest hashes.

- [ ] **Step 6: Run final documentation and repository checks**

```powershell
git diff --check
rg -n "Human Gold.*0/48|Provider.*0/3|pending_explicit_human_signoff" AGENTS.md HANDOFF.md project-docs/00-governance/IMPLEMENTATION_SOURCE_OF_TRUTH.md project-docs/08-implementation/README.md
git status --short
```

Active top-level truth must not contradict the new evidence. Historical documents may retain old counts only when clearly labelled as historical/superseded.

- [ ] **Step 7: Commit final evidence without deploying**

Stage only reviewed Stage12 correction/evidence files and verify the staged list before committing:

```powershell
git diff --cached --name-only
git diff --cached --check
git commit -m "feat: bound Stage12 composer provider"
```

Do not push, deploy, migrate production, activate Stage12, confirm an Action, write business data, or send Telegram without a separate user instruction.

---

## Plan Completion Criteria

This plan is complete only when:

1. every Task checkbox has actual command evidence;
2. the bounded ordering contract is the only Stage12 Composer Provider boundary;
3. all local deterministic, backend, and PostgreSQL gates pass;
4. one new independent real `48 × 3` bundle exists and validates;
5. every hard gate passes for Stage12 acceptance, or the stage remains explicitly `FAIL` with exact evidence;
6. all active documents agree;
7. temporary artifacts are cleaned or documented;
8. production remains unchanged unless separately authorized.
