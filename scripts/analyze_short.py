"""Registered analysis of the short-first-level suite (2026-10-28,
docs/registration_short.md).

Games f<d><kk>: arm d1 is the open 16x16 room, arm d2 the same room with
level 1 shrunk to a pocket around the exit; kk is the base room. Per game,
each configuration is summarized by its mean RHAE (percent) over the seeds.

S1 (primary)    in arm d2, C is above CA in at least 60% of the untied games,
                one-sided sign test p < 0.05
S2 (primary)    within base rooms, C - CA is larger in d2 than in d1 in at least
                60% of the untied base rooms, one-sided sign test p < 0.05
S3 (secondary)  in arm d2, the median number of level-1 probes is 0 for C and
                at least 5 for CA (over runs)
S4 (secondary)  as S1, in arm d1
S5 (secondary)  in arm d2, C is above B as in S1

Also printed (descriptive): mean RHAE, levels completed and level-1 share of
the score per configuration and arm, CA against B in each arm, and level-1
actions and probes.

usage: python scripts/analyze_short.py runs/<dir>/results.jsonl [more ...]
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from statistics import mean, median


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def verdict(w: int, lo: int, p: float) -> str:
    return "PASS" if w + lo and w / (w + lo) >= 0.6 and p < 0.05 else "FAIL"


def level_probes(r: dict, i: int) -> int:
    """Probes in level i; rows list completed levels only, so the probes of the
    level a run ended in are its total minus those listed."""
    lv = [x for x in r["levels"] if x["level"] == i]
    if lv:
        return lv[0]["probes"]
    if i == r["levels_completed"] + 1:
        return r["probes"] - sum(x["probes"] for x in r["levels"])
    return 0


def level1_points(r: dict) -> float:
    """Level 1's part of the run's score, in percentage points (the game score
    split over its levels in proportion to i * min(1.15, (h/a)^2))."""
    base = r["baseline"]
    raw = {}
    for x in r["levels"]:
        if x["completed"] and x["actions"] > 0:
            raw[x["level"]] = x["level"] * min(1.15, (base[x["level"] - 1] / x["actions"]) ** 2)
    if not raw or 1 not in raw:
        return 0.0
    return (r["score_rhae"] or 0.0) * raw[1] / sum(raw.values())


def main(paths: list[str]) -> None:
    rows = []
    for path in paths:
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                if "error" not in r:
                    rows.append(r)
    by = defaultdict(list)
    for r in rows:
        by[(r["game"], r["label"])].append(r)
    configs = sorted({c for _, c in by})
    games = sorted({g for g, _ in by})
    arm = {g: f"d{g[1]}" for g in games}
    base = {g: g[2:] for g in games}
    rhae = {k: mean(r["score_rhae"] or 0.0 for r in v) for k, v in by.items()}
    seeds = sorted({len(v) for v in by.values()})
    print(f"{len(games)} games ({sum(1 for g in games if arm[g] == 'd1')} in d1, "
          f"{sum(1 for g in games if arm[g] == 'd2')} in d2), seeds per game and configuration: {seeds}")

    def compare(x: str, y: str, a: str) -> tuple[int, int, int, float]:
        gs = [g for g in games if arm[g] == a and (g, x) in rhae and (g, y) in rhae]
        w = sum(1 for g in gs if rhae[(g, x)] > rhae[(g, y)])
        lo = sum(1 for g in gs if rhae[(g, x)] < rhae[(g, y)])
        return w, lo, len(gs) - w - lo, sign_test(w, lo)

    print("\nregistered tests")
    w, lo, t, p = compare("C", "CA", "d2")
    print(f"  S1: d2, C above CA in {w}, below in {lo}, tied {t}; one-sided p = {p:.4f} -> {verdict(w, lo, p)}")
    bases = sorted({base[g] for g in games})
    up = down = tie = 0
    for b in bases:
        g1, g2 = f"f1{b}", f"f2{b}"
        if all((g, c) in rhae for g in (g1, g2) for c in ("C", "CA")):
            d = (rhae[(g2, "C")] - rhae[(g2, "CA")]) - (rhae[(g1, "C")] - rhae[(g1, "CA")])
            up += d > 0
            down += d < 0
            tie += d == 0
    p = sign_test(up, down)
    print(f"  S2: base rooms where C - CA is larger in d2 than in d1: {up}, smaller: {down}, tied {tie}; "
          f"one-sided p = {p:.4f} -> {verdict(up, down, p)}")
    for c in ("C", "CA"):
        pr = [level_probes(r, 1) for g in games if arm[g] == "d2" for r in by.get((g, c), [])]
        if pr:
            print(f"  S3: d2, level-1 probes of {c}: median {median(pr)}, mean {mean(pr):.1f} over {len(pr)} runs")
    pr_c = [level_probes(r, 1) for g in games if arm[g] == "d2" for r in by.get((g, "C"), [])]
    pr_ca = [level_probes(r, 1) for g in games if arm[g] == "d2" for r in by.get((g, "CA"), [])]
    if pr_c and pr_ca:
        ok = median(pr_c) == 0 and median(pr_ca) >= 5
        print(f"  S3: {'PASS' if ok else 'FAIL'}")
    w, lo, t, p = compare("C", "CA", "d1")
    print(f"  S4: d1, C above CA in {w}, below in {lo}, tied {t}; one-sided p = {p:.4f} -> {verdict(w, lo, p)}")
    w, lo, t, p = compare("C", "B", "d2")
    print(f"  S5: d2, C above B in {w}, below in {lo}, tied {t}; one-sided p = {p:.4f} -> {verdict(w, lo, p)}")

    print("\ndescriptive")
    print("  arm config  runs  mean RHAE  levels/run  level-1 points  level-1 actions (median)  level-1 probes (mean)")
    for a in ("d1", "d2"):
        for c in configs:
            rs = [r for g in games if arm[g] == a for r in by.get((g, c), [])]
            if not rs:
                continue
            l1a = [r["levels"][0]["actions"] for r in rs if r["levels"]]
            print(f"  {a}  {c:4} {len(rs):5d}  {mean(r['score_rhae'] or 0.0 for r in rs):9.3f}  "
                  f"{mean(r['levels_completed'] for r in rs):10.2f}  {mean(level1_points(r) for r in rs):14.3f}  "
                  f"{median(l1a) if l1a else float('nan'):24.1f}  {mean(level_probes(r, 1) for r in rs):21.1f}")
    for a in ("d1", "d2"):
        for x, y in (("CA", "B"), ("C", "B"), ("C", "CA")):
            w, lo, t, p = compare(x, y, a)
            print(f"  {a}: {x} above {y} in {w}, below in {lo}, tied {t} (p = {p:.4f})")


if __name__ == "__main__":
    main(sys.argv[1:])
