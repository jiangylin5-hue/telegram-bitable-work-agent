# Stage12 Grounded Answer Provider V2 Design

## Status

- Status: `approved-for-written-spec-review`
- Scope: Stage12 final-answer Provider contract, real-model acceptance, diagnostic telemetry, and native-server validation boundary
- Trigger evidence: post-correction real campaign bundle `6b15446524a5a084d744dfc82564a73354d1477260c8e2e705375e9c392f1aa8`
- User decision: approved in-thread on 2026-07-31
- Production authority: Stage11/r76 remains authoritative until every gate in this document passes
- Deployment baseline: native Nginx + systemd + FastAPI + PostgreSQL/pgvector + Redis; Docker and Docker Compose are excluded

## 1. Problem Statement

The bounded `ComposerSectionOrderingPlanV1` correction improved returned-answer integrity but does not satisfy the product goal. In the post-correction `48 cases × 3 rounds` campaign, all 144 returned answers passed because deterministic rendering remained available, while only 24 of 144 cases obtained a completed real Composer result. The other 120 cases exhausted two schema-invalid attempts, producing 240 `provider_schema_invalid` observations.

The current Provider role only reorders sealed section handles and chooses connectors. It does not author the substantive final answer. Therefore:

1. deterministic fallback quality cannot prove real-model answer quality;
2. `provider_unavailable` conflates transport unavailability with an unusable Provider result;
3. a full campaign was started without a small real structured-output compatibility gate;
4. the retained evidence intentionally omits raw Provider output, so it proves validation failure but not the exact malformed field;
5. the Stage12 acceptance definition can pass user-visible answers while the intended real-model path is mostly unused.

Official capability checks do not support the claim that the selected model lacks structured-output support. OpenRouter lists `structured_outputs` and `response_format` for `google/gemini-2.5-flash`, and Google documents structured output for Gemini 2.5 Flash. The first Grounded Answer P1 attempt subsequently proved a narrower incompatibility: Google AI Studio rejected the complete response schema with HTTP `400 INVALID_ARGUMENT` because it produced too many serving states. TDR-023 therefore selects a measured domestic Composer candidate without weakening the contract.

Authoritative references:

- OpenRouter structured outputs: <https://openrouter.ai/docs/guides/features/structured-outputs>
- OpenRouter provider parameter routing: <https://openrouter.ai/docs/guides/routing/provider-selection>
- Google Gemini structured outputs: <https://ai.google.dev/gemini-api/docs/structured-output>

## 2. Goals

1. Make a real Provider call author the complete final Chinese answer structure and prose from permission-filtered Stage12 artifacts.
2. Keep table facts, joins, aggregates, permissions, record versions and Action authority outside the model.
3. Reject ungrounded factual, action or citation output before it becomes a user answer.
4. Distinguish HTTP/provider transport failures, schema failures, semantic-grounding failures and deterministic fallback.
5. Count only `answer_source=real_provider` results toward the Stage12 real-model quality gate.
6. Prove schema compatibility with a small real preflight before any new `48 × 3` campaign.
7. Preserve a deterministic fallback for runtime safety without allowing it to satisfy the real-model release gate.
8. Publish only committed, audited Stage12 sources and validate them through the existing native-server release path.
9. Execute bounded real server-backend and real Telegram tests after local gates pass, with Stage11/r76 retained as rollback authority.

## 3. Non-Goals

- No Docker image, Docker Compose service or container migration.
- No change to PostgreSQL, pgvector, Redis, Nginx or systemd as the chosen native stack.
- No free-form SQL, raw database credentials or unrestricted Provider/tool access.
- No Provider-authored record values, joins, aggregates, permissions, Action targets or execution tickets.
- No weakening of existing field-policy, citation, Action confirmation, Tool Gateway, audit or Telegram allowlist boundaries.
- No business-context architecture; it remains explicitly outside Stage12.
- No use of fallback results to claim real-model success.
- No production-wide Stage12 activation before the isolated server and Telegram gates pass.
- TDR-023 supersedes the original no-profile-replacement constraint for the Stage12 Grounded Composer only. Gemini, Qwen 235B and Qwen Next 80B failed complete P1 attempts; the measured fixed P1/P2/P3 candidate is `deepseek/deepseek-v3.2` after an unchanged-schema four-shape `4/4` comparison. No automatic multi-model routing or per-case failover is added.

## 4. Chosen Architecture

