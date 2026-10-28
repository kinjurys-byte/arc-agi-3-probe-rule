"""Generate the short-first-level suite (fourth family, 2026-10-28).

The games are the 16x16 open rooms of scripts/make_rooms.py (same objects,
rules, exit pen, switch and decoys; the game source is that file's, with one
step added). The only change is level 1: with --first-dist K > 0 its room shrinks to the
floor cells at most K moves from the exit (through the open pen entrance),
the rest turned into wall, and the avatar starts K moves from the exit. Level
1 is then a short pocket that any explorer clears in a few times the human
actions, as in the easy first levels of many public games. Levels 2 to 6 are
exactly those of the open room with the same seed, so the two arms of a base
room differ only in level 1.

This makes the first level the one where an action is dearest: by the score,
an action in level j costs in proportion to j / (a_j r_j^2), with a_j the
actions spent there and r_j = a_j / h_j. Always probing (CA) then spends its
probes where they cost most, while the probe rule (C) waits until a level has
run long enough. The suite tests whether that restraint pays.

Game ids are f<d><kk>: d = arm index (d1, d2, ... use the distances in
--first-dist; 0 keeps the open-room start), kk = instance. Games with the
same instance number share their base room. Tags: synthetic, short, d<d> and
the role (eval, calib or pilot).

usage: python scripts/make_short.py --size 16 --first-dist 0,3 \\
           --eval 50,51 --calib 5,6 --out synthetic/short
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_rooms import GAME_SRC as ROOM_SRC  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

SHORT_FN = r'''

def _short_start(wall, pen, exit_, door, start, level_no):
    """Shrink the level-1 room to the floor cells at most FIRST_DIST moves from
    the exit with the door closed (so through the open entrance), walling the
    rest, and start the avatar FIRST_DIST moves from the exit. Uses its own
    random stream, so the switch, decoys and later levels are unchanged."""
    prev = _bfs(wall, exit_, blocked={door})
    dist = {}
    for cell in prev:
        n, c = 0, cell
        while prev[c] is not None:
            c = prev[c]
            n += 1
        dist[cell] = n
    g = len(wall)
    for y in range(1, g - 1):
        for x in range(1, g - 1):
            if not wall[y][x] and (x, y) not in pen and dist.get((x, y), FIRST_DIST + 1) > FIRST_DIST:
                wall[y][x] = 1
    cands = sorted(c for c, n in dist.items() if n == FIRST_DIST and c not in pen)
    if not cands:
        return start
    return random.Random(SEED * 1000 + level_no + 900000).choice(cands)

'''

ANCHOR_DEF = "\n\ndef _layout(level_no):"
ANCHOR_START = "    start = rng.choice(near)\n"
NEW_START = ("    start = rng.choice(near)\n"
             "    if level_no == 1 and FIRST_DIST > 0:\n"
             "        start = _short_start(wall, pen, (ex, ey), door, start, level_no)\n")
ANCHOR_CONST = "N_LEVELS = 6\n"
NEW_CONST = "N_LEVELS = 6\nFIRST_DIST = __FIRST_DIST__          # level 1 keeps only floor this many moves from the exit (0: open room)\n"


def game_source() -> str:
    src = ROOM_SRC
    for old, new in ((ANCHOR_CONST, NEW_CONST), (ANCHOR_START, NEW_START),
                     (ANCHOR_DEF, SHORT_FN.rstrip("\n") + "\n" + ANCHOR_DEF)):
        assert src.count(old) == 1, f"anchor not found once in make_rooms.GAME_SRC: {old[:40]!r}"
        src = src.replace(old, new)
    return src


def write_game(out: Path, game_id: str, n: int, first_dist: int, seed: int, tags: list[str]) -> list[int]:
    cls = game_id[0].upper() + game_id[1:4]
    src = (game_source().replace("__N__", str(n)).replace("__SEED__", str(seed))
           .replace("__CLASS__", cls).replace("__ID__", game_id).replace("__DOOR_FROM__", "1")
           .replace("__FIRST_DIST__", str(int(first_dist))))
    ns: dict = {}
    exec(compile(src, game_id, "exec"), ns)  # build once to get the baselines
    d = out / game_id / "0001"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{game_id}.py").write_text(src)
    meta = {"game_id": f"{game_id}-0001", "title": f"synthetic room n={n}, level-1 pocket of radius {first_dist} around the exit",
            "class_name": cls, "baseline_actions": ns["BASELINE"], "tags": tags, "first_dist": first_dist}
    (d / "metadata.json").write_text(json.dumps(meta, indent=1))
    return ns["BASELINE"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=16, help="room cells per side, all arms")
    ap.add_argument("--first-dist", default="0,3", help="level-1 pocket radius in moves from the exit for arm 1, 2, ... (0: the open room)")
    ap.add_argument("--out", default=str(ROOT / "synthetic" / "short"))
    ap.add_argument("--eval", default="", help="evaluation instance numbers")
    ap.add_argument("--calib", default="", help="calibration instance numbers")
    ap.add_argument("--pilot", default="", help="pilot instance numbers (design only)")
    args = ap.parse_args()
    out = Path(args.out)
    dists = [int(s) for s in args.first_dist.split(",")]
    for d, k_dist in enumerate(dists, start=1):
        for role, ks in (("eval", args.eval), ("calib", args.calib), ("pilot", args.pilot)):
            for k in (int(x) for x in ks.split(",") if x):
                gid = f"f{d}{k:02d}"
                tags = ["synthetic", "short", f"d{d}", role]
                base = write_game(out, gid, args.size, k_dist, seed=k + 800, tags=tags)
                print(f"{gid}  first_dist={k_dist}  {role:5}  baseline {base}")


if __name__ == "__main__":
    main()
