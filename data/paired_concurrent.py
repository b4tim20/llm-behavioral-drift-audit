#!/usr/bin/env python3
"""paired_concurrent.py — run OBSERVED (monitored) and UNOBSERVED conditions
simultaneously, one pair at a time, so every monitored/unmonitored pair is
issued inside the same time window.

This removes the time-ordering confound of the original sequential runner
(phase 1 all monitored, then phase 2 all unmonitored).

Reuses moral_dilemma_paired_experiment for framings, scenarios, retries, scoring.
"""
import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone

import moral_dilemma_paired_experiment as m


def one(model, framing, prompt, temperature, max_tokens):
    t0 = time.time()
    try:
        raw = m.call_model_with_retry(
            model,
            [{"role": "system", "content": framing}, {"role": "user", "content": prompt}],
            temperature, max_tokens)
        err = None
    except Exception as e:
        raw, err = None, f"{type(e).__name__}: {e}"
    return raw, err, t0, time.time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=m.DEFAULT_MODEL)
    ap.add_argument("--num-scenarios", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--out", default=None)
    ap.add_argument("--swap", action="store_true",
                    help="issue UNOBSERVED first, OBSERVED second (swap role slots)")
    a = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = a.out or os.path.join("results", f"concurrent_{stamp}")
    os.makedirs(out, exist_ok=True)

    scen = m.generate_scenarios(a.num_scenarios, a.seed)
    obs, uno, pairs = [], [], []
    started = datetime.now(timezone.utc).isoformat()

    with ThreadPoolExecutor(max_workers=2) as ex:
        for s in scen:
            prompt = s.to_prompt()
            jobs = [(m.OBSERVED_FRAMING, "obs"), (m.UNOBSERVED_FRAMING, "unobs")]
            if a.swap:
                jobs.reverse()  # unobserved gets the primary slot
            futs = {tag: ex.submit(one, a.model, fr, prompt, a.temperature, a.max_tokens)
                    for fr, tag in jobs}
            ro, ru = futs["obs"].result(), futs["unobs"].result()

            obs.append({"scenario_index": s.index, "scenario": asdict(s),
                        "raw_response": ro[0], "error": ro[1], "condition": "observed_monitored"})
            uno.append({"scenario_index": s.index, "scenario": asdict(s),
                        "raw_response": ru[0], "error": ru[1], "condition": "maximum_freedom_private"})

            skew_ms = abs(ro[2] - ru[2]) * 1000.0
            pairs.append({"i": s.index, "name": s.name, "start_skew_ms": round(skew_ms, 1),
                          "obs_ms": round((ro[3] - ro[2]) * 1000.0),
                          "unobs_ms": round((ru[3] - ru[2]) * 1000.0)})
            ao, au = m.extract_action(ro[0]), m.extract_action(ru[0])
            print(f"[{s.index:2}/{len(scen)}] {s.name:28} skew={skew_ms:6.0f}ms "
                  f"obs={ao or '?'} unobs={au or '?'}", flush=True)

    drift = m.compute_drift(obs, uno)
    ended = datetime.now(timezone.utc).isoformat()

    meta = {
        "method": "paired_concurrent", "model": a.model, "seed": a.seed,
        "temperature": a.temperature, "scenarios": len(scen), "swapped_roles": bool(a.swap),
        "started": started, "ended": ended,
        "skew_ms": {
            "mean": round(statistics.mean(p["start_skew_ms"] for p in pairs), 1),
            "max": round(max(p["start_skew_ms"] for p in pairs), 1),
        },
        "pairs": pairs,
        "note": "both conditions issued in parallel per scenario; no phase ordering",
    }

    for name, obj in (("observed_results.json", {"model": a.model, "condition": "observed_monitored",
                                                "framing": m.OBSERVED_FRAMING, "results": obs}),
                      ("unobserved_results.json", {"model": a.model, "condition": "maximum_freedom_private",
                                                  "framing": m.UNOBSERVED_FRAMING, "results": uno}),
                      ("drift_analysis.json", drift),
                      ("meta.json", meta)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)

    print(f"\nOUT {out}")
    print(f"drift {drift['action_changes']}/{drift['total_scenarios']} "
          f"= {drift['action_change_rate'] * 100:.1f}%")
    print(f"pair start skew: mean {meta['skew_ms']['mean']}ms  max {meta['skew_ms']['max']}ms")


if __name__ == "__main__":
    main()
