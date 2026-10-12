"""Pre-registered analysis of the synthetic confirmatory run (amendment of
2026-10-12). Reads a results.jsonl written by run_experiments.py with the
configs A, B, C, C1 and CU on the evaluation games (tag "eval").

H1 transfer   median over (game, seed, level >= 3 completed by A and B) of
              actions_B / actions_A  <= 0.85
H2 placement  share of games where mean RHAE(C) > mean RHAE(CU) >= 0.6 and
              one-sided sign test p < 0.05 (ties dropped)
H4 depth      Spearman correlation between difficulty and the relative gain
              (C - B) / max(B, 0.01) over games < 0, one-sided p < 0.05
              (permutation test, 20000 draws, seed 0)
H5 discount   in the two hardest difficulties, share of games with
              RHAE(C) > RHAE(C1) >= 0.6 (descriptive)
H6 value      share of games where mean RHAE(C) > mean RHAE(B) >= 0.6 and
              one-sided sign test p < 0.05 (ties dropped); added in round 2
              (amendment of 2026-10-12, before the round-2 runs)

usage: python scripts/analyze_synthetic.py runs/<dir>/results.jsonl
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from statistics import mean, median


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x: list[float], y: list[float]) -> float:
    rx, ry = ranks(x), ranks(y)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def main(path: str) -> None:
    rows = [json.loads(line) for line in open(path) if line.strip()]
    rows = [r for r in rows if "error" not in r]
    diff = {}
    by = defaultdict(list)                      # (game, label) -> rows
    for r in rows:
        d = [t for t in r.get("tags") or [] if t.startswith("d") and t[1:].isdigit()]
        diff[r["game"]] = int(d[0][1:]) if d else 0   # real games: no difficulty tag
        label = r.get("label") or r.get("config")    # older result files have no label
        by[(r["game"], "CU" if label in ("C'", "CP") else label)].append(r)
    games = sorted(diff)
    labels = ["A", "B", "C", "C1", "CU"]
    score = {(g, c): mean(x["score_rhae"] or 0.0 for x in by[(g, c)]) for g in games for c in labels
             if by[(g, c)]}

    print("mean RHAE (%) and levels completed by difficulty")
    for d in sorted(set(diff.values())):
        gs = [g for g in games if diff[g] == d]
        cells = []
        for c in labels:
            rs = [x for g in gs for x in by[(g, c)]]
            if rs:
                cells.append(f"{c} {mean(x['score_rhae'] or 0 for x in rs):6.3f}/"
                             f"{mean(x['levels_completed'] for x in rs):4.2f}")
        print(f"  d{d}: " + "  ".join(cells))

    # H1
    ratios = []
    for g in games:
        a_runs = {x["seed"]: x for x in by[(g, "A")]}
        for b in by[(g, "B")]:
            a = a_runs.get(b["seed"])
            if a is None:
                continue
            la = {s["level"]: s["actions"] for s in a["levels"] if s.get("completed")}
            lb = {s["level"]: s["actions"] for s in b["levels"] if s.get("completed")}
            for lvl in sorted(set(la) & set(lb)):
                if lvl >= 3:
                    ratios.append(lb[lvl] / la[lvl])
    h1 = median(ratios) if ratios else None
    print(f"\nH1 transfer: median B/A action ratio on levels >= 3 = "
          f"{'n/a' if h1 is None else round(h1, 3)} (n = {len(ratios)}) -> "
          f"{'PASS' if h1 is not None and h1 <= 0.85 else 'FAIL'}")

    # H2
    w = sum(1 for g in games if score.get((g, "C"), 0) > score.get((g, "CU"), 0))
    lo = sum(1 for g in games if score.get((g, "C"), 0) < score.get((g, "CU"), 0))
    p2 = sign_test(w, lo)
    share = w / (w + lo) if w + lo else 0.0
    print(f"H2 placement: C > C' in {w} of {w + lo} games (ties {len(games) - w - lo}), "
          f"share {share:.2f}, sign test p = {p2:.4f} -> {'PASS' if share >= 0.6 and p2 < 0.05 else 'FAIL'}")

    if len(set(diff.values())) < 2:
        print("H4, H5: not defined without difficulty tags (e.g. real games)")
    else:
        # H4
        xs = [float(diff[g]) for g in games]
        ys = [(score.get((g, "C"), 0) - score.get((g, "B"), 0)) / max(score.get((g, "B"), 0), 0.01)
              for g in games]
        rho = spearman(xs, ys)
        rng = random.Random(0)
        perm = 0
        for _ in range(20000):
            yp = ys[:]
            rng.shuffle(yp)
            if spearman(xs, yp) <= rho:
                perm += 1
        p4 = (perm + 1) / 20001
        print(f"H4 depth: Spearman(difficulty, relative gain C over B) = {rho:.3f}, one-sided p = {p4:.4f} -> "
              f"{'PASS' if rho < 0 and p4 < 0.05 else 'FAIL'}")
        for d in sorted(set(diff.values())):
            vals = [y for g, y in zip(games, ys) if diff[g] == d]
            print(f"    d{d}: relative gain per game {[round(v, 2) for v in vals]}")

        # H5
        hard = sorted(set(diff.values()))[-2:]
        hg = [g for g in games if diff[g] in hard]
        w5 = sum(1 for g in hg if score.get((g, "C"), 0) > score.get((g, "C1"), 0))
        l5 = sum(1 for g in hg if score.get((g, "C"), 0) < score.get((g, "C1"), 0))
        print(f"H5 discount: hardest difficulties {hard}: C > C1 in {w5} of {len(hg)} games "
              f"(C < C1 in {l5}) -> share {w5 / len(hg) if hg else 0:.2f} "
              f"({'meets 0.6' if hg and w5 / len(hg) >= 0.6 else 'below 0.6'})")

    # H6
    w6 = sum(1 for g in games if score.get((g, "C"), 0) > score.get((g, "B"), 0))
    l6 = sum(1 for g in games if score.get((g, "C"), 0) < score.get((g, "B"), 0))
    p6 = sign_test(w6, l6)
    share6 = w6 / (w6 + l6) if w6 + l6 else 0.0
    print(f"H6 value: C > B in {w6} of {w6 + l6} games (ties {len(games) - w6 - l6}), "
          f"share {share6:.2f}, sign test p = {p6:.4f} -> {'PASS' if share6 >= 0.6 and p6 < 0.05 else 'FAIL'}")

    probes = {c: mean(x["probes"] for g in games for x in by[(g, c)]) for c in ("C", "C1", "CU")
              if any(by[(g, c)] for g in games)}
    print(f"\nmean probes per run: {', '.join(f'{c} {v:.1f}' for c, v in probes.items())}")
    cu = [x for g in games for x in by[(g, "CU")] if x.get("probe_budget") is not None]
    if cu:
        print(f"C' probes spent / budget: {sum(x['probes'] for x in cu)} / "
              f"{sum(x['probe_budget'] for x in cu)}")


if __name__ == "__main__":
    main(sys.argv[1])
