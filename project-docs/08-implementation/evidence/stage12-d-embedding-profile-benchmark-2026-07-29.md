# Stage12-D Embedding Profile Focused Benchmark Evidence

## Status

- Date: 2026-07-29
- Status: selected profile accepted by user; local comparison remains unmeasured
- Scope: 12-case focused synthetic retrieval corpus only
- Corpus hash: `2bf17382489af5ba99aa6ae110361e62e62eeef14cefae6698649235ad4c3653`
- Production effect: none

## Fixed execution boundary

- 27 authorized candidates, 12 queries, `Top K = 20`.
- One untimed warm-up followed by three measured rounds.
- Remote timeout is 20 seconds per request.
- Only synthetic fixture text was sent.
- Every OpenRouter request used `data_collection=deny`, `zdr=true` and `allow_fallbacks=false`.
- Provider catalog revisions were checked before POST; credentials, raw inputs and vectors were not persisted in evidence.

## Measured results

| Profile | Revision | Completed | Recall@20 | MRR@20 | P95 | Forbidden | Cost including warm-up | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| OpenRouter BGE-M3 | `baai/bge-m3-20251117` | 3/3 | 1.0000 | 0.9583 | 3.93 s | 0 | $0.0000474 | pass |
| OpenRouter multilingual-E5-large | `intfloat/multilingual-e5-large-20251117` | 0/3 | n/a | n/a | n/a | 0 | $0 | fail: warm-up exceeded 20 s |
| Local BGE-M3 CPU | `5617a9f61b028005a4858fdac845db406aefb181` | 0/3 | n/a | n/a | n/a | n/a | $0 | incomplete: weight unavailable |

The E5 route was also observed diagnostically with a relaxed 60-second timeout before the fixed run: it completed three rounds at Recall@20/MRR@20 `1.0/1.0`, but averaged about 54 seconds per round. That observation is not decision evidence because it violates the frozen 20-second boundary.

## Local candidate blocker

- Host budget was sufficient: 31.61 GB RAM and 216.79 GB free on C:.
- A temporary CPU runtime passed import checks with `torch 2.4.1`, `sentence-transformers 5.6.1` and `transformers 4.48.3`.
- The pinned BGE-M3 weight is 2,271,145,830 bytes.
- Config and tokenizer files reached the task cache, but the weight transfer stopped making progress. The download was terminated rather than claiming a local result.
- No production dependency was added. The partial cache remains in the explicit task temp directory for resumable follow-up and is not evidence of a completed benchmark.

## Decision state

Hard gates run before weighted scoring. E5 is eliminated by failed rounds, and local BGE-M3 is ineligible because it was not measured. OpenRouter BGE-M3 is therefore the only currently eligible profile, so it is the proposed profile:

```text
profile_name       = stage12.openrouter-bge-m3-v1
model_revision     = baai/bge-m3-20251117
dimension          = 1024
normalization      = l2
distance_metric    = cosine
max_input_tokens   = 8192
batch_size         = 64
provider_location  = remote
data_residency     = OpenRouter deny + ZDR; real workspace data still not authorized
```

The user explicitly accepted this profile/schema boundary on 2026-07-29. Migration `0035`, models and default-off provider configuration may now be implemented. Deployment, production activation and sending real workspace data to OpenRouter remain prohibited until their separate gates are approved.

Machine-readable evidence: [stage12-d-embedding-profile-benchmark-2026-07-29.json](stage12-d-embedding-profile-benchmark-2026-07-29.json)
