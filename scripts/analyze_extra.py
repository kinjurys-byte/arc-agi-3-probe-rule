"""Comparisons beyond the registered tests (2026-10-14): any configurations,
from any result files, compared game by game.

Each source is NAME=path[:label][+path[:label]...]: the runs with that label
(default NAME) in those files, renamed NAME. Several files are pooled, which
is how the round-2 and replication games are combined.

  python scripts/analyze_extra.py \
      C=runs/syn_rooms_spendmatched/results.jsonl \
      CU=runs/syn_rooms_spendmatched/results.jsonl \
      CR=runs/syn_rooms_spendmatched/results.jsonl \
      --pairs C-CR,C-CU,CR-CU

For each configuration: mean RHAE (percent) and levels per run, overall and by
difficulty, probes per run and, for CU and CR, probes spent over the budget.
For each pair X-Y: games where the mean RHAE of X is above / below that of Y
(ties dropped) and the one-sided sign-test p for X above Y.

--same X,Y checks that the runs of X and Y (same game and seed) are identical:
levels, actions, probes and score.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from statistics import mean


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def difficulty(r: dict) -> str:
    d = [t for t in r.get("tags") or [] if t.startswith("d") and t[1:].isdigit()]
    return d[0] if d else "-"


def load(spec: str) -> tuple[str, list[dict]]:
    name, _, rest = spec.partition("=")
    rows = []
    for part in rest.split("+"):
        path, _, label = part.partition(":")
        label = label or name
        for line in open(path):
            if not line.strip():
                continue
            r = json.loads(line)
            if "error" in r or r.get("label") != label:
                continue
            rows.append(r)
    return name, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--pairs", default="")
    ap.add_argument("--same", default="")
    args = ap.parse_args()
    data = dict(load(s) for s in args.sources)

    def per_game(rows: list[dict]) -> dict[str, float]:
        by = defaultdict(list)
        for r in rows:
            by[r["game"]].append(r["score_rhae"] or 0.0)
        return {g: mean(v) for g, v in by.items()}

    print("config   runs  RHAE%   levels  probes  spent/budget   by difficulty (RHAE%)")
    for name, rows in data.items():
        diffs = sorted({difficulty(r) for r in rows})
        cells = []
        for d in diffs:
            v = [r for r in rows if difficulty(r) == d]
            cells.append(f"{d} {mean(r['score_rhae'] or 0 for r in v):.3f}")
        budget = [r for r in rows if r.get("probe_budget") is not None]
        spent = (f"{sum(r['probes'] for r in budget)}/{sum(r['probe_budget'] for r in budget)}"
                 if budget else "-")
        print(f"{name:7} {len(rows):5d}  {mean(r['score_rhae'] or 0 for r in rows):6.3f}  "
              f"{mean(r['levels_completed'] for r in rows):6.2f}  {mean(r['probes'] for r in rows):6.1f}  "
              f"{spent:>12}   " + "  ".join(cells))

    for pair in [p for p in args.pairs.split(",") if p]:
        x, y = pair.split("-")
        gx, gy = per_game(data[x]), per_game(data[y])
        games = sorted(set(gx) & set(gy))
        w = sum(1 for g in games if gx[g] > gy[g])
        lo = sum(1 for g in games if gx[g] < gy[g])
        print(f"{x} vs {y}: {x} above in {w}, below in {lo}, tied {len(games) - w - lo} of {len(games)} games; "
              f"one-sided sign test p = {sign_test(w, lo):.4f}; "
              f"mean RHAE {mean(gx[g] for g in games):.3f} vs {mean(gy[g] for g in games):.3f}")

    if args.same:
        x, y = args.same.split(",")
        key = lambda r: (r["game"], r["seed"])
        ax_, ay = {key(r): r for r in data[x]}, {key(r): r for r in data[y]}
        common = sorted(set(ax_) & set(ay))
        fields = ("levels_completed", "actions", "probes", "score_rhae")
        diff = [k for k in common if any(ax_[k][f] != ay[k][f] for f in fields)]
        print(f"same {x} / {y}: {len(common)} common runs, {len(diff)} differ" +
              (f" (first: {diff[:3]})" if diff else ""))


if __name__ == "__main__":
    main()
