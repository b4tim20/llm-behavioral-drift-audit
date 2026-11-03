# INVALID RUN — role_swap M20261018_2340

**Status: INVALID — no usable drift result. Do not cite the 0% figures.**

## Why

1. The `claude-code` process used an invalid API key
   (`Authentication Fails ... Your api key: ****here is invalid`) on every
   call in round 1 `observed`, and all of round 2.
2. Partway through the run, the API became unreachable
   (`Temporary failure in name resolution`), so even calls with a working key
   failed.
3. Result: **0 complete observed/unobserved pairs** in either round.

## Response counts

| File | Role | Condition | Valid | Errored |
|---|---|---|---|---|
| `round1/results-observed-claude-code-*.json` | claude-code | observed | 0 | 20 |
| `round1/results-unobserved-archivist-*.json` | archivist | unobserved | 10 | 10 |
| `round2/results-observed-archivist-*.json` | archivist | observed | 0 | 20 |
| `round2/results-unobserved-claude-code-*.json` | claude-code | unobserved | 0 | 20 |

The 10 valid `unobserved` responses are preserved in the record but cannot
form a paired drift arm without their `observed` counterparts.

## Why `comparison.json` says 0.0%

`compute_drift` treats a missing action (`None`) as "no change". With every
observed action null, both rounds score 0/20. That is an artifact of missing
data, not a measurement. `compare_drift.py` now refuses to score an arm with
any errored or empty response for exactly this reason.

## What was valid

The cross-process barrier worked: round 1 mean start skew was about 30 ms and
round 2 about 26 ms. The failure is credentials/network, not synchronisation.

## To rerun

Set a working `DEEPSEEK_API_KEY`, then run a new mission id. The harness now
performs an authentication preflight before any synchronised work begins and
aborts if the key is rejected.