```text
raw authorized Query
  -> TaskSpecV2
  -> Authorized Query Plan / structured execution
  -> Typed Specialist artifacts
  -> sealed ClaimGraphV1
  -> GroundedAnswerProviderRequestV2
       objectives
       canonical facts and relation/aggregate results
       risk/daily analysis artifacts
       evidence provenance and record versions
       pending-only authorized Action summaries
       response policy and Chinese presentation requirements
  -> real Grounded Answer Provider
  -> GroundedAnswerPlanV2
       ordered sections[]
       model-authored statement text
       statement kind
       claim/evidence/action references
  -> deterministic schema + grounding validation
  -> exact render receipt
  -> user-visible answer with answer_source=real_provider
```

If the Provider result fails, the runtime may return the existing deterministic safe answer with `answer_source=deterministic_fallback`. That result remains visible and safe, but it fails the Stage12 real-model acceptance gate.

## 5. Provider Input Contract

`GroundedAnswerProviderRequestV2` is a private, immutable, permission-filtered contract. It contains fixed-property arrays rather than dynamic-key maps.

### 5.1 Required top-level fields

| Field | Meaning |
| --- | --- |
| `version` | Literal `grounded-answer-provider-request.v2` |
| `language` | Literal `zh-CN` |
| `objectives` | Ordered objective handles, kind and completion status |
| `claims` | Canonical authorized facts with predicate, typed value projection, evidence handles and source versions |
| `specialist_findings` | Validated Risk/Daily/Tabular analytical findings bound to claims |
| `actions` | Pending-only authorized Action summaries; no execution authority |
| `citations` | Safe citation handles and display labels |
| `presentation_policy` | Section limits, statement limits, refusal/degradation requirements and allowed statement kinds |
| `scope_hash` | Effective permission scope proof |
| `field_policy_version` | Exact Stage12 field-policy version |
| `field_policy_hash` | Exact effective field-policy hash |
| `content_hash` | Canonical hash of every preceding field |

The request may include the authorized user query because the model must understand instruction and emphasis. It must not include raw database credentials, hidden fields, unrestricted table dumps, Gold truth, Case IDs, expected actions, expected answer text or unauthorized context.

### 5.2 Canonical claim representation

Each claim uses fixed properties:

```json
{
  "claim_handle": "claim:sha256:...",
  "objective_handle": "objective:sha256:...",
  "subject_label": "Atlas 项目",
  "predicate_label": "未完成高优先级工作项数量",
  "value_type": "integer",
  "value_text": "2",
  "qualifiers": ["状态 != 已完成", "优先级 = 高"],
  "evidence_handles": ["evidence:sha256:..."],
  "source_versions": ["record-version:sha256:..."]
}
```

The model may explain and combine claims, but it cannot change `value_text`, create a new claim/evidence/action handle or cite a handle outside the request.

## 6. Provider Output Contract

`GroundedAnswerPlanV2` uses only fixed-property objects and arrays. Every object sets `additionalProperties=false`. Business validation remains application-side even when the upstream provider reports strict structured-output support.

```json
{
  "version": "grounded-answer-plan.v2",
  "sections": [
    {
      "section_kind": "answer",
      "heading": "结论",
      "statements": [
        {
          "statement_kind": "fact",
          "text": "Atlas 项目有 2 个高优先级且未完成的工作项。",
          "claim_handles": ["claim:sha256:..."],
          "evidence_handles": ["evidence:sha256:..."],
          "action_handles": []
        }
      ]
    }
  ]
}
```

### 6.1 Statement kinds

- `fact`: must reference at least one canonical claim and its exact evidence closure.
- `analysis`: must reference the complete set of claims on which the reasoning depends.
- `recommendation`: must be phrased as advice, not as an executed or confirmed action, and must reference supporting claims.
- `action_status`: must reference an authorized pending Action handle and must preserve its exact status.
- `limitation`: explains missing permission, missing evidence, degradation or refusal; it cannot claim a business fact.

### 6.2 Schema portability rules

1. No object whose business keys are generated hashes.
2. No `dict[str, T]` in the Provider response schema.
3. No open-ended `additionalProperties` object.
4. Fixed enums for section and statement kinds.
5. Explicit descriptions for every Provider-facing field.
6. Shallow nesting and bounded array lengths.
7. Provider schema generation and Pydantic validation are separate tests.
8. The selected model must advertise both `structured_outputs` and `response_format`; OpenRouter routing keeps `require_parameters=true`.

These rules improve portability but are not accepted as the historical root cause until the diagnostic preflight proves the actual failure shape.

## 7. Grounding and Safety Validation

The server validates in this order:

