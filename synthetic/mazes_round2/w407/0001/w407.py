
import random
from collections import deque

from arcengine import ARCBaseGame, BlockingMode, Camera, GameAction, InteractionMode, Level, Sprite

N_CELLS = 12
SEED = 4007
N_LEVELS = 6
BLOCK_FROM = 3          # from this level on the door blocks the way to the exit
WALL, FLOOR, AVATAR, EXIT, DOOR, SWITCH, SWITCH_ON = 5, 0, 8, 9, 4, 10, 2
DECOYS = (6, 13, 14)
MOVES = {GameAction.ACTION1: (0, -1), GameAction.ACTION2: (0, 1),
         GameAction.ACTION3: (-1, 0), GameAction.ACTION4: (1, 0)}


def _maze(rng, n):
    g = 2 * n + 1
    wall = [[1] * g for _ in range(g)]
    stack = [(0, 0)]
    seen = {(0, 0)}
    wall[1][1] = 0
    while stack:
        cx, cy = stack[-1]
        nb = [(cx + dx, cy + dy, dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
              if 0 <= cx + dx < n and 0 <= cy + dy < n and (cx + dx, cy + dy) not in seen]
        if not nb:
            stack.pop()
            continue
        nx, ny, dx, dy = rng.choice(nb)
        wall[2 * cy + 1 + dy][2 * cx + 1 + dx] = 0
        wall[2 * ny + 1][2 * nx + 1] = 0
        seen.add((nx, ny))
        stack.append((nx, ny))
    return wall


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


def _layout(rng, level_no):
    """Maze, start, exit, main path and door tile; None if this maze has no
    suitable door position (then the caller draws another maze)."""
    wall = _maze(rng, N_CELLS)
    start = (1, 1)
    prev = _bfs(wall, start)
    exit_ = max(prev, key=lambda t: len(_path(prev, t)))
    main = _path(prev, exit_)
    on_main = set(main)
    passages = [t for t in prev if (t[0] % 2) != (t[1] % 2)]   # tiles between two cells
    if level_no >= BLOCK_FROM:
        lo = int(0.55 * len(main))
        hi = max(int(0.8 * len(main)), lo + 1)
        cand = [t for t in main[lo:hi] if t in passages] or [t for t in main[1:-1] if t in passages]
    else:
        cand = [t for t in passages if t not in on_main
                and len(prev) - len(_bfs(wall, start, blocked={t})) >= 3]
    if not cand:
        return None
    return wall, start, exit_, main, prev, rng.choice(cand)


def build_level(level_no):
    rng = random.Random(SEED * 1000 + level_no)
    lay = None
    while lay is None:
        lay = _layout(rng, level_no)
    wall, start, exit_, main, prev, door = lay
    blocking = level_no >= BLOCK_FROM
    pre = _bfs(wall, start, blocked={door})          # floor reachable before opening the door
    g = len(wall)
    walls_next = sorted({(x + dx, y + dy) for (x, y) in pre for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                         if 0 <= x + dx < g and 0 <= y + dy < g and wall[y + dy][x + dx]})
    rng.shuffle(walls_next)
    switch_at, decoys_at = walls_next[0], walls_next[1:4]
    px = [[WALL if v else -1 for v in row] for row in wall]
    sprites = [Sprite(pixels=px, name="walls", blocking=BlockingMode.PIXEL_PERFECT,
                      interaction=InteractionMode.TANGIBLE, layer=-1),
               _block(AVATAR, "player").set_position(*start),
               _block(EXIT, "exit").set_position(*exit_),
               _block(DOOR, "door", tags=("door",)).set_position(*door),
               _block(SWITCH, "switch", tags=("switch",), layer=1).set_position(*switch_at)]
    for i, (color, at) in enumerate(zip(DECOYS, decoys_at)):
        sprites.append(_block(color, f"decoy{i}", tags=("decoy",), layer=1).set_position(*at))
    baseline = len(main) - 1 + (1 if blocking else 0)
    return Level(sprites=sprites, grid_size=(g, g)), baseline


_BUILT = [build_level(i + 1) for i in range(N_LEVELS)]
LEVELS = [lv for lv, _ in _BUILT]
BASELINE = [b for _, b in _BUILT]


class W407(ARCBaseGame):
    def __init__(self, seed: int = 0) -> None:
        g = 2 * N_CELLS + 1
        camera = Camera(width=g, height=g, background=FLOOR, letter_box=3)
        super().__init__(game_id="w407", levels=LEVELS, camera=camera,
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
