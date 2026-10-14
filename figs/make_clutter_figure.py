"""Figure for the cluttered-room suite (achromatic):
(a) base rooms (of 12 per clutter level) where C, and the always-probe control
    CA, had a higher mean RHAE than B over the five seeds;
(b) share of B runs that saw the switch work in level 1.

Reads runs/syn_clutter_confirm/results.jsonl and runs/syn_clutter_free_learning.json
(the output of scripts/diagnose_free_learning.py on runs/syn_clutter_diag).
Writes figure3_clutter.png (200 dpi) and .svg next to this script.

usage: python figs/make_clutter_figure.py [results.jsonl] [free_learning.json]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

OUT = Path(__file__).resolve().parent
RUNS = Path(__file__).resolve().parents[1] / "runs"
SHARES = {1: 0, 2: 20, 3: 40, 4: 60}      # clutter level -> percent of the room floor

INK = "#1a1a1a"
INK2 = "#5c5c5c"
GRID = "#e3e3e3"
MID = "#8a8a8a"
LIGHT = "#b5b5b5"

plt.rcParams.update({
    "font.family": "Inter",
    "font.size": 10,
    "axes.edgecolor": GRID,
    "axes.linewidth": 0.8,
    "axes.labelcolor": INK2,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "svg.fonttype": "none",
    "svg.hashsalt": "pay-for-information-early",
})


def level(game: str) -> int:
    return int(game[1])


def main(results: Path, free: Path) -> dict:
    rows = [json.loads(x) for x in open(results) if x.strip()]
    by = defaultdict(list)
    for r in rows:
        if "error" not in r:
            by[(r["game"], r["label"])].append(r["score_rhae"] or 0.0)
    games = sorted({g for g, c in by if c == "B"})
    xs = sorted(SHARES)
    n_games = {d: sum(1 for g in games if level(g) == d) for d in xs}
    wins = {}
    for c in ("C", "CA"):
        if any((g, c) in by for g in games):
            wins[c] = [sum(1 for g in games if level(g) == d and mean(by[(g, c)]) > mean(by[(g, "B")]))
                       for d in xs]
    fl = json.loads(Path(free).read_text())
    suite = next(iter(fl["suites"].values()))
    b_runs = [r for r in suite["runs"] if r["config"] == "B"]
    switch = [100 * mean(1.0 if r["l1_useful_click"] > 0 else 0.0 for r in b_runs if level(r["game"]) == d)
              for d in xs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 3.9))
    pos = list(range(len(xs)))
    labels = [f"{SHARES[d]}%" for d in xs]
    width = 0.36 if len(wins) == 2 else 0.6
    names = {"C": "C (probe rule)", "CA": "CA (always probe)"}
    colors = {"C": INK, "CA": LIGHT}
    for k, (c, v) in enumerate(wins.items()):
        off = (k - (len(wins) - 1) / 2) * (width + 0.04)
        ax1.bar([p + off for p in pos], v, width=width, color=colors[c], label=names[c], zorder=3)
        for p, val in zip(pos, v):
            ax1.text(p + off, val + 0.15, str(val), ha="center", va="bottom", fontsize=9, color=INK)
    half = max(n_games.values()) / 2
    ax1.axhline(half, color=MID, lw=1, ls=(0, (4, 3)), zorder=2)
    ax1.text(-0.9, half + 0.15, "half", ha="left", va="bottom", fontsize=8.5, color=INK2)
    ax1.set_ylim(0, max(n_games.values()) * 1.3)
    ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax1.set_ylabel(f"Base rooms (of {max(n_games.values())})")
    ax1.set_title("(a) Rooms where the agent beat B", loc="left", fontsize=10.5, color=INK,
                  fontweight="semibold", pad=10)
    leg = ax1.legend(loc="upper right", ncol=2, frameon=False, fontsize=9, borderaxespad=0.1,
                     handlelength=1.2)
    for t in leg.get_texts():
        t.set_color(INK)

    ax2.bar(pos, switch, width=0.6, color=INK, zorder=3)
    for p, v in zip(pos, switch):
        ax2.text(p, v + 2, f"{v:.0f}%", ha="center", va="bottom", fontsize=9, color=INK)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("B runs (%)")
    ax2.set_title("(b) B learned the switch in level 1", loc="left", fontsize=10.5, color=INK,
                  fontweight="semibold", pad=10)

    for ax in (ax1, ax2):
        ax.set_xticks(pos)
        ax.set_xticklabels(labels)
        ax.set_xlim(-0.95 if ax is ax1 else -0.6, len(xs) - 0.4)
        ax.set_xlabel("Room floor turned into wall")
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s_ in ("top", "right", "left"):
            ax.spines[s_].set_visible(False)
    fig.tight_layout(w_pad=3)
    fig.savefig(OUT / "figure3_clutter.png", dpi=200, facecolor="white")
    fig.savefig(OUT / "figure3_clutter.svg", facecolor="white", metadata={"Date": None})
    plt.close(fig)
    return {"wins": wins, "games": n_games, "switch": switch}


if __name__ == "__main__":
    res = Path(sys.argv[1]) if len(sys.argv) > 1 else RUNS / "syn_clutter_confirm" / "results.jsonl"
    fl = Path(sys.argv[2]) if len(sys.argv) > 2 else RUNS / "syn_clutter_free_learning.json"
    out = main(res, fl)
    print("games per level", out["games"])
    for c, v in out["wins"].items():
        print(f"{c} above B:", v)
    print("switch in L1 (% of B runs)", [round(x, 1) for x in out["switch"]])