1. **JSON/schema:** exact `GroundedAnswerPlanV2`, no extra fields, bounded lengths.
2. **Reference closure:** every objective, claim, evidence and Action handle exists in the sealed request.
3. **Citation closure:** a statement's evidence handles equal the union required by its referenced claims; arbitrary allowed citations are insufficient.
4. **Canonical atom validation:** entity labels, codes, numbers, dates, currencies, percentages, enum values and statuses appearing in `fact`, `analysis`, `recommendation` or `action_status` text must be present in the referenced canonical claims or safe presentation vocabulary.
5. **Action boundary:** no statement may say an Action was executed, confirmed, sent or persisted unless the sealed Action status says so.
6. **Permission/version binding:** scope, field policy and record versions must still match before rendering.
7. **Coverage:** every required objective has at least one accepted statement or an explicit limitation/refusal statement.
8. **Language/presentation:** Chinese clarity and prohibited internal-token checks run last.

A schema-valid response can still be `provider_semantic_invalid`. Hash or ID subset checks alone are not sufficient.

## 8. Failure Taxonomy and Diagnostic Evidence

The public and evidence taxonomy is split as follows:

| Code | Meaning |
| --- | --- |
| `provider_http_error` | Non-success HTTP or invalid upstream envelope |
| `provider_timeout` | Request deadline exceeded |
| `provider_rate_limited` | HTTP 429 |
| `provider_quota_exhausted` | HTTP 402/403 classified as quota/authorization failure |
| `provider_schema_invalid` | Response content cannot validate as the exact output schema |
| `provider_grounding_invalid` | References, canonical atoms, facts, citations or Action status are invalid |
| `provider_language_invalid` | Required Chinese presentation contract fails |
| `deterministic_fallback_used` | Safe fallback returned; never counted as real-model success |

The focused diagnostic retains only sanitized fingerprints:

- HTTP status class;
- Provider/model/profile identity;
- attempt number and latency;
- Pydantic error types and JSON paths;
- top-level JSON type;
- sorted top-level key names;
- section/statement counts;
- response byte length and SHA-256;
- input/output token counts;
- whether repair was attempted.

It does not persist raw prompts, raw Provider outputs, secrets, Telegram/chat/user IDs, unauthorized business values or Gold payloads. A one-run in-memory debug mode may inspect raw synthetic output locally, but it must be disabled by default and produce no retained raw artifact.

## 9. Real-Model Acceptance Gates

### Gate P0: capability and schema build

- Selected OpenRouter model advertises `structured_outputs` and `response_format`.
- Provider-safe schema generation passes local structural checks.
- No dynamic-key response object exists.

### Gate P1: real structured-output compatibility smoke

- Exactly 12 real calls: 1, 2, 4 and 7 statement/section shapes, each repeated three times.
- `12/12` HTTP completed.
- `12/12` exact schema valid.
- `12/12` grounding valid.
- `12/12` `answer_source=real_provider`.
- `0` fallback and `0` retained raw output.

Failure stops the pipeline. It does not trigger a full campaign.

### Gate P2: representative end-to-end preflight

- A documented bounded subset covers single-table, relation, aggregate, risk, daily, mixed and Action/refusal cases.
- Three independent real rounds.
- Every result must be Provider-originated; any fallback fails P2.
- Final answers are scored from actual returned model text, not deterministic substitute text.
- No confirmed Action, production record write or unrestricted Telegram send.

### Gate P3: final Human-Gold campaign

- Frozen 48 Human-Gold cases, exactly three independent real rounds.
- `144/144` results have `answer_source=real_provider`.
- `fallback_count=0` for Stage12 acceptance.
- Existing factual correctness, completeness, relation/aggregate, citation, instruction/action, Chinese clarity, refusal/degradation and safety gates remain unchanged or become stricter.
- Provider transport/schema/grounding failure rates are reported separately.
- Existing total-latency P95 gate remains `<= 8000 ms` unless a separately approved SLO decision changes it.
- Mean, worst round and population variance are reported; no selective retry or fourth-round merge.

The production runtime may retain a broader availability SLO and safe fallback policy. That operational fallback does not alter the zero-fallback Stage12 acceptance requirement.

## 10. Runtime and Public Projection

The internal trace and safe result add:

- `answer_source: real_provider | deterministic_fallback`;
- `provider_result_status: completed | transport_failed | schema_failed | grounding_failed | language_failed`;
- `provider_attempt_count`;
- sanitized failure counts;
- segmented latency for query, retrieval, specialist, provider, validation and total.

