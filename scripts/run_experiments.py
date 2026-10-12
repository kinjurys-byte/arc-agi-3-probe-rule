"""Run agent/my_agent.py over games x configs x seeds and collect results.

Each run plays one game in a fresh process with the real Agent.main() loop,
offline, from games cached in ./environment_files (run
`make play-local STEPS=10` once to download all public games first).

Configs
  A    graph explorer, effect table cleared every level
  B    A with the table carried across levels
  C    B plus the probe rule (rho, q)
  C1   C with q = 1 (the original, undiscounted rule)
  CU   control C': as many probes as C (same game, seed, rho), split evenly
       over levels; C runs first

Examples
  .venv/bin/python scripts/run_experiments.py --games ls20 --configs C --seeds 0
  .venv/bin/python scripts/run_experiments.py --configs A,B,C,CU --seeds 0,1,2 --jobs 4
  # rho sweep on the design split (rho affects C, C1 and CU)
  .venv/bin/python scripts/run_experiments.py --split design --configs B,C \\
      --rho 0.00003,0.0001,0.0003 --q 0.5 --seeds 0,1,2 --jobs 4 --no-step-logs
  # synthetic suite (scripts/make_synthetic.py), evaluation games only
  .venv/bin/python scripts/run_experiments.py --tags synthetic,eval --q q_synthetic.json ...

Game selection: real games by default (games tagged "synthetic" are left
out unless --tags asks for them). --split uses splits.json, created the first
time from the sorted real games with random.Random(2026) (15 design, 10
held-out); keep that file in git.

--q takes a number, a JSON file mapping a game id or a tag (e.g. "d2") to q,
or "auto": B runs first and q is its pooled level completion rate on the same
games and seeds (levels completed / levels attempted), used for C.

Outputs (under --out, default runs/<timestamp>)
  results.jsonl   one line per run: score, levels, actions, per-level stats
  logs/           per-step JSONL logs and summary.jsonl written by the agent
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "ARC-AGI-3-Agents"


def local_games(env_dir: Path) -> dict[str, dict]:
    """Short game id -> metadata, for games cached in env_dir."""
    out = {}
    for meta in env_dir.rglob("metadata.json"):
        try:
            info = json.loads(meta.read_text())
        except (OSError, ValueError):
            continue
        out[str(info.get("game_id", "")).split("-")[0]] = info
    return out


def load_split(games: list[str]) -> dict:
    """Frozen design / held-out split of the real games (created once)."""
    path = ROOT / "splits.json"
    if path.exists():
        return json.loads(path.read_text())
    import random
    ordered = sorted(games)
    n_design = round(0.6 * len(ordered))
    design = sorted(random.Random(2026).sample(ordered, n_design))
    split = {"seed": 2026, "games": ordered, "design": design,
             "heldout": [g for g in ordered if g not in design]}
    path.write_text(json.dumps(split, indent=1))
    print(f"wrote {path.name}: {len(design)} design, {len(split['heldout'])} held-out games")
    return split


def rhae(level_actions: list[int], completed: int, baseline: list[int] | None) -> float | None:
    """Per-game score as in arc_agi/scorecard.py: completed level i scores
    min(1.15, (h/a)^2), levels are weighted by i, and the game score is capped
    at the weight share of the levels that scored. Percent, like the scorecard."""
    if not baseline:
        return None
    num = den = scored = 0.0
    for i, h in enumerate(baseline, start=1):
        a = level_actions[i - 1] if i - 1 < len(level_actions) else 0
        s = min(1.15, (h / a) ** 2) if (i <= completed and a > 0) else 0.0
        num += i * s
        den += i
        if s > 0:
            scored += i
    if not den:
        return None
    return 100.0 * min(num / den, scored / den)


def run_one(job: dict) -> dict:
    """Play one game in this (worker) process and return a result row."""
    sys.path.insert(0, str(VENDOR))
    env_dir = job["env_dir"]
    os.environ["OPERATION_MODE"] = "offline"
    os.environ["ENVIRONMENTS_DIR"] = env_dir
    os.environ["ARC_AGENT_CONFIG"] = "C" if job["label"] == "C1" else job["label"]
    os.environ["ARC_SEED"] = str(job["seed"])
    os.environ["ARC_LOG_DIR"] = job["log_dir"]
    for k in ("ARC_RHO", "ARC_Q", "ARC_PROBE_BUDGET"):
        os.environ.pop(k, None)               # worker processes are reused
    for k, v in job["env"].items():
        os.environ[k] = str(v)

    import importlib.util
    import logging

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger().setLevel(logging.WARNING)
    import arc_agi
    from arc_agi import OperationMode

    spec = importlib.util.spec_from_file_location("user_agent", ROOT / "agent" / "my_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    Agent = mod.MyAgent
    Agent.MAX_ACTIONS = job["max_steps"]

    for name in ("arc_agi", "arc_agi.scorecard", "arc_agi.base"):
        logging.getLogger(name).setLevel(logging.WARNING)
    arc = arc_agi.Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=env_dir)
    arc.logger.setLevel(logging.WARNING)
    env = arc.make(job["game"])
    if env is None:
        return {**job, "error": "game not found locally"}
    agent = Agent(card_id="exp", game_id=job["game"], agent_name=f"exp.{job['game']}",
                  ROOT_URL="http://localhost", record=False, arc_env=env, tags=["exp"])
    t0 = time.time()
    agent.main()
    seconds = round(time.time() - t0, 2)
    sc = arc.get_scorecard()
    final = agent.frames[-1]
    done = [s for s in agent.level_stats if s.get("completed")]
    level_actions = [s["actions"] for s in done]
    return {
        "game": job["game"],
        "label": job["label"],
        "config": agent.config,
        "seed": job["seed"],
        "rho": agent.rho,
        "q": agent.q,
        "tags": job["tags"],
        "levels_completed": int(final.levels_completed),
        "win_levels": agent.win_levels,
        "state": final.state.value,
        "actions": agent.steps,
        "probes": agent.probes_total,
        "probe_budget": agent.probe_budget,
        "score_scorecard": getattr(sc, "score", None),
        "score_rhae": rhae(level_actions, int(final.levels_completed), job.get("baseline")),
        "baseline": job.get("baseline"),
        "levels": agent.level_stats,
        "hud_rows": sorted(agent.hud.rows) if agent.hud else [],
        "hud_cols": sorted(agent.hud.cols) if agent.hud else [],
        "errors": agent.errors,
        "seconds": seconds,
    }


def q_for(game: str, tags: list[str], spec: str | None) -> str | None:
    if spec is None:
        return None
    try:
        return str(float(spec))
    except ValueError:
        pass
    table = json.loads(Path(spec).read_text())
    for key in [game] + list(tags):
        if key in table:
            return str(float(table[key]))
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", default="", help="comma list of short ids; default: all selected games")
    ap.add_argument("--configs", default="A,B,C,CU")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--max-steps", type=int, default=15000)
    ap.add_argument("--jobs", type=int, default=1, help="parallel worker processes")
    ap.add_argument("--rho", default=None,
                    help="ARC_RHO for C, C1 and CU; a comma list runs one sweep point per value")
    ap.add_argument("--q", default=None,
                    help="ARC_Q for C: a number, a JSON file (game/tag -> q), or 'auto' (from B)")
    ap.add_argument("--split", default="all", choices=["all", "design", "heldout"],
                    help="restrict real games to the frozen design or held-out split")
    ap.add_argument("--tags", default="", help="only games carrying all these metadata tags")
    ap.add_argument("--env-dir", default=str(ROOT / "environment_files"))
    ap.add_argument("--no-step-logs", action="store_true", help="keep only per-game summaries")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    env_dir = Path(args.env_dir).resolve()
    cached = local_games(env_dir)
    want_tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    def tags_of(g: str) -> list[str]:
        return list(cached[g].get("tags") or [])

    if want_tags:
        pool = [g for g in sorted(cached) if all(t in tags_of(g) for t in want_tags)]
    else:
        pool = [g for g in sorted(cached) if "synthetic" not in tags_of(g)]
    games = [g.strip() for g in args.games.split(",") if g.strip()] or pool
    missing = [g for g in games if g not in cached]
    if missing:
        raise SystemExit(f"not cached locally: {missing}. Run `make play-local STEPS=10` once first.")
    if args.split != "all":
        real = [g for g in sorted(cached) if "synthetic" not in tags_of(g)]
        chosen = set(load_split(real)[args.split])
        games = [g for g in games if g in chosen]
    labels = [c.strip().upper() for c in args.configs.split(",") if c.strip()]
    labels = ["CU" if c in ("C'", "CP") else c for c in labels]
    seeds = [int(s) for s in args.seeds.split(",")]
    out = Path(args.out or ROOT / "runs" / time.strftime("%Y%m%d-%H%M%S"))
    (out / "logs").mkdir(parents=True, exist_ok=True)
    rhos = [r.strip() for r in args.rho.split(",")] if args.rho else [None]
    log_steps = "0" if args.no_step_logs else "1"

    def job(game: str, label: str, seed: int, rho: str | None,
            budget: int | None = None) -> dict:
        env = {"ARC_LOG_STEPS": log_steps}
        tag = label
        if label in ("C", "C1", "CU") and rho is not None:
            env["ARC_RHO"] = rho
            tag = f"{label}_rho{rho}"
        if label == "C1":
            env["ARC_Q"] = "1.0"
        elif label == "C":
            q = q_for(game, tags_of(game), args.q)
            if q is not None:
                env["ARC_Q"] = q
        if budget is not None:
            env["ARC_PROBE_BUDGET"] = str(budget)
        return {"game": game, "label": label, "seed": seed, "env": env, "env_dir": str(env_dir),
                "max_steps": args.max_steps, "log_dir": str(out / "logs" / tag),
                "tags": tags_of(game), "baseline": cached[game].get("baseline_actions")}

    rows: list[dict] = []
    results = out / "results.jsonl"

    def run_batch(jobs: list[dict]) -> None:
        with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as pool_:
            futs = {pool_.submit(run_one, j): j for j in jobs}
            for f in as_completed(futs):
                j = futs[f]
                try:
                    row = f.result()
                except Exception as e:  # keep going; record the failure
                    row = {"game": j["game"], "label": j["label"], "seed": j["seed"], "error": repr(e)}
                rows.append(row)
                with results.open("a") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                if "error" in row:
                    print(f"{j['game']:6} {j['label']:2} s{j['seed']}  ERROR {row['error']}", flush=True)
                else:
                    sr = row["score_rhae"]
                    print(f"{row['game']:6} {row['label']:2} s{row['seed']}  levels {row['levels_completed']}/"
                          f"{row['win_levels']}  actions {row['actions']:5d}  probes {row['probes']:4d}  "
                          f"RHAE {sr if sr is None else round(sr, 3)}  {row['seconds']}s", flush=True)

    if args.q == "auto":
        if "B" not in labels:
            raise SystemExit("--q auto needs B in --configs")
        run_batch([job(g, b, s, None) for b in labels if b in ("A", "B") for g in games for s in seeds])
        bs = [r for r in rows if r.get("label") == "B" and "error" not in r]
        done = sum(r["levels_completed"] for r in bs)
        tried = sum(r["levels_completed"] + (0 if r["state"] == "WIN" else 1) for r in bs)
        args.q = str(round(done / tried, 4) if tried else 1.0)
        print(f"q (auto, from B) = {args.q}: {done} levels completed of {tried} attempted", flush=True)
        (out / "q_auto.json").write_text(json.dumps({"q": float(args.q), "completed": done, "attempted": tried}))
        first_labels = [c for c in labels if c not in ("A", "B", "CU")]
    else:
        first_labels = [c for c in labels if c != "CU"]
    first = []
    for label in first_labels:
        for rho in (rhos if label in ("C", "C1") else [None]):
            first += [job(g, label, s, rho) for g in games for s in seeds]
    run_batch(first)
    if "CU" in labels:
        for rho in rhos:
            want = None if rho is None else float(rho)
            probes = {(r["game"], r["seed"]): r["probes"] for r in rows
                      if r.get("label") == "C" and "error" not in r
                      and (want is None or abs(r["rho"] - want) < 1e-12)}
            if not probes:
                print("CU needs C runs for the same games, seeds and rho; using ARC_UNIFORM_PROBES")
            run_batch([job(g, "CU", s, rho, probes.get((g, s))) for g in games for s in seeds])

    print("\nmean RHAE (percent) by config")
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        if "error" in r:
            continue
        key = (r["label"], r["rho"] if r["label"] in ("C", "C1", "CU") else None)
        groups.setdefault(key, []).append(r)
    for (c, rho), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        vals = [r["score_rhae"] or 0.0 for r in rs]
        lv = [r["levels_completed"] for r in rs]
        label = c if rho is None else f"{c} rho={rho:g}"
        print(f"  {label:16}  {sum(vals) / len(vals):7.3f}   levels/run {sum(lv) / len(lv):5.2f}"
              f"   runs {len(vals)}")
    print(f"\nresults: {results}")


if __name__ == "__main__":
    main()
