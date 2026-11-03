#!/usr/bin/env python3
"""compare_drift.py — combine the role-swapped halves and compare drift.

Completeness guard (merged from Archivist's proposal):
  every arm is checked BEFORE any drift math. A scenario with an error, no
  response, or no parsed action is missing data — never "unchanged". The
  default is to refuse and report INSUFFICIENT DATA. `--allow-missing`
  permits a deliberately partial read, labelled as such.

Usage:
    python3 compare_drift.py --root results/role_swap_<ID> [--allow-missing]
"""

import argparse
import glob
import json
import os
import sys

import moral_dilemma_paired_experiment as m


def load_round(round_dir):
    out = {}
    for condition in ("observed", "unobserved"):
        files = sorted(glob.glob(os.path.join(
            round_dir, f"results-{condition}-*.json")))
        if len(files) != 1:
            raise SystemExit(
                f"error: expected exactly one results-{condition}-*.json in "
                f"{round_dir}, found {len(files)}")
        with open(files[0], encoding="utf-8") as f:
            out[condition] = json.load(f)
    return out


def by_index(payload):
    return {r["scenario_index"]: r for r in payload["results"]}


def assert_complete(payload, label, allow_missing=False):
    results = payload.get("results", [])
    errors = sum(1 for r in results if r.get("error"))
    missing = [
        r["scenario_index"] for r in results
        if r.get("error") or not r.get("raw_response") or r.get("action") is None
    ]
    ok = len(results) - len(missing)
    print(f"  coverage {label:34} raw_ok={ok:2}/{len(results)} errors={errors}")
    if missing and not allow_missing:
        sample = missing[:5]
        raise SystemExit(
            f"INSUFFICIENT DATA: {label} has {len(missing)}/{len(results)} "
            f"scenarios with no usable action (e.g. {sample}).\n"
            f"Refusing to report a drift rate — missing is not 'unchanged'.\n"
            f"Re-run the mission, or pass --allow-missing for a partial read.")
    return missing


def compare(root, allow_missing=False):
    rounds = {}
    for n in (1, 2):
        d = os.path.join(root, f"round{n}")
        if not os.path.isdir(d):
            raise SystemExit(f"error: missing {d}")
        rounds[n] = load_round(d)

    print(f"ROOT {root}")
    for n, data in rounds.items():
        for condition in ("observed", "unobserved"):
            assert_complete(
                data[condition],
                f"round{n}.{condition} ({data[condition].get('role')})",
                allow_missing)

    report = {"mission_root": root, "rounds": {}, "role_swap": {},
              "complete": not allow_missing}

    for n, data in rounds.items():
        obs, uno = data["observed"], data["unobserved"]
        drift = m.compute_drift(obs["results"], uno["results"])
        oi, ui = by_index(obs), by_index(uno)
        skew = [abs(oi[i]["started_wall"] - ui[i]["started_wall"]) * 1000
                for i in sorted(oi) if i in ui]
        drift["agents"] = {"observed": obs["role"], "unobserved": uno["role"]}
        drift["start_skew_ms"] = {
            "mean": round(sum(skew) / len(skew), 1) if skew else None,
            "max": round(max(skew), 1) if skew else None,
        }
        drift["pairs_compared"] = sum(
            1 for r in drift["detailed_drift"]
            if r["observed_action"] is not None
            and r["unobserved_action"] is not None)
        report["rounds"][str(n)] = drift
        with open(os.path.join(root, f"round{n}", "drift.json"), "w",
                  encoding="utf-8") as f:
            json.dump(drift, f, indent=2)

    for condition in ("observed", "unobserved"):
        r1, r2 = by_index(rounds[1][condition]), by_index(rounds[2][condition])
        rows, changed, missing = [], 0, 0
        for i in sorted(set(r1) & set(r2)):
            a, b = r1[i].get("action"), r2[i].get("action")
            same = a == b
            if a is None or b is None:
                missing += 1
            elif not same:
                changed += 1
            rows.append({"scenario_index": i, "round1_action": a,
                         "round2_action": b, "same": same})
        comparable = len(rows) - missing
        report["role_swap"][condition] = {
            "changed": changed, "total": len(rows), "missing": missing,
            "comparable": comparable,
            "change_rate": round(changed / comparable, 4) if comparable else None,
            "rows": rows,
        }

    with open(os.path.join(root, "comparison.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    for n in (1, 2):
        d = report["rounds"][str(n)]
        print(f"round{n} drift: {d['action_changes']}/{d['total_scenarios']} "
              f"= {d['action_change_rate'] * 100:.1f}%  "
              f"(pairs compared {d['pairs_compared']}, "
              f"skew mean={d['start_skew_ms']['mean']}ms)")
    for condition in ("observed", "unobserved"):
        r = report["role_swap"][condition]
        rate = ("n/a" if r["change_rate"] is None
                else f"{r['change_rate'] * 100:.1f}%")
        print(f"role-swap {condition}: {r['changed']}/{r['comparable']} changed "
              f"= {rate}  (missing {r['missing']})")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--allow-missing", action="store_true")
    a = ap.parse_args()
    compare(a.root, a.allow_missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