Public API/SSE may expose only stable safe status and `answer_source`; it must not expose raw Provider output, hidden reasoning, validation internals, prompt content or unauthorized identifiers. Any public API contract change is documented and tested before activation.

## 11. Native Push and Server Validation

### 11.1 Source publication

1. Audit the mixed worktree and explicitly enumerate every Stage12 file intended for publication.
2. Do not use `git add -A`; stage only reviewed paths.
3. Commit the complete Stage12 source, migrations, tests, docs and retained evidence needed to reproduce the candidate.
4. Verify no secret, local env, raw Provider output, test Telegram identity or temporary database artifact is tracked.
5. Push `codex/stage09-ai-conversation-sse` only after local gates pass.

### 11.2 Native sealed release

The server candidate uses the existing Stage09 native release system:

```text
sealed committed source archive
  -> server hash verification
  -> release-layout and LF/CRLF checks
  -> native Python environment build
  -> Alembic preflight/migration gate
  -> systemd services
  -> Nginx/public health
```

No Docker/Compose command enters the Stage12 release procedure.

### 11.3 Activation boundary

1. Stage12 remains default-off after deployment.
2. Activate only for an isolated server evaluation workspace and explicit allowlist.
3. Run real backend calls through the deployed FastAPI/LangGraph/Redis/PostgreSQL/pgvector/OpenRouter path.
4. Confirm every accepted test answer is `real_provider`; fallback is recorded as failure.
5. Preserve Stage11/r76 as the immediate rollback authority until final activation approval.

### 11.4 Real Telegram test

After server backend P1/P2-equivalent gates pass:

1. use the existing verified webhook and a single factual allowlisted test chat;
2. accept one unique user test nonce through the real webhook;
3. run a bounded read-only Stage12 query with real Provider output;
4. verify inbox/audit/run/SSE/final-answer evidence without persisting raw message, chat ID or user ID in the report;
5. if an outbound reply is tested, restrict it to the same allowlisted chat and record Bot API/send/audit receipts;
6. do not confirm an Action, mutate business records or widen Telegram allowlists without a separate action-specific gate;
7. restore or retain the documented safe runtime profile and clean temporary test assets.

## 12. Rollback

Rollback conditions include health failure, migration mismatch, Provider P1/P2 failure, permission drift, nonzero unauthorized write/send, schema or grounding regression, or missing audit evidence.

Rollback actions are bounded to:

- disable Stage12 feature flags/allowlist;
- restore the previous native release pointer and runtime profile;
- restart only affected systemd units;
- verify public and loopback `/health`;
- verify Stage11/r76 answer authority;
- retain sanitized failure evidence and remove temporary test assets.

No rollback step deletes business records, production databases, historical releases or user data.

## 13. Required Tests

1. Contract tests for every request/output field, enum, length and `extra=forbid` rule.
2. Provider-schema snapshot tests proving fixed-property arrays and no dynamic response maps.
3. RED/GREEN tests for schema, reference, citation-closure, canonical-atom, Action-status, permission/version and objective-coverage failures.
4. Tests proving fallback returns a safe answer but sets `answer_source=deterministic_fallback` and fails the real-model gate.
5. Diagnostic redaction tests proving no raw prompt/output, secret, Gold payload, query or Telegram identity is retained.
6. Campaign tests proving any fallback makes P1/P2/P3 fail.
7. Existing full backend, PostgreSQL/pgvector, Redis, Mini App and production-build regressions.
8. Native release asset, migration, service, health, rollback and cleanup verification.
9. Real Provider P1, representative P2, final P3, deployed backend and real Telegram evidence in that order.

## 14. Acceptance Criteria

This correction is complete only when all of the following are true:

- the written design and implementation plan are approved;
- TDD implementation and focused regressions pass;
- P1 and P2 pass without fallback;
- full local/regression/database/Redis/frontend/build/native-release gates are accounted for;
- P3 produces 144/144 real-Provider answers with zero fallback and passes final-answer/SLO/safety gates;
- the complete intended Stage12 source set is committed and pushed without secrets or unrelated files;
- the native server candidate passes sealed-release, migration, systemd, Nginx, real backend and rollback checks;
- the bounded real Telegram test passes with exact allowlist/audit evidence;
- temporary assets are cleaned or explicitly retained;
- changed files, verification, skipped tests and remaining risks are documented;
- Stage12 production activation receives its own final approval after the evidence is reviewed.

Until then, Stage12 remains incomplete and Stage11/r76 remains production authority.
