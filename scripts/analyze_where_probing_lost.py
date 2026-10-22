"""Exploratory follow-up to the registered real-game test: where always probing
(CA) lost RHAE, and why the rule (C) did not. Not part of any registration.

1. Over the real games in which B cleared level 1 in some run: Spearman
   correlation between B's median level-1 action ratio (actions over the human
   baseline) and the change in mean RHAE of CA, and of C, against B; one-sided
   permutation test (20,000 draws, seed 0).
2. Games B clears within five times the human actions in level 1: the RHAE
   changes and C's level-1 probes.
3. Probes as a share of actions, per configuration and suite.
4. Fast levels: the share of B's completed levels that took at most three
   times the human actions, the share of B's score they earned, and, on real
   games, the change in RHAE of C and CA summed over the game-levels B clears
   that fast (B's median over seeds) and over the rest. Each run's exact score
   (scripts/run_experiments.py rhae) is split over its levels in proportion to
   i * min(1.15, (h/a)^2).

usage: python scripts/analyze_where_probing_lost.py
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "runs" / "real_seeds15_34" / "results.jsonl"
SYNTHETIC = {
    "open rooms": ["syn_rooms_confirm", "syn_rooms_alwaysprobe"],
    "new rooms": ["syn_rooms_rep", "syn_rooms_rep_alwaysprobe"],
    "mazes": ["syn_r2_mazes_confirm", "syn_r2_mazes_alwaysprobe"],
    "cluttered rooms": ["syn_clutter_confirm"],
}
FAST = 3.0


def load(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        for line in open(p):
            if line.strip():
                r = json.loads(line)
                if "error" not in r:
                    rows.append(r)
    return rows


def level_scores(r: dict) -> dict[int, float]:
    """The run's score (percent) split over its completed levels."""
    base = r["baseline"]
    den = sum(range(1, len(base) + 1))
    raw, scored = {}, 0
    for x in r["levels"]:
        i = x["level"]
        if x["completed"] and i <= r["levels_completed"] and x["actions"] > 0:
            raw[i] = i * min(1.15, (base[i - 1] / x["actions"]) ** 2)
            scored += i
    if not raw:
        return {}
    total = 100.0 * min(sum(raw.values()) / den, scored / den)
    return {i: total * v / sum(raw.values()) for i, v in raw.items()}


def level_probes(r: dict, i: int) -> int:
    """Probes the run made in level i. Rows list completed levels only, so the
    probes of the level a run ended in are its total minus those listed."""
    lv = [x for x in r["levels"] if x["level"] == i]
    if lv:
        return lv[0]["probes"]
    if i == r["levels_completed"] + 1:
        return r["probes"] - sum(x["probes"] for x in r["levels"])
    return 0


def ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(x: list[float], y: list[float]) -> float:
    rx, ry = ranks(x), ranks(y)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den


def perm_p(x: list[float], y: list[float], draws: int = 20000, seed: int = 0) -> float:
    obs = spearman(x, y)
    rng = random.Random(seed)
    yy = list(y)
    hits = 0
    for _ in range(draws):
        rng.shuffle(yy)
        if spearman(x, yy) >= obs - 1e-12:
            hits += 1
    return hits / draws


