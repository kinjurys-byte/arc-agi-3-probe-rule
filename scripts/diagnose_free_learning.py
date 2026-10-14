"""Free-learning diagnosis from the per-step logs of B and C (exploratory, 2026-10-14).

The probe rule values a probe by the later-level actions it saves, but that
saving is counterfactual: it is zero when the default policy B would try the
action anyway. B tries actions of unknown effect only when it is stuck (no
action known to work is left untried anywhere in the level graph; reason
"retry" in the step log). This script measures, for the same games and seeds:

  stuck share    share of B's level-1 actions taken while stuck, i.e. "retry"
                 steps after some action type has already worked (the opening
                 steps of a game, before anything is known, do not count)
  first stuck    B's level-1 action count at its first such step, and its
                 distance from the first action that worked
  useful types   action types (a simple action, or a click type keyed by colour
                 and shape) that changed the frame, completed a level or won,
                 in B or C of the same game and seed
  free share     of the useful types C found useful in level 1, the share B
                 also found useful in level 1 (learned for free); by kind
                 (simple actions "a*", click types "c*") and only over the
                 games and seeds where both completed level 1
  first use      level-1 action count at which B and C first saw each type
                 work, for types both found in level 1 (median)
  B later        for types C found in level 1 and B did not: the level in which
                 B first saw them work (or never)

usage (one or more --out directories of run_experiments.py, run with step logs,
that is without --no-step-logs, and with configs B and C):

  python scripts/diagnose_free_learning.py runs/real_diag_heldout runs/real_diag_design \\
      --out runs/free_learning_real.json

Only the standard library is used. The JSON holds per-run counts, per game and
seed comparisons and the aggregates printed here; no frames or game content.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

USEFUL = {"change", "level", "win"}
NAME = re.compile(r"^(?P<game>.+)_(?P<cfg>[A-Z0-9]+)_s(?P<seed>-?\d+)\.jsonl$")


def parse_run(path: Path) -> dict:
    """One step log -> per-level counts and the first try / first use of every type."""
    first_try: dict[str, list] = {}      # type -> [level, level action count, reason]
    first_use: dict[str, list] = {}      # type -> [level, level action count]
    levels: dict[int, dict] = {}
    known = False                        # has any type worked yet in this run
    summary = None
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue                 # a run cut off mid-line
            if "summary" in rec:
                summary = rec["summary"]
                continue
            lvl, al, why, eff, key = rec.get("lvl"), rec.get("al"), rec.get("why"), rec.get("eff"), rec.get("key")
            if lvl is None:
                continue
            L = levels.setdefault(lvl, {"n": 0, "stuck": 0, "first_stuck": None, "first_useful": None,
                                        "why": Counter(), "eff": Counter()})
            L["n"] += 1
            L["why"][why] += 1
            L["eff"][eff] += 1
            if why == "retry" and known:
                L["stuck"] += 1
                if L["first_stuck"] is None:
                    L["first_stuck"] = al
            if key is not None:
                first_try.setdefault(key, [lvl, al, why])
                if eff in USEFUL:
                    first_use.setdefault(key, [lvl, al])
                    if L["first_useful"] is None:
                        L["first_useful"] = al
                    known = True
    return {"levels": levels, "first_try": first_try, "first_use": first_use, "summary": summary}


def load_dir(d: Path) -> tuple[dict, dict]:
    """Step logs of a run directory -> {(game, cfg, seed): parsed}, and results.jsonl rows."""
    runs = {}
    for p in sorted((d / "logs").glob("*/*.jsonl")):
        if p.name == "summary.jsonl":
            continue
        m = NAME.match(p.name)
        if not m or m["cfg"] not in ("B", "C"):
            continue
        runs[(m["game"], m["cfg"], int(m["seed"]))] = parse_run(p)
    rows = {}
    res = d / "results.jsonl"
    if res.exists():
        for line in open(res):
            if not line.strip():
                continue
            r = json.loads(line)
            if "error" in r or r.get("label") not in ("B", "C"):
                continue
            rows[(r["game"], r["label"], r["seed"])] = r
    return runs, rows


def completed_level1(run: dict) -> bool:
    s = run["summary"] or {}
    if s.get("levels_completed"):
        return True
    return any(lv > 1 for lv in run["levels"])


def pair_stats(b: dict, c: dict) -> dict:
    useful = set(b["first_use"]) | set(c["first_use"])
    c_l1 = sorted(k for k in useful if c["first_use"].get(k, [0])[0] == 1)
    b_l1 = {k for k in useful if b["first_use"].get(k, [0])[0] == 1}
    both = [k for k in c_l1 if k in b_l1]
    later = Counter()
    for k in c_l1:
        if k not in b_l1:
            later[str(b["first_use"][k][0]) if k in b["first_use"] else "never"] += 1
    gaps_b = [b["first_use"][k][1] for k in both]
    gaps_c = [c["first_use"][k][1] for k in both]
    return {
        "useful": len(useful),
        "c_l1": len(c_l1), "free": len(both),
        "c_l1_simple": sum(1 for k in c_l1 if k.startswith("a")),
        "free_simple": sum(1 for k in both if k.startswith("a")),
        "c_l1_click": sum(1 for k in c_l1 if k.startswith("c")),
        "free_click": sum(1 for k in both if k.startswith("c")),
        "b_first_use_l1_median": median(gaps_b) if gaps_b else None,
        "c_first_use_l1_median": median(gaps_c) if gaps_c else None,
        "b_later": dict(later),
        "b_done_l1": completed_level1(b), "c_done_l1": completed_level1(c),
        "moves_l1_b": all(b["first_use"].get(f"a{i}", [0])[0] == 1 for i in (1, 2, 3, 4)),
        "moves_l1_c": all(c["first_use"].get(f"a{i}", [0])[0] == 1 for i in (1, 2, 3, 4)),
    }


def ratio(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


def aggregate(runs: dict, rows: dict, pairs: dict) -> dict:
    out: dict = {}
    for cfg in ("B", "C"):
        rs = [v for (g, k, s), v in runs.items() if k == cfg]
        l1 = [r["levels"].get(1) for r in rs if r["levels"].get(1)]
        n1 = sum(L["n"] for L in l1)
        stuck1 = sum(L["stuck"] for L in l1)
        fs = [L["first_stuck"] for L in l1 if L["first_stuck"] is not None]
        dist = [L["first_stuck"] - L["first_useful"] for L in l1
                if L["first_stuck"] is not None and L["first_useful"] is not None]
        n_all = sum(L["n"] for r in rs for L in r["levels"].values())
        stuck_all = sum(L["stuck"] for r in rs for L in r["levels"].values())
        lv = [(r["summary"] or {}).get("levels_completed", 0) for r in rs]
        sc = [rows[k]["score_rhae"] or 0.0 for k in rows if k[1] == cfg]
        out[cfg] = {
            "runs": len(rs),
            "levels_completed_mean": round(mean(lv), 3) if lv else None,
            "share_done_l1": ratio(sum(1 for r in rs if completed_level1(r)), len(rs)),
            "rhae_mean_pct": round(mean(sc), 4) if sc else None,
            "stuck_share_l1": ratio(stuck1, n1),
            "share_runs_stuck_l1": ratio(len(fs), len(l1)),
            "first_stuck_l1_median": median(fs) if fs else None,
            "first_stuck_after_first_useful_median": median(dist) if dist else None,
            "stuck_share_all": ratio(stuck_all, n_all),
            "level1_actions_median": median(L["n"] for L in l1) if l1 else None,
        }
    ps = list(pairs.values())

    def free(sel: list[dict], part: str = "") -> dict:
        a = sum(p["free" + part] for p in sel)
        b = sum(p["c_l1" + part] for p in sel)
        return {"free": a, "of": b, "share": ratio(a, b)}

    done = [p for p in ps if p["b_done_l1"] and p["c_done_l1"]]
    later = Counter()
    for p in ps:
        later.update(p["b_later"])
    bm = [p["b_first_use_l1_median"] for p in ps if p["b_first_use_l1_median"] is not None]
    cm = [p["c_first_use_l1_median"] for p in ps if p["c_first_use_l1_median"] is not None]
    out["pairs"] = {
        "n": len(ps),
        "useful_types_mean": round(mean(p["useful"] for p in ps), 2) if ps else None,
        "free_all": free(ps), "free_simple": free(ps, "_simple"), "free_click": free(ps, "_click"),
        "pairs_both_done_l1": len(done),
        "free_all_both_done_l1": free(done), "free_click_both_done_l1": free(done, "_click"),
        "b_first_use_l1_median": median(bm) if bm else None,
        "c_first_use_l1_median": median(cm) if cm else None,
        "b_later_level": dict(sorted(later.items())),
        "moves_known_after_l1_b": sum(p["moves_l1_b"] for p in ps),
        "moves_known_after_l1_c": sum(p["moves_l1_c"] for p in ps),
    }
    return out


def per_game(runs: dict, rows: dict, pairs: dict) -> dict:
    out = {}
    for g in sorted({k[0] for k in runs}):
        ps = [v for (gg, s), v in pairs.items() if gg == g]
        b1 = [v["levels"].get(1) for (gg, k, s), v in runs.items() if gg == g and k == "B" and v["levels"].get(1)]
        n1 = sum(L["n"] for L in b1)
        sc = {cfg: [rows[k]["score_rhae"] or 0.0 for k in rows if k[0] == g and k[1] == cfg] for cfg in ("B", "C")}
        lv = {cfg: [(v["summary"] or {}).get("levels_completed", 0) for (gg, k, s), v in runs.items()
                    if gg == g and k == cfg] for cfg in ("B", "C")}
        out[g] = {
            "pairs": len(ps),
            "b_stuck_share_l1": ratio(sum(L["stuck"] for L in b1), n1),
            "free": sum(p["free"] for p in ps), "c_l1": sum(p["c_l1"] for p in ps),
            "levels_b": round(mean(lv["B"]), 2) if lv["B"] else None,
            "levels_c": round(mean(lv["C"]), 2) if lv["C"] else None,
            "rhae_b": round(mean(sc["B"]), 4) if sc["B"] else None,
            "rhae_c": round(mean(sc["C"]), 4) if sc["C"] else None,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default=None, help="write the JSON summary here")
    args = ap.parse_args()
    result = {"version": 1, "suites": {}}
    for d in map(Path, args.dirs):
        runs, rows = load_dir(d)
        if not runs:
            print(f"{d}: no step logs of B or C found under {d / 'logs'}", file=sys.stderr)
            continue
        pairs = {}
        for (g, cfg, s), v in runs.items():
            if cfg == "B" and (g, "C", s) in runs:
                pairs[(g, s)] = pair_stats(v, runs[(g, "C", s)])
        agg = aggregate(runs, rows, pairs)
        compact_runs = []
        for (g, cfg, s), v in sorted(runs.items()):
            r = rows.get((g, cfg, s), {})
            sm = v["summary"] or {}
            l1 = v["levels"].get(1, {})
            compact_runs.append({
                "game": g, "config": cfg, "seed": s,
                "levels_completed": sm.get("levels_completed"), "win_levels": sm.get("win_levels"),
                "actions": sm.get("actions"), "probes": sm.get("probes"),
                "score_rhae": r.get("score_rhae"),
                "l1_n": l1.get("n"), "l1_stuck": l1.get("stuck"), "l1_first_stuck": l1.get("first_stuck"),
                "l1_first_useful": l1.get("first_useful"),
                "useful_types": len(v["first_use"]), "tried_types": len(v["first_try"]),
                "logged_steps": sum(L["n"] for L in v["levels"].values()),
            })
        result["suites"][d.name] = {
            "aggregate": agg,
            "per_game": per_game(runs, rows, pairs),
            "pairs": [dict(game=g, seed=s, **p) for (g, s), p in sorted(pairs.items())],
            "runs": compact_runs,
        }
        a = agg
        print(f"== {d.name}: {a['B']['runs']} B runs, {a['C']['runs']} C runs, {a['pairs']['n']} game-seed pairs")
        for cfg in ("B", "C"):
            x = a[cfg]
            print(f"  {cfg}: levels {x['levels_completed_mean']}  done L1 {x['share_done_l1']}  "
                  f"RHAE% {x['rhae_mean_pct']}  stuck share L1 {x['stuck_share_l1']} (all levels "
                  f"{x['stuck_share_all']})  runs stuck in L1 {x['share_runs_stuck_l1']}  first stuck "
                  f"{x['first_stuck_l1_median']} (+{x['first_stuck_after_first_useful_median']} after first "
                  f"useful)  L1 actions {x['level1_actions_median']}")
        p = a["pairs"]
        print(f"  useful types per pair {p['useful_types_mean']}; of the types C found useful in L1, B also "
              f"did in L1: {p['free_all']['free']}/{p['free_all']['of']} = {p['free_all']['share']} "
              f"(simple {p['free_simple']['share']}, clicks {p['free_click']['share']}); "
              f"pairs where both cleared L1: {p['pairs_both_done_l1']}, free share there "
              f"{p['free_all_both_done_l1']['share']} (clicks {p['free_click_both_done_l1']['share']})")
        print(f"  first use in L1 (median of pair medians): B {p['b_first_use_l1_median']}, "
              f"C {p['c_first_use_l1_median']}; B's level for the rest: {p['b_later_level']}; "
              f"all four moves known after L1: B {p['moves_known_after_l1_b']}, C {p['moves_known_after_l1_c']} "
              f"of {p['n']}")
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1, default=str))
        print(f"wrote {args.out} ({Path(args.out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
