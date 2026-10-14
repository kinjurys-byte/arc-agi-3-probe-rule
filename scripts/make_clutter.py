"""Generate the cluttered-room suite (third family, 2026-10-14).

The games are the open rooms of scripts/make_rooms.py (same objects, rules,
exit pen, switch and decoys; the game source is that file's, with one step
added), except that a share of the room floor is turned into wall, one random
cell at a time, skipping any cell whose removal would split the floor. The
start, its four neighbours and the cell in front of each pen entrance stay
free, so in levels 1-2 the exit can still be reached without the switch and
from level 3 on only through the door.

Clutter makes dead ends. An explorer that knows only some moves, or has
covered a pocket, is then stuck more often, and when stuck it tries the
clicks it has not tried, which teaches it the switch for free (as in the
mazes of scripts/make_synthetic.py). All difficulties have one room size;
the difficulty axis is the clutter share: d1, d2, ... use the shares in
--clutter. Games with the same instance number share their base room (the
layout seed does not depend on the difficulty) and the random order in which
cells are tried, so the clutter of a lower share is part of that of a higher
one: within an instance, only the clutter differs. With share 0 a level is
exactly the open-room level of the same size and seed.

Game ids are k<d><kk>: d = difficulty index, kk = instance. Tags: synthetic,
clutter, d<d> and the role (eval, calib or pilot).

usage: python scripts/make_clutter.py --size 16 --clutter 0,0.15,0.3,0.45 \\
           --eval 0,1,2,3 --calib 5,6,7 --out synthetic/clutter
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_rooms import GAME_SRC as ROOM_SRC  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CLUTTER_FN = r'''

def _connected(start, room):
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            t = (x + dx, y + dy)
            if t in room and t not in seen:
                seen.add(t)
                q.append(t)
    return len(seen) == len(room)


def _clutter(wall, start, pen, entrances, exit_, level_no):
    """Turn a share CLUTTER of the room floor (outside the exit pen) into wall,
    trying cells in random order and skipping any whose removal would split
    the room floor. The start, its four neighbours and the floor cell in
    front of each pen entrance stay free."""
    rng = random.Random(SEED * 1000 + level_no + 500000)
    g = len(wall)
    ex, ey = exit_
    keep = {start} | {(start[0] + dx, start[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
    keep |= {(2 * x - ex, 2 * y - ey) for x, y in entrances}
    room = {(x, y) for y in range(1, g - 1) for x in range(1, g - 1) if not wall[y][x] and (x, y) not in pen}
    size = len(room)
    target = round(CLUTTER * size)
    cand = sorted(room - keep)
    rng.shuffle(cand)
    placed = 0
    for x, y in cand:
        if placed >= target:
            break
        wall[y][x] = 1
        room.discard((x, y))
        if _connected(start, room):
            placed += 1
        else:
            wall[y][x] = 0
            room.add((x, y))
    PLACED[level_no] = (placed, target, size)

'''

ANCHOR_DEF = "\n\ndef _layout(level_no):"
ANCHOR_RET = ("    rng.shuffle(border)\n"
              "    return wall, start, (ex, ey), door, gap, blocking, border[0], border[1:4]\n")
NEW_RET = ("    rng.shuffle(border)\n"
           "    if CLUTTER > 0:\n"
           "        _clutter(wall, start, pen, (door, gap), (ex, ey), level_no)\n"
           "    return wall, start, (ex, ey), door, gap, blocking, border[0], border[1:4]\n")
ANCHOR_CONST = "N_LEVELS = 6\n"
NEW_CONST = "N_LEVELS = 6\nCLUTTER = __CLUTTER__          # share of the room floor turned into wall\nPLACED = {}\n"


def game_source() -> str:
    src = ROOM_SRC
    for old, new in ((ANCHOR_CONST, NEW_CONST), (ANCHOR_RET, NEW_RET),
                     (ANCHOR_DEF, CLUTTER_FN.rstrip("\n") + "\n" + ANCHOR_DEF)):
        assert src.count(old) == 1, f"anchor not found once in make_rooms.GAME_SRC: {old[:40]!r}"
        src = src.replace(old, new)
    return src


def write_game(out: Path, game_id: str, n: int, clutter: float, seed: int, tags: list[str]) -> tuple:
    cls = game_id[0].upper() + game_id[1:4]
    src = (game_source().replace("__N__", str(n)).replace("__SEED__", str(seed))
           .replace("__CLASS__", cls).replace("__ID__", game_id).replace("__DOOR_FROM__", "1")
           .replace("__CLUTTER__", repr(float(clutter))))
    ns: dict = {}
    exec(compile(src, game_id, "exec"), ns)  # build once to get the baselines
    d = out / game_id / "0001"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{game_id}.py").write_text(src)
    placed = [ns["PLACED"].get(i + 1, (0, 0, 0)) for i in range(ns["N_LEVELS"])]
    shares = [round(p / s, 3) if s else 0.0 for p, _, s in placed]
    meta = {"game_id": f"{game_id}-0001", "title": f"synthetic cluttered room n={n} clutter={clutter}",
            "class_name": cls, "baseline_actions": ns["BASELINE"], "tags": tags,
            "clutter": clutter, "clutter_share_by_level": shares}
    (d / "metadata.json").write_text(json.dumps(meta, indent=1))
    return ns["BASELINE"], shares


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=16, help="room cells per side, all difficulties")
    ap.add_argument("--clutter", default="0,0.15,0.3,0.45", help="clutter share for difficulty 1, 2, ...")
    ap.add_argument("--out", default=str(ROOT / "synthetic" / "clutter"))
    ap.add_argument("--eval", default="0,1,2,3", help="evaluation instance numbers")
    ap.add_argument("--calib", default="5,6,7", help="calibration instance numbers")
    ap.add_argument("--pilot", default="", help="pilot instance numbers (design only)")
    args = ap.parse_args()
    out = Path(args.out)
    shares = [float(s) for s in args.clutter.split(",")]
    for d, c in enumerate(shares, start=1):
        for role, ks in (("eval", args.eval), ("calib", args.calib), ("pilot", args.pilot)):
            for k in (int(x) for x in ks.split(",") if x):
                gid = f"k{d}{k:02d}"
                tags = ["synthetic", "clutter", f"d{d}", role]
                base, got = write_game(out, gid, args.size, c, seed=k + 700, tags=tags)
                print(f"{gid}  clutter {c:.2f} (placed {min(got):.2f}-{max(got):.2f})  {role:5}  baseline {base}")


if __name__ == "__main__":
    main()
