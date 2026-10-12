
import random
from collections import deque

from arcengine import ARCBaseGame, BlockingMode, Camera, GameAction, InteractionMode, Level, Sprite

N_CELLS = 20
SEED = 3507
N_LEVELS = 6
BLOCK_FROM = 3          # from this level on the door is the only way to the exit
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
    px = [[WALL if v else -1 for v in row] for row in wall]
    sprites = [Sprite(pixels=px, name="walls", blocking=BlockingMode.PIXEL_PERFECT,
                      interaction=InteractionMode.TANGIBLE, layer=-1),
               _block(AVATAR, "player").set_position(*start),
               _block(EXIT, "exit").set_position(*exit_),
               _block(DOOR, "door", tags=("door",)).set_position(*door),
               _block(SWITCH, "switch", tags=("switch",), layer=1).set_position(*switch_at)]
    for i, (color, at) in enumerate(zip(DECOYS, decoys_at)):
        sprites.append(_block(color, f"decoy{i}", tags=("decoy",), layer=1).set_position(*at))
    sol = _solution(wall, start, exit_, door, blocking)
    g = len(wall)
    return Level(sprites=sprites, grid_size=(g, g)), len(sol), sol


_BUILT = [build_level(i + 1) for i in range(N_LEVELS)]
LEVELS = [lv for lv, _, _ in _BUILT]
BASELINE = [b for _, b, _ in _BUILT]
SOLUTIONS = [s for _, _, s in _BUILT]


class R307(ARCBaseGame):
    def __init__(self, seed: int = 0) -> None:
        g = N_CELLS + 2
        camera = Camera(width=g, height=g, background=FLOOR, letter_box=3)
        super().__init__(game_id="r307", levels=LEVELS, camera=camera,
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
