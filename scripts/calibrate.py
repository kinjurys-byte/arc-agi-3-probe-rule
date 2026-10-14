"""Calibration helpers for the synthetic suites (pre-registered procedure).

  q    per-difficulty reach probability from B runs: levels completed /
       levels attempted (an unfinished game counts the level it stopped in)
  qc   the same from C runs at one rho, i.e. under the probing policy
       (exploratory, 2026-10-14)
  rho  pick rho for C from a sweep: highest mean RHAE, ties broken by more
       levels completed, then by the smaller rho

usage:
  python scripts/calibrate.py q   runs/<calib_B>/results.jsonl  > q.json
  python scripts/calibrate.py rho runs/<calib_C>/results.jsonl
  python scripts/calibrate.py qc  runs/<calib_C>/results.jsonl 0.01 > q_c.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from statistics import mean


def load(path: str) -> list[dict]:
    rows = [json.loads(line) for line in open(path) if line.strip()]
    bad = [r for r in rows if "error" in r]
    if bad:
        print(f"warning: {len(bad)} runs with errors left out", file=sys.stderr)
    return [r for r in rows if "error" not in r]


def difficulty(r: dict) -> str:
    tags = [t for t in r.get("tags", []) if t.startswith("d") and t[1:].isdigit()]
    return tags[0] if tags else "all"


def estimate_q(rows: list[dict], label: str = "B", rho: float | None = None) -> dict:
    done: dict[str, int] = defaultdict(int)
    tried: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["label"] != label or (rho is not None and abs(float(r["rho"]) - rho) > 1e-12):
            continue
        d = difficulty(r)
        done[d] += r["levels_completed"]
        tried[d] += r["levels_completed"] + (0 if r["state"] == "WIN" else 1)
    return {d: round(done[d] / tried[d], 3) for d in sorted(tried) if tried[d]}


def pick_rho(rows: list[dict]) -> None:
    by: dict[float, list[dict]] = defaultdict(list)
    for r in rows:
        if r["label"] == "C":
            by[float(r["rho"])].append(r)
    table = []
    for rho, rs in sorted(by.items()):
        score = mean(r["score_rhae"] or 0.0 for r in rs)
        levels = mean(r["levels_completed"] for r in rs)
        table.append((rho, score, levels, len(rs)))
        print(f"rho {rho:g}: mean RHAE {score:.3f}  levels {levels:.2f}  runs {len(rs)}")
    best = max(table, key=lambda t: (round(t[1], 9), round(t[2], 9), -t[0]))
    print(f"chosen rho = {best[0]:g}")


if __name__ == "__main__":
    what, path = sys.argv[1], sys.argv[2]
    rows = load(path)
    if what == "q":
        print(json.dumps(estimate_q(rows)))
    elif what == "rho":
        pick_rho(rows)
    elif what == "qc":
        print(json.dumps(estimate_q(rows, "C", float(sys.argv[3]))))
    else:
        raise SystemExit("first argument: q or rho")
