"""Check the open-room games: every level is solved by its stored shortest
solution in exactly the baseline number of actions, the whole game ends in
WIN, and from level 3 on the exit cannot be reached without the switch
(while in levels 1-2 it can).

usage: python scripts/verify_synthetic.py <env_dir> [game ids comma]
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "ARC-AGI-3-Agents"))


def check(env_dir: Path, gid: str, arc) -> list[str]:
    from arcengine import GameAction
    src = (env_dir / gid / "0001" / f"{gid}.py").read_text()
    ns: dict = {}
    exec(compile(src, gid, "exec"), ns)
    problems = []
    for lv in range(ns["N_LEVELS"]):
        wall, start, exit_, door, gap, blocking, _, _ = ns["_layout"](lv + 1)
        free = exit_ in ns["_bfs"](wall, start, blocked={door})
        if blocking == free:
            problems.append(f"level {lv + 1}: exit reachable without switch = {free}")
    env = arc.make(gid)
    frame = env.reset()
    for lv, sol in enumerate(ns["SOLUTIONS"]):
        if len(sol) != ns["BASELINE"][lv]:
            problems.append(f"level {lv + 1}: solution {len(sol)} != baseline {ns['BASELINE'][lv]}")
        for step in sol:
            if step[0] == "click":
                grid = np.array(frame.frame[-1])
                ys, xs = np.nonzero(grid == ns["SWITCH"])
                if len(xs) == 0:
                    problems.append(f"level {lv + 1}: switch not visible")
                    break
                frame = env.step(GameAction.ACTION6, {"x": int(xs[0]), "y": int(ys[0])})
            else:
                frame = env.step(getattr(GameAction, f"ACTION{step[1]}"))
        if frame.levels_completed != lv + 1:
            problems.append(f"level {lv + 1}: not completed by its solution "
                            f"(levels_completed {frame.levels_completed})")
            break
    if not problems and frame.state.value != "WIN":
        problems.append(f"final state {frame.state.value}")
    return problems


def main() -> None:
    env_dir = Path(sys.argv[1]).resolve()
    want = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    logging.basicConfig(level=logging.WARNING)
    import arc_agi
    from arc_agi import OperationMode
    arc = arc_agi.Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(env_dir))
    arc.logger.setLevel(logging.WARNING)
    for name in ("arc_agi", "arc_agi.scorecard", "arc_agi.base"):
        logging.getLogger(name).setLevel(logging.WARNING)
    bad = 0
    for meta in sorted(env_dir.rglob("metadata.json")):
        gid = json.loads(meta.read_text())["game_id"].split("-")[0]
        if want and gid not in want:
            continue
        problems = check(env_dir, gid, arc)
        bad += bool(problems)
        print(f"{gid}: {'ok' if not problems else '; '.join(problems)}")
    print("all ok" if not bad else f"{bad} games with problems")


if __name__ == "__main__":
    main()
