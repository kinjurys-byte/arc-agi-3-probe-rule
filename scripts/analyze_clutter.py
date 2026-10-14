"""Registered analysis of the cluttered-room suite (third family, 2026-10-14).

Games k<d><kk>: clutter level d (1-4) and base room kk; the four games of a
base room differ only in clutter (scripts/make_clutter.py). Per game, scores
are mean RHAE over seeds and the relative gain of C over B is
(C - B) / max(B, 0.01), as in H4 of scripts/analyze_synthetic.py.

K1 dose      mean over base rooms of the Spearman correlation between clutter
             and the relative gain of C over B (four games per room); one-sided
             permutation p for a negative value, permuting clutter within each
             base room (20000 draws, seed 0). Criterion: < 0 and p < 0.05.
K2 free      the same statistic and test between clutter and the share of B
             runs that saw a click type work in level 1 (the switch: decoys
             never change the frame), from the step logs of B. Criterion: > 0
             and p < 0.05 (one-sided, for a positive value).
K3 link      the same statistic between that share and the relative gain
             (descriptive; negative if the gain falls where B learns the
             switch for free).
Also printed: the pooled Spearman correlations over all games, C above B by
clutter level, and the level-1 free share of all useful types (B and C, from
scripts/diagnose_free_learning.py).

usage: python scripts/analyze_clutter.py RESULTS.jsonl STEP_LOG_DIR
  RESULTS.jsonl  results of B and C (other configurations are ignored)
  STEP_LOG_DIR   a run_experiments.py --out directory with step logs of B and C
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_synthetic import sign_test, spearman  # noqa: E402
import diagnose_free_learning as dfl  # noqa: E402

DRAWS = 20000


def within(xs: dict, ys: dict, rooms: dict) -> float:
    """Mean over base rooms of Spearman(x, y) across the games of that room."""
    vals = []
    for games in rooms.values():
        x = [xs[g] for g in games]
        y = [ys[g] for g in games]
        if len(set(x)) > 1 and len(set(y)) > 1:
            vals.append(spearman(x, y))
        else:
            vals.append(0.0)
    return mean(vals)


def stratified_p(xs: dict, ys: dict, rooms: dict, observed: float, lower: bool) -> float:
    rng = random.Random(0)
    hits = 0
    for _ in range(DRAWS):
        xp = {}
        for games in rooms.values():
            vals = [xs[g] for g in games]
            rng.shuffle(vals)
            xp.update(zip(games, vals))
        r = within(xp, ys, rooms)
        hits += (r <= observed) if lower else (r >= observed)
    return (hits + 1) / (DRAWS + 1)


def main(results: str, log_dir: str) -> None:
    rows = [json.loads(x) for x in open(results) if x.strip()]
    rows = [r for r in rows if "error" not in r and r.get("label") in ("B", "C")]
    score = defaultdict(list)
    for r in rows:
        score[(r["game"], r["label"])].append(r["score_rhae"] or 0.0)
    games = sorted({g for g, _ in score})
    level = {g: int(g[1]) for g in games}
    rooms = defaultdict(list)
    for g in games:
        rooms[g[2:]].append(g)
    b = {g: mean(score[(g, "B")]) for g in games}
    c = {g: mean(score[(g, "C")]) for g in games}
    gain = {g: (c[g] - b[g]) / max(b[g], 0.01) for g in games}

    runs, _ = dfl.load_dir(Path(log_dir))
    sw = {}
    for g in games:
        seen = [v for (gg, cfg, s), v in runs.items() if gg == g and cfg == "B"]
        sw[g] = mean(any(k.startswith("c") and v["first_use"][k][0] == 1 for k in v["first_use"])
                     for v in seen) if seen else float("nan")
    missing = [g for g in games if sw[g] != sw[g]]
    if missing:
        raise SystemExit(f"no step logs of B for {missing}")

    print(f"{len(games)} games, {len(rooms)} base rooms, "
          f"{len(rows) // max(1, 2 * len(games))} seeds per game and configuration")
    print("clutter level: mean RHAE B, C; C above B; B saw the switch work in level 1 (share of runs)")
    for d in sorted(set(level.values())):
        gs = [g for g in games if level[g] == d]
        w = sum(1 for g in gs if c[g] > b[g])
        lo = sum(1 for g in gs if c[g] < b[g])
        print(f"  d{d}: B {mean(b[g] for g in gs):.3f}  C {mean(c[g] for g in gs):.3f}  "
              f"C above B in {w}, below in {lo} of {len(gs)}  switch in L1 {mean(sw[g] for g in gs):.2f}")
    w = sum(1 for g in games if c[g] > b[g])
    lo = sum(1 for g in games if c[g] < b[g])
    print(f"  all: C above B in {w}, below in {lo} of {len(games)}, one-sided sign test p = {sign_test(w, lo):.4f}")

    k1 = within(level, gain, rooms)
    p1 = stratified_p(level, gain, rooms, k1, lower=True)
    print(f"\nK1 dose: mean within-room Spearman(clutter, relative gain) = {k1:.3f}, "
          f"stratified one-sided p = {p1:.4f} -> {'PASS' if k1 < 0 and p1 < 0.05 else 'FAIL'}")
    k2 = within(level, sw, rooms)
    p2 = stratified_p(level, sw, rooms, k2, lower=False)
    print(f"K2 free: mean within-room Spearman(clutter, B switch in L1) = {k2:.3f}, "
          f"stratified one-sided p = {p2:.4f} -> {'PASS' if k2 > 0 and p2 < 0.05 else 'FAIL'}")
    k3 = within(sw, gain, rooms)
    print(f"K3 link: mean within-room Spearman(B switch in L1, relative gain) = {k3:.3f} (descriptive)")
    xs = [level[g] for g in games]
    print(f"pooled Spearman over games: (clutter, gain) {spearman(xs, [gain[g] for g in games]):.3f}, "
          f"(clutter, switch) {spearman(xs, [sw[g] for g in games]):.3f}, "
          f"(switch, gain) {spearman([sw[g] for g in games], [gain[g] for g in games]):.3f}")

    pairs = {(g, s): dfl.pair_stats(v, runs[(g, "C", s)]) for (g, cfg, s), v in runs.items()
             if cfg == "B" and (g, "C", s) in runs and g in level}
    print("\nlevel-1 free share (types C found useful in L1 that B also did), by clutter level:")
    for d in sorted(set(level.values())):
        ps = [p for (g, s), p in pairs.items() if level[g] == d]
        f = sum(p["free"] for p in ps)
        n = sum(p["c_l1"] for p in ps)
        fc = sum(p["free_click"] for p in ps)
        nc = sum(p["c_l1_click"] for p in ps)
        print(f"  d{d}: all {f}/{n} = {f / n if n else 0:.2f}   switch {fc}/{nc}   "
              f"four moves known after L1: B {sum(p['moves_l1_b'] for p in ps)}, "
              f"C {sum(p['moves_l1_c'] for p in ps)} of {len(ps)}")
    print("\nper game: clutter level, B, C, relative gain, B switch in L1")
    for g in games:
        print(f"  {g}: d{level[g]}  {b[g]:.3f}  {c[g]:.3f}  {gain[g]:+.2f}  {sw[g]:.2f}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
