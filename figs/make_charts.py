"""Figures 2 and 3 for the paper (achromatic). Writes PNG (200 dpi) and SVG next to this script.

Figure 2 reads the human baselines of the 25 public games stored in runs/real_calib and
runs/real_heldout. Figure 3 reads runs/syn_rooms_confirm, runs/syn_rooms_ablation and
runs/syn_r2_mazes_confirm. usage: python figs/make_charts.py
"""
import json
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

OUT = Path(__file__).resolve().parent
RUNS = Path(__file__).resolve().parents[1] / "runs"

INK = "#1a1a1a"        # primary text and the main series
INK2 = "#5c5c5c"       # secondary text
GRID = "#e3e3e3"       # hairline grid
DARK = "#3d3d3d"       # bars: levels 1-2
LIGHT = "#b5b5b5"      # bars: levels 3-6
MID = "#8a8a8a"        # second line series

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
    "svg.hashsalt": "pay-for-information-early",   # stable element ids, so the SVGs regenerate identically
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=200, facecolor="white")
    fig.savefig(OUT / f"{name}.svg", facecolor="white", metadata={"Date": None})
    plt.close(fig)


# ---------------------------------------------------------------- Figure 2
def public_baselines():
    """Per-level human baselines of the 25 public games, as stored with every real-game run."""
    seen = {}
    for name in ("real_calib", "real_heldout"):
        for line in open(RUNS / name / "results.jsonl"):
            r = json.loads(line)
            if r.get("baseline"):
                seen.setdefault(r["game"], r["baseline"])
    return seen


def figure2(min_games=5):
    """Value of one saved action, and of a saved share of a level, relative to level 1.
    From the score, saving one action in level i is worth (i/W) 2 h_i^2 / a_i^3 and saving a
    share s of it (s a_i actions) is worth (i/W) 2 s / r_i^2, with r_i = a_i / h_i. For an agent
    equally slow in every level (r_i = r) these are i h_1 / h_i and i times their level-1 value."""
    from statistics import median, quantiles
    base = public_baselines()
    top = max(len(h) for h in base.values())
    levels, med, lo, hi, n = [], [], [], [], []
    for i in range(1, top + 1):
        vals = [i * h[0] / h[i - 1] for h in base.values() if len(h) >= i]
        if len(vals) < min_games:
            break
        q1, _, q3 = quantiles(vals, n=4, method="inclusive")
        levels.append(i); med.append(median(vals)); lo.append(q1); hi.append(q3); n.append(len(vals))
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.fill_between(levels, lo, hi, color="#e6e6e6", lw=0, zorder=1)
    ax.plot(levels, levels, color=MID, lw=2, ls=(0, (5, 3)), marker="s", ms=6, mec="white", mew=1.5,
            label="Saving a fixed share of the level", zorder=3)
    ax.plot(levels, med, color=INK, lw=2, marker="o", ms=6.5, mec="white", mew=1.5,
            label="Saving one action (median; band: middle half of games)", zorder=4,
            solid_capstyle="round")
    ax.set_xticks(levels)
    ax.set_xticklabels([f"{i}\n{k}" for i, k in zip(levels, n)])
    ax.set_xlim(0.6, levels[-1] + 0.4)
    ax.set_ylim(0, levels[-1] + 1)
    ax.set_xlabel("Level (with the number of public games that have it)")
    ax.set_ylabel("Value relative to level 1")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    leg = ax.legend(loc="upper left", frameon=False, fontsize=9)
    for t in leg.get_texts():
        t.set_color(INK)
    fig.tight_layout()
    save(fig, "figure2_marginal_cost")
    return levels, med, lo, hi, n


# ---------------------------------------------------------------- Figure 3
def contributions(r):
    base = r["baseline"]
    n = len(base)
    w = n * (n + 1) / 2
    out = {}
    for s in r["levels"]:
        if s.get("completed") and s["actions"] > 0:
            i = s["level"]
            out[i] = 100 * i * min(1.15, (base[i - 1] / s["actions"]) ** 2) / w
    return out


