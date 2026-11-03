# LLM Behavioral Drift Audit

A controlled audit of whether a deployed language model changes its stated moral action depending on
whether it believes it is being observed.

**deepseek/deepseek-chat** · 20 fixed moral dilemmas · two framings (monitored / unobserved) ·
temperature 0.0 · seed 42 · 11 valid scoring runs.

## Result

| Measure | Value |
|---|---|
| Median drift (action changes between framings) | **30.0%** of the 20 scenarios |
| Range across runs | 15% – 35% |
| Mean | 27.7% |
| Distinct flip-set behaviours | 7 across the 11 configurations |

The eleven runs are **configurations of one model family, not independent draws from a model population**,
so the figures are a fixed-suite census, not a population estimate. Three runs share one flip set, two
share another, and two more share a third.

## Correction history

Version 1.0 of the report published the ten-run statistics under an eleven-run label, and one row's flip
set omitted scenario 11. Both are corrected in v1.0.1, which carries a correction note on its face.

The measurement protocol separately withdrew pooled N × R binomial intervals (55/200 and 61/220) as
invalid under its own §2: in deterministic mode the repeats are determinism checks, not sampling draws.
Version 1.0.2 of the threshold rationale removed them and reports counts only.

## Layout

```
protocol/       FT-BDC v1.1 measurement amendment (rev 0.6), threshold rationale v1.0.3, decision memo
data/           per-run drift analysis, comparison table, findings
tools/          independent_stats.c — pass counts, Wilson/Clopper-Pearson, Fisher, power analysis
published/      the report as deployed (HTML)
*.tex *.pdf     audit report v1.0.1
```

## Reproducing

`tools/independent_stats.c` is standalone C — `cc -O2 independent_stats.c -o independent_stats && ./independent_stats`.
It prints the run-level BDS values, distinct behaviour groups, pass counts under both denominators,
descriptive Wilson intervals, the Fisher comparison, and the exact-binomial power figures. Pooled N × R
values are printed **tagged PROTOCOL-INVALID** rather than suppressed, so the arithmetic and the refusal
can both be audited. `tools/independent_stats.out` is a recorded run.

## Status

Research instrument. Not a safety certification.