def main() -> None:
    rows = load([REAL])
    by = defaultdict(list)
    for r in rows:
        by[(r["game"], r["label"])].append(r)
    games = sorted({r["game"] for r in rows})
    rhae = {k: mean(r["score_rhae"] or 0.0 for r in v) for k, v in by.items()}

    def l1_ratios(g: str, c: str) -> list[float]:
        return [r["levels"][0]["actions"] / r["baseline"][0] for r in by[(g, c)]
                if r["levels"] and r["levels"][0]["completed"]]

    print("1. B's level-1 action ratio against the change in mean RHAE (points)")
    cleared = [g for g in games if l1_ratios(g, "B")]
    ratio = [median(l1_ratios(g, "B")) for g in cleared]
    for c in ("CA", "C"):
        d = [rhae[(g, c)] - rhae[(g, "B")] for g in cleared]
        print(f"   {c}: {len(cleared)} games, Spearman {spearman(ratio, d):+.3f}, "
              f"one-sided permutation p = {perm_p(ratio, d):.4f}")

    print("\n2. games B clears within five times the human actions in level 1")
    fast = [g for g, x in zip(cleared, ratio) if x <= 5]
    for g in fast:
        c_l1 = mean(level_probes(r, 1) for r in by[(g, "C")])
        ca_l1 = mean(level_probes(r, 1) for r in by[(g, "CA")])
        acts = {c: median(r["levels"][0]["actions"] for r in by[(g, c)]
                          if r["levels"] and r["levels"][0]["completed"]) for c in ("B", "C", "CA")
                if l1_ratios(g, c)}
        print(f"   {g}: B ratio {median(l1_ratios(g, 'B')):.1f} (h = {by[(g, 'B')][0]['baseline'][0]}), "
              f"RHAE change CA {rhae[(g, 'CA')] - rhae[(g, 'B')]:+.2f}, C {rhae[(g, 'C')] - rhae[(g, 'B')]:+.2f}; "
              f"level-1 probes per run C {c_l1:.1f}, CA {ca_l1:.1f}; median level-1 actions "
              + ", ".join(f"{c} {v:.0f}" for c, v in acts.items()))
    rest = [g for g in cleared if g not in fast]
    up = sum(1 for g in rest if rhae[(g, "CA")] > rhae[(g, "B")])
    down = sum(1 for g in rest if rhae[(g, "CA")] < rhae[(g, "B")])
    print(f"   other {len(rest)} games: CA above B in {up}, below in {down}")

    print("\n3. probes as a share of actions")
    suites = {name: load([ROOT / "runs" / d / "results.jsonl" for d in ds]) for name, ds in SYNTHETIC.items()}
    suites["real games"] = rows
    for name, rs in suites.items():
        cells = []
        for c in ("C", "CA"):
            sub = [r for r in rs if r["label"] == c]
            if sub:
                cells.append(f"{c} {100 * sum(r['probes'] for r in sub) / sum(r['actions'] for r in sub):.1f}%")
        print(f"   {name}: " + ", ".join(cells))

    print(f"\n4. levels B completed within {FAST:g} times the human actions")
    for name, rs in suites.items():
        b = [r for r in rs if r["label"] == "B"]
        n = n_fast = 0
        total = total_fast = 0.0
        for r in b:
            sc = level_scores(r)
            for x in r["levels"]:
                if x["level"] in sc:
                    n += 1
                    total += sc[x["level"]]
                    if x["actions"] / r["baseline"][x["level"] - 1] <= FAST:
                        n_fast += 1
                        total_fast += sc[x["level"]]
        print(f"   {name}: {n_fast} of {n} completed levels ({100 * n_fast / n:.0f}%), "
              f"earning {100 * total_fast / total:.0f}% of B's score")

    contrib = defaultdict(float)
    b_ratio = defaultdict(list)
    for r in rows:
        for i, v in level_scores(r).items():
            contrib[(r["game"], i, r["label"])] += v / len(by[(r["game"], r["label"])])
        if r["label"] == "B":
            for x in r["levels"]:
                if x["completed"]:
                    b_ratio[(r["game"], x["level"])].append(x["actions"] / r["baseline"][x["level"] - 1])
    cells = sorted({(g, i) for g, i, _ in contrib})
    fast_cells = [k for k in cells if k in b_ratio and median(b_ratio[k]) <= FAST]
    print(f"   real game-levels with B's median ratio within {FAST:g}: "
          + ", ".join(f"{g} level {i}" for g, i in fast_cells))
    for c in ("C", "CA"):
        d_fast = sum(contrib[(g, i, c)] - contrib[(g, i, "B")] for g, i in fast_cells)
        d_rest = sum(contrib[(g, i, c)] - contrib[(g, i, "B")] for g, i in cells if (g, i) not in fast_cells)
        print(f"   {c} against B, summed over games (points of game RHAE): there {d_fast:+.2f}, elsewhere {d_rest:+.2f}")
    for g, i in fast_cells:
        print(f"     {g} level {i}: B {contrib[(g, i, 'B')]:.3f}, C {contrib[(g, i, 'C')]:.3f}, "
              f"CA {contrib[(g, i, 'CA')]:.3f}")

    print(f"\n5. run by run: the same game, seed and level as each level B completed within {FAST:g} times")
    print("   the human actions (points of game RHAE summed over games, i.e. summed over runs and divided by")
    print("   the seeds per game; probes are per such level)")
    for name, rs in suites.items():
        runs = {(r["game"], r["seed"], r["label"]): r for r in rs}
        seeds = len({r["seed"] for r in rs})
        scores = {k: level_scores(v) for k, v in runs.items()}
        per_level = defaultdict(lambda: defaultdict(float))
        for (g, s, c), r in runs.items():
            if c != "B":
                continue
            for x in r["levels"]:
                i = x["level"]
                if i not in scores[(g, s, "B")] or x["actions"] / r["baseline"][i - 1] > FAST:
                    continue
                cell = per_level[i]
                cell["n"] += 1
                for other in ("C", "CA"):
                    if (g, s, other) not in runs:
                        continue
                    cell[other] += scores[(g, s, other)].get(i, 0.0) - scores[(g, s, "B")][i]
                    cell[other + " probes"] += level_probes(runs[(g, s, other)], i)
        if not per_level:
            print(f"   {name}: none")
            continue
        tot = {c: sum(v[c] for v in per_level.values()) / seeds for c in ("C", "CA")}
        print(f"   {name}: C {tot['C']:+.2f}, CA {tot['CA']:+.2f}")
        for i in sorted(per_level):
            v = per_level[i]
            print(f"     level {i}: {int(v['n'])} levels; C {v['C'] / seeds:+.2f} ({v['C probes'] / v['n']:.2f} probes), "
                  f"CA {v['CA'] / seeds:+.2f} ({v['CA probes'] / v['n']:.2f} probes)")


if __name__ == "__main__":
    main()
