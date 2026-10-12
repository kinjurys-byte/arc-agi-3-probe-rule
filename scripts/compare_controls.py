"""Compare configurations with the trivial-policy controls R and K.

Reads one or more results.jsonl files (for example the main run and a
separate run of the controls on the same games and seeds) and prints, per
configuration, the mean RHAE and levels completed, the games in which a
control completed at least one level, and per-game sign tests of every
configuration against each control.

usage: python scripts/compare_controls.py runs/<main>/results.jsonl runs/<controls>/results.jsonl
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from statistics import mean

ORDER = ["A", "B", "C", "C1", "CU", "R", "K"]


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n if n else 1.0


def main(paths: list[str]) -> None:
    rows = []
    for p in paths:
        rows += [json.loads(x) for x in open(p) if x.strip()]
    rows = [r for r in rows if "error" not in r]
    by = defaultdict(list)
    for r in rows:
        label = r.get("label") or r.get("config")
        by[(r["game"], "CU" if label in ("C'", "CP") else label)].append(r)
    games = sorted({g for g, _ in by})
    labels = [c for c in ORDER if any((g, c) in by for g in games)]
    score = {(g, c): mean(x["score_rhae"] or 0.0 for x in by[(g, c)]) for g in games for c in labels if (g, c) in by}
    levels = {(g, c): mean(x["levels_completed"] for x in by[(g, c)]) for g in games for c in labels if (g, c) in by}

    print("config  mean RHAE (%)  levels/run  runs")
    for c in labels:
        rs = [x for g in games for x in by.get((g, c), [])]
        print(f"  {c:3}   {mean(x['score_rhae'] or 0 for x in rs):10.3f}  {mean(x['levels_completed'] for x in rs):10.2f}  {len(rs):4d}")

    for k in ("R", "K"):
        if k not in labels:
            continue
        solved = [g for g in games if levels.get((g, k), 0) > 0]
        print(f"\ngames where control {k} completed a level: {len(solved)} of {len(games)} {solved}")
        for c in labels:
            if c in ("R", "K"):
                continue
            pairs = [g for g in games if (g, c) in score and (g, k) in score]
            w = sum(1 for g in pairs if score[(g, c)] > score[(g, k)])
            lo = sum(1 for g in pairs if score[(g, c)] < score[(g, k)])
            lw = sum(1 for g in pairs if levels[(g, c)] > levels[(g, k)])
            ll = sum(1 for g in pairs if levels[(g, c)] < levels[(g, k)])
            print(f"  {c:3} vs {k}: RHAE higher in {w}, lower in {lo}, tied {len(pairs) - w - lo} "
                  f"(sign test p = {sign_test(w, lo):.4f}); levels higher in {lw}, lower in {ll}")


if __name__ == "__main__":
    main(sys.argv[1:])
