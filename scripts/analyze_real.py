"""Registered analysis of the real-game test (2026-10-22): B, C and CA on the
25 public ARC-AGI-3 games, compared game by game.

Per game, each configuration is summarized by the mean over seeds of
(i) levels completed and (ii) RHAE (percent). Tests are one-sided sign tests
over games, ties dropped; a test passes when the first configuration is above
the second in at least 60% of the untied games and p < 0.05.

R1  CA completes more levels than B     (primary)
R2  C completes more levels than B      (primary)
R3  CA has a higher RHAE than B         (secondary)
R4  C has a higher RHAE than B          (secondary)
R5  over game-seed pairs whose levels differ, CA completes more levels than
    B more often than fewer (one-sided sign test over pairs, p < 0.05;
    pairs of one game are not independent)                    (secondary)
R6  the same for C against B                                   (secondary)

Also printed (descriptive): C against CA on both measures, the same tests on
the held-out and design games separately (splits.json), total levels
completed and mean RHAE per configuration, and the number of game-seed pairs
in which one configuration completed more levels than the other.

usage: python scripts/analyze_real.py runs/<dir>/results.jsonl [more results.jsonl ...]
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ("B", "C", "CA")


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def compare(per_game: dict, x: str, y: str, games: list[str]) -> tuple[int, int, int, float]:
    gs = [g for g in games if (g, x) in per_game and (g, y) in per_game]
    w = sum(1 for g in gs if per_game[(g, x)] > per_game[(g, y)])
    lo = sum(1 for g in gs if per_game[(g, x)] < per_game[(g, y)])
    return w, lo, len(gs) - w - lo, sign_test(w, lo)


def verdict(w: int, lo: int, p: float) -> str:
    return "PASS" if w + lo and w / (w + lo) >= 0.6 and p < 0.05 else "FAIL"


def main(paths: list[str]) -> None:
    rows = []
    for path in paths:
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                if "error" not in r and r.get("label") in CONFIGS:
                    rows.append(r)
    by = defaultdict(list)
    for r in rows:
        by[(r["game"], r["label"])].append(r)
    games = sorted({g for g, _ in by})
    levels = {k: mean(r["levels_completed"] for r in v) for k, v in by.items()}
    rhae = {k: mean(r["score_rhae"] or 0.0 for r in v) for k, v in by.items()}
    seeds = {k: sorted(r["seed"] for r in v) for k, v in by.items()}
    nseeds = sorted({len(s) for s in seeds.values()})
    split = json.loads((ROOT / "splits.json").read_text())
    heldout = set(split["heldout"])

    print(f"{len(games)} games, seeds per game and configuration: {nseeds}")
    print("config  runs  levels completed (total, per run)  mean RHAE %")
    for c in CONFIGS:
        rs = [r for r in rows if r["label"] == c]
        if rs:
            tot = sum(r["levels_completed"] for r in rs)
            print(f"  {c:3}  {len(rs):5d}  {tot:6d}  {tot / len(rs):5.3f}            "
                  f"{mean(r['score_rhae'] or 0.0 for r in rs):.4f}")

    tests = [("R1", "CA", "B", levels, "levels"), ("R2", "C", "B", levels, "levels"),
             ("R3", "CA", "B", rhae, "RHAE"), ("R4", "C", "B", rhae, "RHAE")]
    print("\nregistered tests (all games)")
    for name, x, y, d, what in tests:
        w, lo, t, p = compare(d, x, y, games)
        print(f"  {name}: {x} above {y} on {what} in {w}, below in {lo}, tied {t}; "
              f"one-sided p = {p:.4f} -> {verdict(w, lo, p)}")

    def pair_counts(x: str, y: str) -> tuple[int, int, int]:
        pairs = defaultdict(dict)
        for r in rows:
            if r["label"] in (x, y):
                pairs[(r["game"], r["seed"])][r["label"]] = r["levels_completed"]
        both = [v for v in pairs.values() if x in v and y in v]
        return (sum(1 for v in both if v[x] > v[y]), sum(1 for v in both if v[x] < v[y]), len(both))

    for name, x in (("R5", "CA"), ("R6", "C")):
        more, less, n = pair_counts(x, "B")
        p = sign_test(more, less)
        ok = "PASS" if more > less and p < 0.05 else "FAIL"
        print(f"  {name}: game-seed pairs where {x} completed more / fewer levels than B: {more} / {less} "
              f"of {n}; one-sided p = {p:.4f} -> {ok}")

    print("\ndescriptive")
    for what, d in (("levels", levels), ("RHAE", rhae)):
        w, lo, t, p = compare(d, "C", "CA", games)
        print(f"  C vs CA on {what}: above {w}, below {lo}, tied {t}, p = {p:.4f}")
    for label, gs in (("held-out", [g for g in games if g in heldout]),
                      ("design", [g for g in games if g not in heldout])):
        cells = []
        for name, x, y, d, what in tests:
            w, lo, t, p = compare(d, x, y, gs)
            cells.append(f"{name} {w}:{lo} (tied {t})")
        print(f"  {label} games ({len(gs)}): " + "  ".join(cells))
    more, less, n = pair_counts("C", "CA")
    print(f"  game-seed pairs where C completed more / fewer levels than CA: {more} / {less} of {n}")

    print("\nper game: levels B, C, CA | RHAE B, C, CA")
    for g in games:
        lv = " ".join(f"{levels.get((g, c), float('nan')):4.2f}" for c in CONFIGS)
        sc = " ".join(f"{rhae.get((g, c), float('nan')):6.3f}" for c in CONFIGS)
        print(f"  {g}{'*' if g in heldout else ' '}  {lv} | {sc}")
    print("  (* held-out game)")


if __name__ == "__main__":
    main(sys.argv[1:])
