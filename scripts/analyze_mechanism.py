"""Where does a configuration's score come from? (exploratory analysis)

1. From results.jsonl: the RHAE contribution of levels 1-2 and of levels 3+
   per difficulty and configuration, and how many runs cleared level 3.
2. If the run kept per-step logs (run_experiments.py without --no-step-logs):
   when each run knew all four moves (ACTION1-4 changed the frame at least
   once) and in which level it first used the switch (color 10).

usage: python scripts/analyze_mechanism.py runs/<dir>/results.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median


def contributions(r: dict) -> dict[int, float]:
    """Per-level share of the game score in percent (levels weighted by index)."""
    base = r.get("baseline") or []
    n = len(base)
    w = n * (n + 1) / 2 if n else 1
    out = {}
    for s in r.get("levels", []):
        if s.get("completed") and s["level"] <= n and s["actions"] > 0:
            i = s["level"]
            out[i] = 100 * i * min(1.15, (base[i - 1] / s["actions"]) ** 2) / w
    return out


def difficulty(r: dict) -> str:
    d = [t for t in r.get("tags", []) if t.startswith("d") and t[1:].isdigit()]
    return d[0] if d else "all"


def trace(path: Path) -> dict:
    known: set[str] = set()
    all4 = None
    switch_level = None
    for line in path.open():
        row = json.loads(line)
        if "why" not in row:
            continue
        key = str(row.get("key"))
        if key in ("a1", "a2", "a3", "a4") and row.get("eff") in ("change", "level"):
            known.add(key)
            if len(known) == 4 and all4 is None:
                all4 = (row["lvl"], row["t"])
        if key.startswith("c10:") and row.get("eff") == "change" and switch_level is None:
            switch_level = row["lvl"]
    return {"all4": all4, "switch_level": switch_level}


def main(path: str) -> None:
    rows = [json.loads(x) for x in open(path) if x.strip()]
    rows = [r for r in rows if "error" not in r]
    by = defaultdict(list)
    for r in rows:
        by[(difficulty(r), r["label"])].append(r)
    print("RHAE contribution (%) of levels 1-2 and 3+, runs clearing level 3")
    for (d, label), rs in sorted(by.items()):
        c12 = mean(sum(v for i, v in contributions(r).items() if i <= 2) for r in rs)
        c3 = mean(sum(v for i, v in contributions(r).items() if i >= 3) for r in rs)
        l3 = sum(1 for r in rs if r["levels_completed"] >= 3)
        print(f"  {d:4} {label:3} levels 1-2 {c12:.3f}  levels 3+ {c3:.3f}  cleared level 3: {l3}/{len(rs)}")

    logs = Path(path).parent / "logs"
    traces = defaultdict(list)
    for f in logs.glob("*/*.jsonl"):
        if f.name == "summary.jsonl":
            continue
        game, label = f.stem.split("_")[0], f.parent.name.split("_")[0]
        tags = next((r["tags"] for r in rows if r["game"] == game), [])
        d = next((t for t in tags if t.startswith("d") and t[1:].isdigit()), "all")
        traces[(d, label)].append(trace(f))
    if not traces:
        print("\nno per-step logs next to the results file; rerun without --no-step-logs for part 2")
        return
    print("\nmove and switch learning (from per-step logs)")
    for (d, label), ts in sorted(traces.items()):
        by_l1 = sum(1 for t in ts if t["all4"] and t["all4"][0] <= 1)
        steps = [t["all4"][1] for t in ts if t["all4"]]
        sw = defaultdict(int)
        for t in ts:
            sw[t["switch_level"]] += 1
        print(f"  {d:4} {label:3} all four moves by end of level 1: {by_l1}/{len(ts)}; "
              f"step when known (median): {median(steps) if steps else '-'}; "
              f"first switch use by level: {dict(sorted(sw.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)))}")


if __name__ == "__main__":
    main(sys.argv[1])
