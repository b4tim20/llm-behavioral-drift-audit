#!/usr/bin/env python3
"""compare_missions.py — compare two role_swap mission roots.

Typical use: mission A ran under one key, mission B under another. Compares,
per round and per condition, the same agent arm across missions:
  - claude-code arm: changes when the key is rotated
  - archivist arm:   same key both missions -> reproducibility control

Reports per-round drift for both missions and per-arm agreement/flips.

Usage:
    python3 compare_missions.py \
        --a results/role_swap_M20261019_0035 \
        --b results/role_swap_M20261019_0044 \
        [--label-a old-key --label-b new-key]
"""

import argparse
import glob
import json
import os
import sys

import moral_dilemma_paired_experiment as m


def load_arm(root, round_no, condition):
    files = sorted(glob.glob(os.path.join(
        root, f"round{round_no}", f"results-{condition}-*.json")))
    if len(files) != 1:
        raise SystemExit(
            f"error: expected one results-{condition}-*.json under "
            f"{root}/round{round_no}, found {len(files)}")
    with open(files[0], encoding="utf-8") as f:
        payload = json.load(f)
    bad = [r for r in payload["results"]
           if r.get("error") or not r.get("raw_response") or r.get("action") is None]
    if bad:
        raise SystemExit(
            f"INSUFFICIENT DATA: {files[0]} has {len(bad)}/"
            f"{len(payload['results'])} unusable scenarios; refusing to compare")
    return payload


def by_index(payload):
    return {r["scenario_index"]: r for r in payload["results"]}


def arm_diff(a_payload, b_payload):
    x, y = by_index(a_payload), by_index(b_payload)
    rows, changed, missing = [], [], 0
    for i in sorted(set(x) & set(y)):
        ax, ay = x[i].get("action"), y[i].get("action")
        if ax is None or ay is None:
            missing += 1
            rows.append({"i": i, "a": ax, "b": ay, "same": None})
            continue
        same = ax == ay
        if not same:
            changed.append((i, ax, ay))
        rows.append({"i": i, "a": ax, "b": ay, "same": same})
    comparable = len(rows) - missing
    return {
        "comparable": comparable, "missing": missing, "changed": len(changed),
        "change_rate": (len(changed) / comparable) if comparable else None,
        "flips": changed, "rows": rows,
        "role_a": a_payload.get("role"), "role_b": b_payload.get("role"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    args = ap.parse_args()

    report = {"a": {"root": args.a, "label": args.label_a},
              "b": {"root": args.b, "label": args.label_b},
              "rounds": {}, "arms": {}}

    for round_no in (1, 2):
        arms = {}
        for tag, root in (("a", args.a), ("b", args.b)):
            arms[tag] = {c: load_arm(root, round_no, c)
                         for c in ("observed", "unobserved")}
            drift = m.compute_drift(arms[tag]["observed"]["results"],
                                    arms[tag]["unobserved"]["results"])
            report["rounds"].setdefault(str(round_no), {})[tag] = {
                "drift": drift["action_changes"],
                "total": drift["total_scenarios"],
                "rate": drift["action_change_rate"],
                "agents": {"observed": arms[tag]["observed"]["role"],
                           "unobserved": arms[tag]["unobserved"]["role"]},
            }
        for condition in ("observed", "unobserved"):
            diff = arm_diff(arms["a"][condition], arms["b"][condition])
            key = f"round{round_no}.{condition}"
            report["arms"][key] = diff
            rate = ("n/a" if diff["change_rate"] is None
                    else f"{diff['change_rate'] * 100:.1f}%")
            print(f"{key}: {diff['role_a']} vs {diff['role_b']} | "
                  f"{diff['changed']}/{diff['comparable']} actions changed "
                  f"= {rate} | missing {diff['missing']}")
            if diff["flips"]:
                print("  flips: " + ", ".join(
                    f"#{i} {a}->{b}" for i, a, b in diff["flips"]))

    for round_no in (1, 2):
        for tag in ("a", "b"):
            d = report["rounds"][str(round_no)][tag]
            label = args.label_a if tag == "a" else args.label_b
            print(f"round{round_no} drift [{label}]: "
                  f"{d['drift']}/{d['total']} = {d['rate'] * 100:.1f}%  "
                  f"(obs={d['agents']['observed']}, "
                  f"unobs={d['agents']['unobserved']})")

    out = os.path.join(args.b, "cross_mission_comparison.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"OUT {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
