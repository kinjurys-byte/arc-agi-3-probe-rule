"""Generate the open-room suite used to test the probe rule (round 2).

Same objects and rules as scripts/make_synthetic.py (avatar, exit, door,
switch, three decoys, ACTION5 does nothing), but each level is an open room
of n x n floor tiles instead of a maze. The avatar starts near the centre
with all four directions open, so an explorer that has learned the four
moves is not stuck until it has covered the room. In a maze it is stuck in
the first dead end, and then tries every click it has not tried yet, which
teaches it the switch for free.

The exit sits in a small walled pen in one corner with two entrances, one of
them closed by the door. In levels 1-2 the other entrance is open, so the
switch is never needed. From level 3 on it is walled up and the door is the
only way in. Knowing the switch before level 3 therefore saves exploring
the whole room once.

Game ids are r<d><kk>: d = difficulty index, kk = instance. Instances 00-03
are evaluation games, 05-07 calibration games (tags "eval" / "calib").
Each game module also defines SOLUTIONS, a shortest action sequence per
level, used by scripts/verify_synthetic.py.

usage: python scripts/make_rooms.py --sizes 6,10,14,18 --out rooms/environment_files
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GAME_SRC = r'''
import random
from collections import deque

from arcengine import ARCBaseGame, BlockingMode, Camera, GameAction, InteractionMode, Level, Sprite

N_CELLS = __N__
SEED = __SEED__
N_LEVELS = 6
BLOCK_FROM = 3          # from this level on the door is the only way to the exit
DOOR_FROM = __DOOR_FROM__           # levels before this have no door sprite (ablation)
WALL, FLOOR, AVATAR, EXIT, DOOR, SWITCH, SWITCH_ON = 5, 0, 8, 9, 4, 10, 2
DECOYS = (6, 13, 14)
MOVES = {GameAction.ACTION1: (0, -1), GameAction.ACTION2: (0, 1),
         GameAction.ACTION3: (-1, 0), GameAction.ACTION4: (1, 0)}
STEPS = {(0, -1): 1, (0, 1): 2, (-1, 0): 3, (1, 0): 4}


def _bfs(wall, start, blocked=()):
    g = len(wall)
    prev = {start: None}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < g and 0 <= ny < g and not wall[ny][nx] and (nx, ny) not in prev \
                    and (nx, ny) not in blocked:
                prev[(nx, ny)] = (x, y)
                q.append((nx, ny))
    return prev


def _path(prev, end):
    out = []
    while end is not None:
        out.append(end)
        end = prev[end]
    return out[::-1]


def _block(color, name, tags=(), layer=0):
    return Sprite(pixels=[[color]], name=name, blocking=BlockingMode.BOUNDING_BOX,
                  interaction=InteractionMode.TANGIBLE, tags=list(tags), layer=layer)


def _layout(level_no):
    rng = random.Random(SEED * 1000 + level_no)
    g = N_CELLS + 2
    wall = [[1 if x in (0, g - 1) or y in (0, g - 1) else 0 for x in range(g)] for y in range(g)]
    lo, hi = 2, g - 3
    ex, ey = rng.choice([(lo, lo), (hi, lo), (lo, hi), (hi, hi)])
    ring = [(ex + dx, ey + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]
    for x, y in ring:
        wall[y][x] = 1
    sx = 1 if ex == lo else -1                     # from the exit towards the room
    sy = 1 if ey == lo else -1
    entrances = [(ex + sx, ey), (ex, ey + sy)]
    rng.shuffle(entrances)
    door, gap = entrances
    blocking = level_no >= BLOCK_FROM
    wall[door[1]][door[0]] = 0                     # floor under the door sprite
    if not blocking:
        wall[gap[1]][gap[0]] = 0
    pen = set(ring) | {(ex, ey)}
    c = (g - 1) // 2

    def open4(t):
        return all(not wall[t[1] + dy][t[0] + dx] and (t[0] + dx, t[1] + dy) not in pen
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    cands = sorted((max(abs(x - c), abs(y - c)), x, y) for y in range(1, g - 1) for x in range(1, g - 1)
                   if not wall[y][x] and (x, y) not in pen and open4((x, y)))
    near = [(x, y) for d, x, y in cands if d <= max(1, cands[0][0])]
    start = rng.choice(near)
    border = [(x, 0) for x in range(1, g - 1)] + [(x, g - 1) for x in range(1, g - 1)] \
        + [(0, y) for y in range(1, g - 1)] + [(g - 1, y) for y in range(1, g - 1)]
    border = [t for t in border if all(max(abs(t[0] - p[0]), abs(t[1] - p[1])) > 1 for p in pen)]
    rng.shuffle(border)
    return wall, start, (ex, ey), door, gap, blocking, border[0], border[1:4]


def _solution(wall, start, exit_, door, blocking):
    """Shortest action list: ("click",) for the switch, then moves."""
    best = None
    for use_switch in ((True,) if blocking else (False, True)):
        prev = _bfs(wall, start, blocked=() if use_switch else {door})
        if exit_ not in prev:
            continue
        cells = _path(prev, exit_)
        acts = ([("click",)] if use_switch else []) + \
            [("move", STEPS[(b[0] - a[0], b[1] - a[1])]) for a, b in zip(cells, cells[1:])]
        if best is None or len(acts) < len(best):
            best = acts
    return best


def build_level(level_no):
    wall, start, exit_, door, gap, blocking, switch_at, decoys_at = _layout(level_no)
    has_door = level_no >= DOOR_FROM
    px = [[WALL if v else -1 for v in row] for row in wall]
    sprites = [Sprite(pixels=px, name="walls", blocking=BlockingMode.PIXEL_PERFECT,
                      interaction=InteractionMode.TANGIBLE, layer=-1),
               _block(AVATAR, "player").set_position(*start),
               _block(EXIT, "exit").set_position(*exit_)]
    if has_door:
        sprites.append(_block(DOOR, "door", tags=("door",)).set_position(*door))
    sprites.append(_block(SWITCH, "switch", tags=("switch",), layer=1).set_position(*switch_at))
    for i, (color, at) in enumerate(zip(DECOYS, decoys_at)):
        sprites.append(_block(color, f"decoy{i}", tags=("decoy",), layer=1).set_position(*at))
    sol = _solution(wall, start, exit_, door if has_door else None, blocking)
    g = len(wall)
    return Level(sprites=sprites, grid_size=(g, g)), len(sol), sol


_BUILT = [build_level(i + 1) for i in range(N_LEVELS)]
LEVELS = [lv for lv, _, _ in _BUILT]
BASELINE = [b for _, b, _ in _BUILT]
SOLUTIONS = [s for _, _, s in _BUILT]


class __CLASS__(ARCBaseGame):
    def __init__(self, seed: int = 0) -> None:
        g = N_CELLS + 2
        camera = Camera(width=g, height=g, background=FLOOR, letter_box=3)
        super().__init__(game_id="__ID__", levels=LEVELS, camera=camera,
                         available_actions=[1, 2, 3, 4, 5, 6])

    def step(self) -> None:
        aid = self.action.id
        if aid == GameAction.ACTION6:
            pos = self.camera.display_to_grid(int(self.action.data.get("x", 0)),
                                              int(self.action.data.get("y", 0)))
            if pos is not None:
                s = self.current_level.get_sprite_at(pos[0], pos[1], tag="switch")
                if s is not None and int(s.pixels[0][0]) == SWITCH:
                    for d in self.current_level.get_sprites_by_tag("door"):
                        self.current_level.remove_sprite(d)
                    s.color_remap(SWITCH, SWITCH_ON)
        elif aid in MOVES:
            dx, dy = MOVES[aid]
            hit = self.try_move("player", dx, dy)
            if hit and any(sp.name == "exit" for sp in hit):
                self.next_level()
        self.complete_action()
'''


def write_game(out: Path, game_id: str, n: int, seed: int, tags: list[str], door_from: int = 1) -> list[int]:
    cls = game_id[0].upper() + game_id[1:4]
    src = (GAME_SRC.replace("__N__", str(n)).replace("__SEED__", str(seed))
           .replace("__CLASS__", cls).replace("__ID__", game_id).replace("__DOOR_FROM__", str(door_from)))
    ns: dict = {}
    exec(compile(src, game_id, "exec"), ns)  # build once to get the baselines
    d = out / game_id / "0001"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{game_id}.py").write_text(src)
    meta = {"game_id": f"{game_id}-0001", "title": f"synthetic switch room n={n}",
            "class_name": cls, "baseline_actions": ns["BASELINE"], "tags": tags}
    (d / "metadata.json").write_text(json.dumps(meta, indent=1))
    return ns["BASELINE"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", default="6,10,14,18", help="room cells per side for difficulty 1, 2, ...")
    ap.add_argument("--out", default=str(ROOT / "rooms" / "environment_files"))
    ap.add_argument("--eval", default="0,1,2,3", help="evaluation instance numbers")
    ap.add_argument("--calib", default="5,6,7", help="calibration instance numbers")
    ap.add_argument("--first-difficulty", type=int, default=1,
                    help="difficulty index of the first size (for pilots of single sizes)")
    ap.add_argument("--door-from", type=int, default=1,
                    help="first level with a door sprite; 3 removes the redundant door of levels 1-2 (ablation)")
    args = ap.parse_args()
    out = Path(args.out)
    sizes = [int(s) for s in args.sizes.split(",")]
    for d, n in enumerate(sizes, start=args.first_difficulty):
        for role, ks in (("eval", args.eval), ("calib", args.calib)):
            for k in (int(x) for x in ks.split(",") if x):
                gid = f"r{d}{k:02d}"
                tags = ["synthetic", "rooms", f"d{d}", role] + (["ablation"] if args.door_from > 1 else [])
                base = write_game(out, gid, n, seed=1000 * d + k + 500, tags=tags, door_from=args.door_from)
                print(f"{gid}  n={n:2d}  {role:5}  baseline {base}")


if __name__ == "__main__":
    main()