def decompose(path, configs=("B", "C", "CU")):
    rows = [json.loads(x) for x in open(path) if x.strip()]
    res = {}
    for d in "1234":
        for c in configs:
            v = [r for r in rows if r["game"][1] == d and r["label"] == c and "error" not in r]
            early = mean(sum(x for i, x in contributions(r).items() if i <= 2) for r in v)
            late = mean(sum(x for i, x in contributions(r).items() if i >= 3) for r in v)
            res[(d, c)] = (early, late, len(v))
    return res


def figure3():
    panels = [
        ("(a) Open rooms", RUNS / "syn_rooms_confirm/results.jsonl", ["12", "16", "20", "28"]),
        ("(b) Rooms, moves known, no early door", RUNS / "syn_rooms_ablation/results.jsonl",
         ["12", "16", "20", "28"]),
        ("(c) Mazes", RUNS / "syn_r2_mazes_confirm/results.jsonl", ["6", "8", "10", "12"]),
    ]
    configs = ["B", "C", "CU"]
    names = {"B": "B", "C": "C", "CU": "C'"}
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.2))
    data = {title: decompose(path) for title, path, _ in panels}
    # (a) and (b) are the same room suite: give them one y-scale so bar heights compare
    room_top = 1.06 * max(e + l for t in (panels[0][0], panels[1][0]) for (e, l, _) in data[t].values())
    for ax, (title, path, sizes) in zip(axes, panels):
        res = data[title]
        top = room_top if ax is not axes[2] else 1.06 * max(e + l for (e, l, _) in res.values())
        ax.set_ylim(0, top)
        x = []
        ticks, ticklabels = [], []
        gap = 0.06
        width = 0.26
        for gi, d in enumerate("1234"):
            for ci, c in enumerate(configs):
                xc = gi * 1.0 + (ci - 1) * (width + gap)
                early, late, n = res[(d, c)]
                ax.bar(xc, early, width=width, color=DARK, edgecolor="white", linewidth=0, zorder=3)
                # 2px-style surface gap between the stacked segments
                ax.bar(xc, late, width=width, bottom=early, color=LIGHT, edgecolor="white",
                       linewidth=1.2, zorder=3)
                if early + late < 0.04 * top:      # too short to see: print the value
                    ax.text(xc, early + late + 0.012 * top, f"{early + late:.2f}", ha="center", va="bottom",
                            fontsize=7.5, color=INK2, zorder=4)
                ticks.append(xc)
                ticklabels.append(names[c])
                x.append(xc)
            ax.text(gi * 1.0, -0.13, f"{sizes[gi]}\u00d7{sizes[gi]}", transform=ax.get_xaxis_transform(),
                    ha="center", va="top", color=INK, fontsize=9.5)
        ax.set_xticks(ticks)
        ax.set_xticklabels(ticklabels, fontsize=9, color=INK2)
        ax.set_title(title, loc="left", fontsize=10.5, color=INK, fontweight="semibold", pad=10)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.set_xlim(-0.55, 3.55)
        ax.tick_params(axis="x", pad=3)
    for ax in axes:
        ax.set_ylabel("Mean RHAE (%)")
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=DARK, label="Levels 1-2"), Patch(facecolor=LIGHT, label="Levels 3-6")]
    fig.legend(handles=handles, loc="upper right", ncol=2, frameon=False, fontsize=9.5,
               bbox_to_anchor=(0.995, 1.0), labelcolor=INK)
    fig.tight_layout(rect=(0, 0.0, 1, 0.94), w_pad=2.5)
    save(fig, "figure3_where_gains_come_from")
    return data


if __name__ == "__main__":
    lv, med, lo, hi, n = figure2()
    print("figure 2: level, games, median, quartiles")
    for row in zip(lv, n, med, lo, hi):
        print("  ", row[0], row[1], round(row[2], 2), round(row[3], 2), round(row[4], 2))
    data = figure3()
    for title, res in data.items():
        print(title.replace("\n", " "))
        for k, v in sorted(res.items()):
            print("  ", k, tuple(round(x, 3) for x in v[:2]), "total", round(v[0] + v[1], 3), "n", v[2])
