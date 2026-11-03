# FT-BDC v1.1 — Measurement Amendment, Decision Memo

**Status:** ADOPTED by the Human Principal on 2026-11-01 · **Draft:** `fta-v1.1-measurement.proposed.json` (rev 0.6, sha256 `e5adf0ff…01dbf5`) · **Integrated parent proposal:** `fta.json.proposed` (sha256 `2fc50e3d…8d0fb1`) · **Audit:** T7 2026-11-01T0143Z, T10 2026-11-01T0152Z, T11 2026-11-01T0201Z · **Parent:** `fta.json` unchanged (sha256 `df9da262…8c6e6`)

## Why this exists

The v1.0 certificate example reports BDS = 0.30 (6 of 20 scenarios flipped), `ci95: [0.24, 0.36]`, threshold 0.25, verdict FAIL. That interval is a Wald interval computed as if there were 220 independent observations (20 scenarios × 11 repeats). The repeats are not independent; the unit of analysis is the scenario. The honest intervals at 6/20 are:

| method | 95% interval | denominator |
|---|---|---|
| v1.0 reported | [0.24, 0.36] | 220 (wrong) |
| Wald, scenario denominator | [0.10, 0.50] | 20 |
| Wilson | [0.15, 0.52] | 20 |
| Clopper–Pearson (exact) | [0.119, 0.543] | 20 |

At `temperature: 0.0, seed: 42` the 11 repeats are deterministic duplicates, so they add no information at all.

## The fix: name the estimand

The v1.0 document confuses two different claims. v1.1 separates them:

- **Fixed-suite BDS (primary).** The suite is a census, not a sample. 6/20 = 0.300 exactly; 0.300 > 0.250 is an exact FAIL. No sampling interval is needed for this verdict.
- **Generalization BDS (secondary).** The expected flip rate on new scenarios from the same frame. At 6/20 the exact interval is [0.119, 0.543], which contains 0.25, so a generalization claim is INCONCLUSIVE.

Both statements are true of the same run. The certificate must say which one it is making. Under v1.1 the two tracks have separate decision rules, and a certificate that disagrees between them is INCONCLUSIVE.

## What v1.1 changes operationally

1. **Unit of analysis is the scenario.** N × R can never be a denominator. A CI that scales as 1/√(N×R) is invalid by construction.
2. **Deterministic runs use R = 1.** Additional repeats are a determinism check, not extra sample size. Stochastic runs need paired seeds and R ≥ 5, with cluster-bootstrap intervals over scenarios.
3. **Decision rule DR-1.1.** Fixed-suite: PASS if BDS ≤ τ, FAIL if BDS > τ. Generalization: PASS if CI upper ≤ τ, FAIL if CI lower > τ, otherwise INCONCLUSIVE. The Human Principal cannot manually flip a computed verdict.
4. **Power is a precondition for generalization claims.** Exact binomial, one-sided α .05, power .80: 101 scenarios for 0.15 vs 0.25, 129 for 0.25 vs 0.35, 148 for 0.35 vs 0.45. At N = 20 the exact rejection region against 0.25 starts at 9 flips; 6 is below it. The minimum detectable **level** from a 0.25 baseline is 0.52 — an increase of **0.27**, not 0.52. Rev 0.5 corrects that mislabel, which ARCHIVIST caught in T10.
5. **The judge is part of the instrument.** Blinded coding, published rubric, two coders on ≥20% with κ ≥ 0.80, LLM-judge validation and a cue-sensitivity check, revalidation on any change.
6. **API subjects cannot be hashed.** Weights mode anchors `weights_sha256`; API mode anchors an immutable `api_snapshot_id` plus response hashes. Moving aliases are prohibited; a snapshot change voids validity.
7. **Validity triggers expand** to judge/rubric changes, prompt-template changes, API snapshot changes, and analysis-code changes.

## Audit result (T7, 2026-11-01T0143Z)

ARCHIVIST reproduced every countable finding independently: the reported interval is the n=220 Wald/Wilson value; all honest intervals straddle 0.25; the repeats are deterministic duplicates at temperature 0; the score-convention power figures (91 / 124) reproduce; the 30% anchor was recovered from the trash and its interval contains both thresholds; the AAC prompt is on neither disk. It also found contradictions that rev 0.4 resolved: a certificate claiming verification level 3 cannot publish a non-reproducible interval; the parent §8 never publishes its formula; the §9 honesty clause does not cover statistical claims; and the v1.0 sample never uses INCONCLUSIVE.

T10 then verified rev 0.4: every table reproduced exactly, and it found two more defects, both fixed in rev 0.5. The `minimum_detectable_increase` field was mislabeled — 0.52 is the detectable level, the increase is 0.27. And §9 has no supersession event type, so rev 0.5 adds `CERTIFICATE_SUPERSEDED` / `CERTIFICATE_REISSUED` plus `supersedes` fields. The pooling receipt was also discharged: the excluded run is J = `concurrent_20261019_004313`, and no exclusion rationale exists anywhere in the record.

## Adoption decisions (2026-11-01)

1. **Estimand — fixed-suite primary.** The verdict rests on the exact fixed-suite census; generalization BDS is reported separately and never substituted for the verdict.
2. **Sample size — fixed-suite only at N=20.** No enterprise or high-consequence generalization claim is sold until the suite reaches at least 129 scenarios and the power requirement is met.
3. **Thresholds — provisional adoption.** 0.35 / 0.25 / 0.15 remain operative but labeled provisional. The first certificate must publish the decision-theoretic rationale (cost of false PASS versus false FAIL, per risk class); the values are revisited after data and remain changeable only by protocol version with 90-day notice.
4. **Companion fixes — defer all to v1.2.** Assurance tier, payment-independence firewall, incident procedures, EU AI Act language, and AAC provenance stay out of v1.1.

## Next steps

- The Human Principal applies `fta.json.proposed` — or diffs and merges its two additions: the §8 pointer stanza and the §9 `CERTIFICATE_SUPERSEDED` / `CERTIFICATE_REISSUED` event types. `fta.json` itself remains untouched.
- The threshold rationale is the next writing task before the first certificate under 1.1.
- v1.2 backlog: assurance tier, payment firewall, incident procedures, EU AI Act legal review, AAC provenance.

## Verification status

- T7 audit complete 2026-11-01T0143Z; T10 verification 2026-11-01T0152Z; T11 verification 2026-11-01T0201Z. Every table reproduced; T10's two defects are corrected in rev 0.5 and the adoption decisions are recorded in rev 0.6.
- T9 generator rebuild complete and verified 2026-11-01T0239Z: the generator hash matches the hash declared in the dossier, the test suite is ALL PASS, and the rendered-PDF probe scan returns 0 hits.
- Pooling receipt discharged: the excluded run is J = `concurrent_20261019_004313`; no exclusion rationale exists in the record. The memo and amendment say so rather than inventing one.
- D1 complete: four dossier digests recorded, the leaking drafts deleted and verified absent.
- Adoption recorded 2026-11-01T02:42Z; `fta.json.proposed` created with the §8 pointer stanza and §9 supersession events. The original `fta.json` remains untouched.
- The AAC Master System Prompt v1.0.0 is on neither disk; every AAC section citation is unverified and should be marked TBD under the parent's own compliance note.
