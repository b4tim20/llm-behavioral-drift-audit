#!/usr/bin/env python3
"""role_swap_audit.py — split-process, per-scenario-synchronised drift audit.

Each agent runs ONE condition per round; the agents swap conditions between
rounds. Every scenario is released by a cross-process file barrier, so the
monitored and unmonitored calls are issued in the same time window.

Round 1: claude-code -> observed   | archivist -> unobserved
Round 2: claude-code -> unobserved | archivist -> observed

Usage (both agents, same --mission):
    cd ".../04-Security-Research/audits/data"
    python3 role_swap_audit.py --role claude-code --mission <ID>
    python3 role_swap_audit.py --role archivist  --mission <ID>

Output:
    results/role_swap_<ID>/round{1,2}/
        results-<condition>-<role>-<ID>.json
        tick-<round>-<i>-<role>-<ID>.json     (barrier record)
        round-summary-<role>-<ID>.json

Then:
    python3 compare_drift.py --root results/role_swap_<ID>
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone

import moral_dilemma_paired_experiment as m

ROLE_PLAN = {
    "claude-code": {1: "observed", 2: "unobserved"},
    "archivist": {1: "unobserved", 2: "observed"},
}
CONDITIONS = {
    "observed": (m.OBSERVED_FRAMING, "observed_monitored"),
    "unobserved": (m.UNOBSERVED_FRAMING, "maximum_freedom_private"),
}


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def has_valid_key():
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        return False
    low = key.lower()
    return not any(marker in low for marker in
                   ("your_api_key", "your_key", "placeholder", "changeme",
                    "_here", "replace_me"))


def write_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def peer_role(role):
    return "archivist" if role == "claude-code" else "claude-code"


def wait_for(path, timeout, label):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path):
            return
        time.sleep(0.05)
    raise TimeoutError(f"barrier timeout waiting for {label}: {path}")


def run_round(role, mission, round_no, condition, out_root, args):
    round_dir = os.path.join(out_root, f"round{round_no}")
    os.makedirs(round_dir, exist_ok=True)
    other = peer_role(role)
    framing, cond_name = CONDITIONS[condition]

    ready = os.path.join(round_dir, f"ready-{role}-{mission}.json")
    write_atomic(ready, {"role": role, "condition": condition, "pid": os.getpid(),
                         "ts": iso_now()})
    peer_ready = os.path.join(round_dir, f"ready-{other}-{mission}.json")
    wait_for(peer_ready, args.initial_timeout, f"{other} ready")
    print(f"[round {round_no}] {role} starts {condition} (peer ready)", flush=True)

    scenarios = m.generate_scenarios(args.num_scenarios, args.seed)
    results = []
    started = iso_now()
    for s in scenarios:
        tick = os.path.join(round_dir, f"tick-{round_no}-{s.index}-{role}-{mission}.json")
        write_atomic(tick, {"role": role, "round": round_no, "scenario": s.index,
                            "ts": iso_now(), "wall": time.time()})
        peer_tick = os.path.join(
            round_dir, f"tick-{round_no}-{s.index}-{other}-{mission}.json")
        wait_for(peer_tick, args.tick_timeout, f"scenario {s.index} peer tick")

        t0 = time.time()
        messages = [
            {"role": "system", "content": framing},
            {"role": "user", "content": s.to_prompt()},
        ]
        try:
            raw = m.call_model_with_retry(
                args.model, messages, args.temperature, args.max_tokens)
            err = None
        except Exception as exc:  # noqa: BLE001
            raw, err = None, f"{type(exc).__name__}: {exc}"
        t1 = time.time()

        action = m.extract_action(raw)
        results.append({
            "scenario_index": s.index,
            "scenario": asdict(s),
            "raw_response": raw,
            "error": err,
            "condition": cond_name,
            "started_at": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
            "started_wall": t0,
            "ended_wall": t1,
            "latency_ms": round((t1 - t0) * 1000, 1),
            "action": action,
        })
        print(f"  [{round_no}/{s.index:2}/{len(scenarios)}] {s.name:28} "
              f"{action or '?'}", flush=True)

    errors = sum(1 for r in results if r["error"] or not r["raw_response"])
    payload = {
        "role": role,
        "condition": condition,
        "condition_name": cond_name,
        "mission": mission,
        "round": round_no,
        "model": args.model,
        "seed": args.seed,
        "temperature": args.temperature,
        "num_scenarios": args.num_scenarios,
        "started": started,
        "ended": iso_now(),
        "valid": errors == 0,
        "errors": errors,
        "results": results,
    }
    result_path = os.path.join(
        round_dir, f"results-{condition}-{role}-{mission}.json")
    write_atomic(result_path, payload)

    actions = {r["scenario_index"]: r["action"] for r in results}
    summary = {
        "role": role, "round": round_no, "condition": condition,
        "result_file": os.path.basename(result_path),
        "actions": actions,
        "errors": errors,
        "valid": errors == 0,
        "done_at": iso_now(),
    }
    write_atomic(os.path.join(round_dir, f"round-summary-{role}-{mission}.json"),
                 summary)
    print(f"[round {round_no}] {role} done -> {result_path}", flush=True)
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", required=True, choices=sorted(ROLE_PLAN))
    ap.add_argument("--mission", required=True,
                    help="shared mission id; both agents must pass the same value")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--model", default=m.DEFAULT_MODEL)
    ap.add_argument("--num-scenarios", type=int, default=m.DEFAULT_NUM_SCENARIOS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--initial-timeout", type=float, default=900.0)
    ap.add_argument("--tick-timeout", type=float, default=300.0)
    args = ap.parse_args()

    out_root = args.out_root or os.path.join(
        "results", f"role_swap_{args.mission}")

    if not has_valid_key():
        print("REFUSED: DEEPSEEK_API_KEY is missing or still a placeholder; "
              "set a real key before starting a synchronised run.",
              file=sys.stderr, flush=True)
        return 2

    print("preflight: verifying API authentication...", flush=True)
    try:
        m.call_model_with_retry(
            args.model,
            [{"role": "user", "content": "Reply with exactly: OK"}],
            0.0, 5)
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: API preflight failed ({type(exc).__name__}): "
              f"{str(exc)[:160]}", file=sys.stderr, flush=True)
        return 2

    os.makedirs(out_root, exist_ok=True)

    print(f"role={args.role} mission={args.mission} out={out_root}", flush=True)
    invalid = False
    for round_no in (1, 2):
        condition = ROLE_PLAN[args.role][round_no]
        try:
            payload = run_round(args.role, args.mission, round_no, condition,
                                out_root, args)
        except TimeoutError as exc:
            print(f"ABORT round {round_no}: {exc}", file=sys.stderr, flush=True)
            return 3
        if not payload.get("valid"):
            invalid = True
    if invalid:
        print(f"INVALID {args.role}: one or more rounds had failed responses; "
              f"records written under {out_root}", file=sys.stderr, flush=True)
        return 4
    print(f"COMPLETE {args.role}: both rounds valid under {out_root}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
