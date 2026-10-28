"""Exploratory diagnosis for the short-first-level suite (not registered).

In the pocket arm (d2), always probing (CA) tries every untried action of
unknown effect first, including moves that the pocket's walls block. A simple
action that has not changed the frame in its first k_simple = 4 tries is
classed as a no-op (README, Known issues), and the table carries over to the
next levels. This script reads the step logs of a rerun of d2 with step logs
(runs/syn_short_diag) and reports, per configuration:

- runs in which some move (ACTION1-4) was classed as a no-op at the end of
  level 1, and in which some move was still a no-op when the run ended;
- levels completed with and without such a move;
- that the rerun's result rows equal the stored rows of runs/syn_short_confirm.

usage: python scripts/diagnose_short_moves.py [runs/syn_short_diag] [runs/syn_short_confirm/results.jsonl]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
MOVES = ("a1", "a2", "a3", "a4")
IGNORE = {"seconds"}


def classes(rows: list[dict], level: int | None) -> dict:
    """Last recorded class of each action type, up to the end of a level."""
    out = {}
    for r in rows:
        if "lvl" not in r:
            continue
        if level is not None and r["lvl"] > level:
            break
        if r.get("key"):
            out[r["key"]] = r["cls"]
    return out


def main(diag: Path, stored: Path) -> None:
    rows = [json.loads(x) for x in open(diag / "results.jsonl") if x.strip()]
    ref = {}
    for x in open(stored):
        if x.strip():
            r = json.loads(x)
            ref[(r["game"], r["label"], r["seed"])] = r
    same = sum(1 for r in rows
               if all(r[k] == ref[(r["game"], r["label"], r["seed"])][k] for k in r if k not in IGNORE))
    print(f"rerun rows equal to the stored rows (all fields but timing): {same} of {len(rows)}")

    by_cfg = defaultdict(list)
    for r in rows:
        folder = "C_rho" + format(r["rho"], "g") if r["label"] == "C" else r["label"]
        log = diag / "logs" / folder / f"{r['game']}_{r['label']}_s{r['seed']}.jsonl"
        steps = [json.loads(x) for x in open(log) if x.strip()]
        end1 = classes(steps, 1)
        end = classes(steps, None)
        noop1 = sorted(m for m in MOVES if end1.get(m) == "noop")
        noop_end = sorted(m for m in MOVES if end.get(m) == "noop")
        by_cfg[r["label"]].append((r, noop1, noop_end))
    for c, items in sorted(by_cfg.items()):
        with1 = [r for r, n1, _ in items if n1]
        without1 = [r for r, n1, _ in items if not n1]
        still = [r for r, _, ne in items if ne]
        print(f"{c}: {len(items)} runs; some move a no-op at the end of level 1 in {len(with1)}, "
              f"still a no-op at the end of the run in {len(still)}")
        if with1:
            print(f"   levels completed: {mean(r['levels_completed'] for r in with1):.2f} with such a move, "
                  + (f"{mean(r['levels_completed'] for r in without1):.2f} without" if without1 else "no run without"))
        if still:
            print(f"   levels completed when a move stayed a no-op: {mean(r['levels_completed'] for r in still):.2f}")


if __name__ == "__main__":
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "runs" / "syn_short_diag"
    s = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "runs" / "syn_short_confirm" / "results.jsonl"
    main(d, s)
