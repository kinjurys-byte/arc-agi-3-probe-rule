"""Level-weighted exploration agent for ARC-AGI-3 (ARC Prize 2026 paper track).

LLM-free and CPU-only. The file depends only on numpy and the official
ARC-AGI-3-Agents framework, so the Kaggle notebook can splice it in as is.

Configurations (environment variable ARC_AGENT_CONFIG, default "C"):

  A    graph explorer; the action-effect table is cleared at every new level
  B    A, but the table is carried across levels                   (H1: B vs A)
  C    B plus the probe rule derived from the RHAE level weights    (H2: C vs C')
  CU   control C': the same number of probes as C, split evenly over levels,
       with quota a level could not use carried forward (aliases: "C'", "CP");
       the budget comes from ARC_PROBE_BUDGETS or ARC_PROBE_BUDGET, otherwise
       ARC_UNIFORM_PROBES per level
  R    trivial control: hold one action until it leaves the frame unchanged
       twice in a row, then move to the next in a fixed cycle (ACTION1-5,
       then a click on the most salient object); no search, table or probes
  K    trivial control: click every object of the current frame once, in
       salience order, then cycle through the simple actions

Optional environment variables:

  ARC_SEED            tie-breaking seed (default 0)
  ARC_RHO             relative saving per settled effect, rho (default 0.0003,
                      calibrated on the 15 public design games, 2026-10-12)
  ARC_RSTAR           target action ratio r* for later levels (default 2.0)
  ARC_Q               chance of completing each further level, q (default 0.5,
                      the completion rate of B on the same design games;
                      q = 1 gives the original, undiscounted rule)
  ARC_K               NONE observations that confirm a no-op click target, k (default 2)
  ARC_K_SIMPLE        the same for ACTION1-5, which walls often block (default 4)
  ARC_R1              efficiency proxy r_hat used in level 1 (default 5.0)
  ARC_LEVEL_CAP       per-level action cap (default 1500)
  ARC_MAX_CLICKS      click candidates kept per state (default 48)
  ARC_RESET_PENALTY   extra cost of a voluntary RESET when planning (default 10)
  ARC_PROBE_BUDGETS   JSON file {"<game>:<seed>" or "<game>": probes} for CU
  ARC_PROBE_BUDGET    total probes per game for CU (overrides the file)
  ARC_UNIFORM_PROBES  per-level quota for CU when no budget is known (default 6)
  ARC_LOG_DIR         if set, write per-step JSONL logs and summary.jsonl here
  ARC_LOG_STEPS       "0" keeps summary.jsonl but skips the per-step logs
  ARC_HUD_THRESH      share of transitions a counter line must change in (default 0.75)
  ARC_PRIOR_MOVES     "1" starts with ACTION1-4 marked as working (ablation only, off by default)
  ARC_RECORD          "1" keeps the framework's per-frame recordings (off by default)
  ARC_DEBUG           "1" re-raises internal errors instead of recovering

Probe rule (paper, Appendix E, with the 2026-10-12 amendment). In level j of
L, with a_j actions already spent there and r_hat the efficiency proxy from
the previous level, an action whose effect is still unknown is tried first
when

    rho * sum_{i>j} i * q^(i-j) / r*^2  >  j / (a_j * r_hat^2),

where q is the chance of completing each further level (q = 1 gives the
original rule). Without probing (A, B, or when the rule says no), actions of
unknown effect are tried only once nothing known to work is left to try.

r_hat = actions used in the previous level / shortest winning path found in
the agent's own graph (human baselines are hidden during play).
"""

from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
import zlib
from collections import deque
from hashlib import blake2b
from typing import Any, Callable, Optional

import numpy as np
from arcengine import FrameData, GameAction, GameState

from agents.agent import Agent

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# constants

CONFIG_ALIASES = {
    "A": "A",
    "B": "B",
    "C": "C",
    "CU": "CU",
    "C'": "CU",
    "CP": "CU",
    "C_PRIME": "CU",
    "UNIFORM": "CU",
    "R": "R",
    "REPEAT": "R",
    "K": "K",
    "CLICK": "K",
}

RESET = ("R",)            # local action id of RESET (only used in plans)
TERMINAL = "<terminal>"   # edge target: the action ended the game
WIN = "<win>"             # edge target: the action completed the level
ACTIVE, UNKNOWN, NOOP = 0, 1, 2
CLASS_NAMES = {ACTIVE: "active", UNKNOWN: "unknown", NOOP: "noop"}
SIMPLE_IDS = (1, 2, 3, 4, 5)   # ACTION7 (undo) is history dependent, not explored
MASK_VALUE = 255
MAX_TIER = 4                   # click tiers 0 (likely buttons) .. 4 (background)
COMMON_SHARE = 0.34            # a colour above this share of the foreground is "common"
MAX_STORED_DIFF = 800          # larger diffs are stored as "always a change"

_FILE_LOCK = threading.Lock()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except ValueError:
        return int(default)


def _to_grid(f: Optional[FrameData]) -> Optional[np.ndarray]:
    """Last (settled) grid of a response as uint8, or None if there is none."""
    if f is None or not f.frame:
        return None
    try:
        a = np.asarray(f.frame[-1], dtype=np.int16)
    except (TypeError, ValueError):
        return None
    if a.ndim != 2 or a.size == 0:
        return None
    return (a & 0xFF).astype(np.uint8)


# --------------------------------------------------------------------------
# connected components (run-length union-find, 4-connectivity)


def _components(grid: np.ndarray, valid: np.ndarray) -> list[dict[str, Any]]:
    h, w = grid.shape
    g = np.where(valid, grid.astype(np.int16), -1)
    rr: list[int] = []
    c0: list[int] = []
    c1: list[int] = []
    col: list[int] = []
    row_start = [0]
    for r in range(h):
        row = g[r]
        cuts = (np.flatnonzero(row[1:] != row[:-1]) + 1).tolist()
        starts = [0] + cuts
        ends = cuts + [w]
        for s, e in zip(starts, ends):
            rr.append(r)
            c0.append(s)
            c1.append(e)
            col.append(int(row[s]))
        row_start.append(len(rr))
    n = len(rr)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for r in range(1, h):
        i, i_end = row_start[r - 1], row_start[r]
        j, j_end = row_start[r], row_start[r + 1]
        while i < i_end and j < j_end:
            if col[i] == col[j] and col[i] >= 0 and c0[i] < c1[j] and c0[j] < c1[i]:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
            if c1[i] < c1[j]:
                i += 1
            elif c1[j] < c1[i]:
                j += 1
            else:
                i += 1
                j += 1

    groups: dict[int, list[int]] = {}
    for idx in range(n):
        if col[idx] >= 0:
            groups.setdefault(find(idx), []).append(idx)

    comps = []
    for runs in groups.values():
        size = 0
        sy = 0.0
        sx = 0.0
        rmin, rmax, cmin, cmax = h, -1, w, -1
        for k in runs:
            ln = c1[k] - c0[k]
            size += ln
            sy += rr[k] * ln
            sx += (c0[k] + c1[k] - 1) * ln / 2.0
            rmin = min(rmin, rr[k])
            rmax = max(rmax, rr[k])
            cmin = min(cmin, c0[k])
            cmax = max(cmax, c1[k] - 1)
        cy, cx = sy / size, sx / size
        best = None
        for k in runs:
            x = int(round(min(max(cx, c0[k]), c1[k] - 1)))
            d = (x - cx) ** 2 + (rr[k] - cy) ** 2
            if best is None or d < best[0]:
                best = (d, x, rr[k])
        shape = sorted((rr[k] - rmin, c0[k] - cmin, c1[k] - cmin) for k in runs)
        shash = zlib.crc32(repr(shape).encode()) & 0xFFFF
        comps.append(
            {
                "color": col[runs[0]],
                "size": size,
                "h": rmax - rmin + 1,
                "w": cmax - cmin + 1,
                "x": best[1],
                "y": best[2],
                "shape": shash,
            }
        )
    return comps


# --------------------------------------------------------------------------
# HUD (move counter) detection


class _Hud:
    """Finds a move counter or energy bar near the frame border and masks it
    out of state identity, so that positions do not look new just because the
    counter ticked. Two tests, either of which adds rows/columns to the mask:

    1. Every-step test: a thin band (1-4 lines) of border rows or columns
       whose colour histogram changes in at least `thresh` of all in-level
       transitions. Avatar motion along a row keeps that row's histogram, so
       an avatar walking along the border does not pass.
    2. Clock test: after a RESET, a border line that shows exactly the same
       content as in an earlier life at the same step count, even though the
       two lives took different actions, while taking 3 or more values over
       time. That is a display driven by the step count, not by the actions,
       and it also catches counters that tick only every few steps.
    3. Reset test: right after a RESET or a restart by the game, the frame
       should equal the level's first frame. Differences confined to a few
       border lines that ordinary moves never change are meta-state such as
       a lives display.

    Rows are read across the full width (with already masked columns blanked)
    and columns only across the middle rows, so a horizontal bar never makes
    the columns it crosses look like a counter, and vice versa. Statistics
    restart whenever the mask grows."""

    CHECKPOINTS = frozenset([8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024])

    def __init__(self, shape: tuple[int, int], zone: int = 10, min_obs: int = 12,
                 thresh: float = 0.75, max_lines: int = 6, max_band: int = 4) -> None:
        self.shape = shape
        h, w = shape
        self.zone = zone
        self.min_obs = min_obs
        self.thresh = _env_float("ARC_HUD_THRESH", thresh)
        self.max_lines = max_lines
        self.max_band = max_band
        self.zrows = [r for r in range(h) if r < zone or r >= h - zone]
        self.zcols = [c for c in range(w) if c < zone or c >= w - zone]
        self.mid = slice(zone, max(zone, h - zone))   # rows used for column features
        self.row_windows = self._windows(self.zrows)
        self.col_windows = self._windows(self.zcols)
        self.mask = np.zeros(shape, dtype=bool)
        self.rows: set[int] = set()
        self.cols: set[int] = set()
        # how often each line changed in ordinary in-level transitions (never
        # reset): lines the player's actions touch are playfield, not meta-state
        self.row_changes = np.zeros(h, dtype=np.int32)
        self.col_changes = np.zeros(w, dtype=np.int32)
        self._restart()

    def _restart(self) -> None:
        self.row_bits: deque[int] = deque(maxlen=400)
        self.col_bits: deque[int] = deque(maxlen=400)
        self.n_updates = 0
        self.lives: list[tuple[list, dict[int, tuple]]] = []
        self.life: dict[int, tuple] = {}
        self.life_actions: list = []
        self.life_valid = False          # becomes True at the next level start or RESET

    def _windows(self, idx: list[int]) -> list[tuple[int, list[int]]]:
        pos = {v: i for i, v in enumerate(idx)}
        out = []
        for size in range(1, self.max_band + 1):
            for start in idx:
                lines = list(range(start, start + size))
                if all(v in pos for v in lines):
                    m = 0
                    for v in lines:
                        m |= 1 << pos[v]
                    out.append((m, lines))
        return out

    def _rows_view(self, grid: np.ndarray) -> np.ndarray:
        if not self.cols:
            return grid
        g = grid.copy()
        g[:, sorted(self.cols)] = MASK_VALUE
        return g

    # test 1 ------------------------------------------------------------
    def update(self, prev: np.ndarray, new: np.ndarray) -> bool:
        """Feed one in-level transition. Returns True if the mask grew."""
        self.n_updates += 1
        changed = prev != new
        self.row_changes += changed.any(axis=1)
        self.col_changes += changed.any(axis=0)
        rb = cb = 0
        pr, nr = self._rows_view(prev), self._rows_view(new)
        rows_changed = (pr != nr).any(axis=1)
        for i, r in enumerate(self.zrows):
            if r not in self.rows and rows_changed[r] and not np.array_equal(
                    np.bincount(pr[r], minlength=256), np.bincount(nr[r], minlength=256)):
                rb |= 1 << i
        pc, nc = prev[self.mid], new[self.mid]
        if pc.size:
            cols_changed = (pc != nc).any(axis=0)
            for i, c in enumerate(self.zcols):
                if c not in self.cols and cols_changed[c] and not np.array_equal(
                        np.bincount(pc[:, c], minlength=256), np.bincount(nc[:, c], minlength=256)):
                    cb |= 1 << i
        self.row_bits.append(rb)
        self.col_bits.append(cb)
        if len(self.row_bits) < self.min_obs or self.n_updates % 4:
            return False
        return self._grow(self._every_step(self.row_bits, self.row_windows),
                          self._every_step(self.col_bits, self.col_windows))

    def _every_step(self, bits: deque, windows: list[tuple[int, list[int]]]) -> set[int]:
        need = self.thresh * len(bits)
        seen = 0
        for b in bits:
            seen |= b
        found: set[int] = set()
        for m, lines in windows:
            if not (m & seen) or found.intersection(lines):
                continue
            if sum(1 for b in bits if b & m) >= need:
                found.update(lines)
        return found

    # test 2 ------------------------------------------------------------
    def new_level(self) -> None:
        self.lives = []
        self.life = {}
        self.life_actions = []
        self.life_valid = True

    def new_life(self) -> None:
        if self.life and self.life_valid:
            self.lives.append((self.life_actions, self.life))
            self.lives = self.lives[-3:]
        self.life = {}
        self.life_actions = []
        self.life_valid = True

    def record(self, t: int, grid: np.ndarray, action: Optional[tuple]) -> bool:
        """Remember border lines at life step t. Returns True if the mask grew."""
        if not self.life_valid:
            return False
        if action is not None:
            self.life_actions.append(action)
        rv = self._rows_view(grid)
        cv = grid[self.mid]
        self.life[t] = (tuple(hash(rv[r].tobytes()) for r in self.zrows),
                        tuple(hash(cv[:, c].tobytes()) for c in self.zcols) if cv.size else ())
        if not self.lives or t not in self.CHECKPOINTS:
            return False
        return self._grow(self._clock(0), self._clock(1) if cv.size else set())

    def _clock(self, axis: int) -> set[int]:
        idx = self.zrows if axis == 0 else self.zcols
        done = self.rows if axis == 0 else self.cols
        n = len(idx)
        agree = [0] * n
        bad = [False] * n
        values: list[set] = [set() for _ in range(n)]   # values seen after divergence
        for actions, other in self.lives:
            d = 0
            m = min(len(actions), len(self.life_actions))
            while d < m and actions[d] == self.life_actions[d]:
                d += 1
            for t, rec in self.life.items():
                if t <= d or t not in other:
                    continue        # identical history so far: no evidence
                orec = other[t]
                for i in range(n):
                    if rec[axis][i] == orec[axis][i]:
                        agree[i] += 1
                        values[i].add(rec[axis][i])
                    else:
                        bad[i] = True
        return {idx[i] for i in range(n)
                if idx[i] not in done and not bad[i] and agree[i] >= 6 and len(values[i]) >= 3}

    # test 3 ------------------------------------------------------------
    def _border_lines(self, ref: np.ndarray, grid: np.ndarray) -> Optional[tuple[set, set]]:
        """(rows, cols) to mask if grid differs from ref only in a few border
        lines; ({}, {}) if they are equal under the mask; None otherwise."""
        if ref.shape != grid.shape:
            return None
        d = (ref != grid) & ~self.mask
        if not d.any():
            return set(), set()
        rows = {int(r) for r in np.flatnonzero(d.any(axis=1))}
        cols = {int(c) for c in np.flatnonzero(d.any(axis=0))}
        quiet_rows = all(self.row_changes[r] == 0 for r in rows)
        quiet_cols = all(self.col_changes[c] == 0 for c in cols)
        if rows <= set(self.zrows) and len(rows) <= self.max_band and quiet_rows:
            return rows, set()
        if cols <= set(self.zcols) and len(cols) <= self.max_band and quiet_cols:
            return set(), cols
        return None

    def _quiet(self) -> np.ndarray:
        """Cells on border lines that ordinary moves have never changed."""
        q = np.zeros(self.shape, dtype=bool)
        for r in self.zrows:
            if self.row_changes[r] == 0 and r not in self.rows:
                q[r, :] = True
        for c in self.zcols:
            if self.col_changes[c] == 0 and c not in self.cols:
                q[:, c] = True
        return q

    def restart_like(self, prev: np.ndarray, new: np.ndarray, start: np.ndarray) -> bool:
        """Did the game restart the level by itself? The new frame equals the
        level's first frame up to quiet border lines, the playfield changed,
        and either a quiet border line (a lives display) changed too or the
        move counter jumped back to its starting value."""
        if not (prev.shape == new.shape == start.shape):
            return False
        if self._border_lines(start, new) is None:
            return False
        d = (prev != new) & ~self.mask
        quiet = self._quiet()
        if not (d & ~quiet).any():
            return False
        if (d & quiet).any():
            return True
        # a masked counter that jumped back: most of the HUD cells that changed
        # now show their level-start values (a lives display may still differ)
        ch = (prev != new) & self.mask
        if not ch.any():
            return False
        back = int(((new == start) & ch).sum())
        return back >= max(1, 0.5 * int(ch.sum()))

    def reset_diff(self, start: np.ndarray, grid: np.ndarray) -> bool:
        """Compare a freshly restarted level with its first frame."""
        lines = self._border_lines(start, grid)
        if not lines or not (lines[0] or lines[1]):
            return False
        return self._grow(lines[0], lines[1])

    # ------------------------------------------------------------------
    def _grow(self, rows: set[int], cols: set[int]) -> bool:
        grew = False
        if rows - self.rows and len(self.rows | rows) <= self.max_lines:
            self.rows |= rows
            grew = True
        if cols - self.cols and len(self.cols | cols) <= self.max_lines:
            self.cols |= cols
            grew = True
        if grew:
            self.mask[:] = False
            for r in self.rows:
                self.mask[r, :] = True
            for c in self.cols:
                self.mask[:, c] = True
            self._restart()          # evidence gathered under the old mask is stale
        return grew


# --------------------------------------------------------------------------
# per-level state graph


class _Cand:
    __slots__ = ("local", "tkey", "sal")

    def __init__(self, local: tuple, tkey: str, sal: tuple) -> None:
        self.local = local
        self.tkey = tkey
        self.sal = sal


class _LevelGraph:
    def __init__(self, index: int) -> None:
        self.index = index                       # levels_completed at level start
        self.frames: dict[str, tuple[tuple[int, int], bytes]] = {}
        self.edges: dict[str, dict[tuple, str]] = {}
        self.cands: dict[str, list[_Cand]] = {}
        self.weak: dict[str, set[tuple]] = {}   # suspected terminal edges
        self.avail: dict[str, tuple[int, ...]] = {}
        self.over: dict[tuple[str, tuple], int] = {}
        self.restarts: dict[tuple[str, tuple], int] = {}   # jumps back to the level start
        self.ends: dict[tuple[str, tuple], int] = {}       # every life end, blamed or not
        self.start: Optional[str] = None
        self.reset_target: Optional[str] = None

    def add(self, nid: str, grid: np.ndarray, avail: tuple[int, ...]) -> None:
        if nid not in self.edges:
            self.edges[nid] = {}
            self.frames[nid] = (grid.shape, zlib.compress(grid.tobytes(), 1))
            self.avail[nid] = avail

    def grid(self, nid: str) -> np.ndarray:
        shape, blob = self.frames[nid]
        return np.frombuffer(zlib.decompress(blob), dtype=np.uint8).reshape(shape)

    def rekey(self, keyfn: Callable[[np.ndarray], str]) -> dict[str, str]:
        mapping = {nid: keyfn(self.grid(nid)) for nid in self.frames}
        frames: dict[str, tuple[tuple[int, int], bytes]] = {}
        avail: dict[str, tuple[int, ...]] = {}
        edges: dict[str, dict[tuple, str]] = {}
        weak: dict[str, set[tuple]] = {}
        over: dict[tuple[str, tuple], int] = {}
        restarts: dict[tuple[str, tuple], int] = {}
        ends: dict[tuple[str, tuple], int] = {}
        for nid, new in mapping.items():
            frames.setdefault(new, self.frames[nid])
            avail.setdefault(new, self.avail.get(nid, ()))
            dst = edges.setdefault(new, {})
            for local, t in self.edges.get(nid, {}).items():
                dst[local] = mapping.get(t, t)
            if nid in self.weak:
                weak.setdefault(new, set()).update(self.weak[nid])
        for (nid, local), cnt in self.over.items():
            key = (mapping.get(nid, nid), local)
            over[key] = over.get(key, 0) + cnt
        for (nid, local), cnt in self.restarts.items():
            key = (mapping.get(nid, nid), local)
            restarts[key] = restarts.get(key, 0) + cnt
        for (nid, local), cnt in self.ends.items():
            key = (mapping.get(nid, nid), local)
            ends[key] = ends.get(key, 0) + cnt
        self.frames, self.edges, self.weak, self.over = frames, edges, weak, over
        self.avail = avail
        self.restarts = restarts
        self.ends = ends
        self.cands = {}
        if self.start is not None:
            self.start = mapping.get(self.start, self.start)
        if self.reset_target is not None:
            self.reset_target = mapping.get(self.reset_target, self.reset_target)
        return mapping

    def shortest(self, src: Optional[str], dst: str) -> Optional[int]:
        if src is None or src not in self.edges:
            return None
        dist = {src: 0}
        q = deque([src])
        while q:
            n = q.popleft()
            if n == dst:
                return dist[n]
            for t in self.edges.get(n, {}).values():
                if t in self.edges and t not in dist:
                    dist[t] = dist[n] + 1
                    q.append(t)
        return None


class _Pending:
    """An action that has been sent but whose result has not been seen yet."""

    __slots__ = ("nid", "local", "tkey", "reason", "grid", "lvl", "al")

    def __init__(self, nid: Optional[str], local: tuple, tkey: Optional[str],
                 reason: str, grid: Optional[np.ndarray], lvl: int, al: int) -> None:
        self.nid = nid
        self.local = local
        self.tkey = tkey
        self.reason = reason
        self.grid = grid
        self.lvl = lvl      # 1-based level in which the action was taken
        self.al = al        # its index among that level's actions


# --------------------------------------------------------------------------
# the agent


class MyAgent(Agent):
    """Graph explorer with a cross-level action-effect table and a probe rule
    derived from the RHAE level weights. See the module docstring."""

    MAX_ACTIONS = 15000
    MIN_BUDGET = 8      # shorter recurring life lengths are traps, not a move budget
    END_CAP = 4         # a (state, action) that ends a life this often is given up

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # set before super().__init__(): with record=True (as in the Kaggle
        # swarm) the base class builds the recording name from self.name
        raw_cfg = os.getenv("ARC_AGENT_CONFIG", "C").strip().upper()
        self.config = CONFIG_ALIASES.get(raw_cfg, "C")
        self.seed = _env_int("ARC_SEED", 0)
        super().__init__(*args, **kwargs)
        self.rho = _env_float("ARC_RHO", 0.0003)
        self.rstar = _env_float("ARC_RSTAR", 2.0)
        self.q = min(1.0, max(0.0, _env_float("ARC_Q", 0.5)))
        self.k = max(1, _env_int("ARC_K", 2))
        # moves are often blocked by walls, so a simple action needs more NONE
        # observations than a clicked object type before it counts as a no-op
        self.k_simple = max(self.k, _env_int("ARC_K_SIMPLE", 4))
        self.r1 = _env_float("ARC_R1", 5.0)
        self.level_cap = _env_int("ARC_LEVEL_CAP", 1500)
        self.max_clicks = _env_int("ARC_MAX_CLICKS", 48)
        self.reset_penalty = _env_float("ARC_RESET_PENALTY", 10.0)
        self.debug = os.getenv("ARC_DEBUG", "") == "1"
        self.game_key = str(self.game_id).split("-")[0]
        # Common random numbers: every config draws the same tie-breaks for a
        # given game and seed, so A and B act identically until the table
        # transfer (or the probe rule) makes them differ.
        self.rng = random.Random(zlib.crc32(f"{self.game_key}|{self.seed}".encode()))
        self.probe_budget = self._load_probe_budget()
        self.uniform_quota = _env_int("ARC_UNIFORM_PROBES", 6)

        # world model
        self.hud: Optional[_Hud] = None
        self.graph: Optional[_LevelGraph] = None
        self.table: dict[str, list[int]] = {}   # tkey -> [n_none, n_change, n_new_state]
        self.seen_keys: set[str] = set()
        self.trans: list[tuple[int, str, Optional[np.ndarray], bool]] = []
        if os.getenv("ARC_PRIOR_MOVES", "0") == "1":
            # ablation only: start as if ACTION1-4 were already known to work
            for k in ("a1", "a2", "a3", "a4"):
                self.trans.append((0, k, None, True))
                self._count(k, None, True)
        self.level: Optional[int] = None
        self.win_levels = 0
        self.avail: tuple[int, ...] = ()
        self.cur: Optional[str] = None
        self.last_grid: Optional[np.ndarray] = None
        self.need_reset = False
        self.pending: Optional[_Pending] = None
        self.plan: deque[tuple[str, tuple]] = deque()
        self.end_lens: list[tuple[int, tuple]] = []   # (life length, (node, action)) per ended life
        self.budget: Optional[int] = None              # detected moves per life in this level

        # bookkeeping
        self.rhat = self.r1
        self.a_level = 0          # actions in this level, RESET included
        self.life = 0             # non-RESET actions since level start, RESET or restart
        self.anchor = 0           # same, used to keep RESET from restarting the whole game
        self.probes_level = 0
        self.tier_cap = 0
        self.probes_total = 0
        self.last_label: Optional[str] = None   # effect label of the last transition
        self.r_idx = 0                          # controls R and K: position in the action cycle
        self.r_still = 0                        # control R: unchanged frames in a row
        self.k_ptr: dict[str, int] = {}         # control K: next click per state
        self.level_stats: list[dict[str, Any]] = []
        self.steps = 0
        self.errors = 0
        self.random_mode = False
        self.t0 = time.time()
        self._send_data: dict[str, int] = {}
        self._resync = False
        self._send_reason: dict[str, str] = {}
        self._summary_written = False

        self.log_dir = os.getenv("ARC_LOG_DIR", "")
        self._log_fh = None
        if self.log_dir and os.getenv("ARC_LOG_STEPS", "1") != "0":
            try:
                os.makedirs(self.log_dir, exist_ok=True)
                path = os.path.join(
                    self.log_dir, f"{self.game_key}_{self.config}_s{self.seed}.jsonl")
                self._log_fh = open(path, "w", buffering=1)
            except OSError:
                self._log_fh = None

    # ------------------------------------------------------------ framework

    @property
    def name(self) -> str:
        return f"{super().name}.{getattr(self, 'config', 'C')}.s{getattr(self, 'seed', 0)}"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        if latest_frame.state is GameState.WIN:
            if self.pending is not None:
                self._safe_observe(latest_frame)
            return True
        return self.a_level >= self.level_cap

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        try:
            if self.pending is not None or self.level is None or self._resync:
                self._resync = False
                self._observe(latest_frame)
            if self.random_mode:
                local, tkey, reason = self._fallback(latest_frame)
            else:
                local, tkey, reason = self._decide()
        except Exception:  # never let a bug end the game
            if self.debug:
                raise
            self.errors += 1
            logger.exception("agent error %d in %s", self.errors, self.game_id)
            if self.errors >= 50:
                self.random_mode = True
            self._recover(latest_frame)
            local, tkey, reason = self._fallback(latest_frame)
        return self._send(local, tkey, reason)

    def do_action_request(self, action: GameAction) -> FrameData:
        # Swarm runs one thread per game and GameAction members are shared
        # singletons, so click coordinates are passed per agent instead of
        # through action.set_data().
        env = getattr(self, "arc_env", None)
        if env is None or not hasattr(self, "_convert_raw_frame_data"):
            # other framework versions: fall back to the base implementation
            if action is GameAction.ACTION6:
                action.set_data(dict(self._send_data))
            return super().do_action_request(action)
        data = dict(self._send_data) if action is GameAction.ACTION6 else {}
        raw = env.step(action, data=data, reasoning=dict(self._send_reason))
        if raw is None:
            # No response (HTTP error or timeout). Retrying could apply the
            # action twice, so forget this transition and resync on the next
            # observation instead of raising, which would end the game thread.
            self.pending = None
            self._resync = True
            obs = getattr(env, "observation_space", None)
            if obs is not None:
                return self._convert_raw_frame_data(obs)
            return self.frames[-1]
        return self._convert_raw_frame_data(raw)

    def append_frame(self, frame: FrameData) -> None:
        super().append_frame(frame)
        if len(self.frames) > 16:        # only frames[-1] is ever read; keep RAM flat
            del self.frames[:-8]

    def start_recording(self) -> None:
        # The client-side recorder writes every frame to disk (about 10 KB
        # each); with thousands of actions per game that adds up quickly, and
        # the gateway records actions on its own. Set ARC_RECORD=1 to keep it.
        if os.getenv("ARC_RECORD", "0") == "1":
            super().start_recording()

    def cleanup(self, *args: Any, **kwargs: Any) -> None:
        if self.pending is not None and self.frames and self.frames[-1].frame:
            self._safe_observe(self.frames[-1])
        self._write_summary()
        super().cleanup(*args, **kwargs)

    # ------------------------------------------------------------ observing

    def _safe_observe(self, f: FrameData) -> None:
        try:
            self._observe(f)
        except Exception:
            if self.debug:
                raise
            self.errors += 1
            logger.exception("agent error %d in %s", self.errors, self.game_id)

    def _observe(self, f: FrameData) -> None:
        p, self.pending = self.pending, None
        grid = _to_grid(f)
        state = f.state
        if grid is None:
            self.need_reset = state in (GameState.NOT_PLAYED, GameState.GAME_OVER)
            self.cur = None
            self._log(p, "empty", f)
            return
        self.win_levels = max(self.win_levels, int(f.win_levels or 0))
        self.avail = tuple(sorted(int(a) for a in (f.available_actions or [])))
        if self.hud is None or self.hud.shape != grid.shape:
            self.hud = _Hud(grid.shape)
        lc = int(f.levels_completed or 0)
        label: Optional[str] = None

        if state is GameState.NOT_PLAYED or (self.level is None and state is not GameState.NOT_FINISHED):
            # nothing to learn before the game has started
            self.need_reset = True
            self.cur = None
            self.last_grid = grid
            self._log(p, "not_started", f)
            return

        if self.level is None:
            self._start_level(lc, grid)
        elif lc != self.level:
            if p is not None and p.local != RESET and p.nid is not None and lc > self.level:
                label = "level"
                self.graph.edges.setdefault(p.nid, {})[p.local] = WIN
                self._record(p.tkey, None, True)
                self._finish_level(p)
            else:
                label = "jump"
                self._finish_level(None)
            self._start_level(lc, grid)
        elif p is not None:
            if p.local == RESET:
                label = "reset"
                self.hud.new_life()
                self.hud.record(0, grid, None)
                g = self.graph
                if g.start is not None and self.hud.reset_diff(g.grid(g.start), grid):
                    self._apply_mask()
            elif state is GameState.GAME_OVER:
                label = "over"
                if p.nid is not None:
                    self._game_over(p)
            elif state is GameState.WIN:
                label = "win"
            elif p.grid is not None and p.grid.shape == grid.shape and p.nid is not None:
                diff = p.grid != grid
                idx = np.flatnonzero(diff)
                stored = idx.astype(np.int16) if idx.size <= MAX_STORED_DIFF else None
                if self._is_restart(p, grid):
                    label = "restart"
                    self._restart(p, grid, stored)
                else:
                    p_nid = p.nid
                    grew = self.hud.update(p.grid, grid)
                    grew = self.hud.record(self.life, grid, p.local) or grew
                    if grew:
                        p_nid = self._apply_mask().get(p_nid, p_nid)
                    nid = self._nid(grid)
                    is_new = nid not in self.graph.edges
                    self._record(p.tkey, stored, is_new)
                    label = "change" if (diff & ~self.hud.mask).any() else "none"
                    self.graph.add(nid, grid, self.avail)
                    if p_nid in self.graph.edges:
                        self.graph.edges[p_nid][p.local] = nid

        if state is GameState.GAME_OVER or state is GameState.NOT_PLAYED:
            self.need_reset = True
            self.cur = None
        elif state is GameState.WIN:
            self.cur = None
        else:
            self.need_reset = False
            self.cur = self._nid(grid)
            self.graph.add(self.cur, grid, self.avail)
            if p is not None and p.local == RESET:
                self.graph.reset_target = self.cur
            if self.graph.start is None:
                self.graph.start = self.cur
                self.graph.reset_target = self.cur
        self.last_grid = grid
        self.last_label = label
        self._log(p, label, f)

    def _start_level(self, lc: int, grid: np.ndarray) -> None:
        self.level = lc
        self.graph = _LevelGraph(lc)
        self.plan.clear()
        self.a_level = 0
        self.life = 0
        self.probes_level = 0
        self.tier_cap = 0
        self.end_lens = []
        self.budget = None
        self.anchor = 0
        if self.config == "A":           # no transfer across levels
            self.table = {}
            self.seen_keys = set()
        if self.hud is not None:
            self.hud.new_level()
            self.hud.record(0, grid, None)
        nid = self._nid(grid)
        self.graph.add(nid, grid, self.avail)
        self.graph.start = nid
        self.graph.reset_target = nid

    def _finish_level(self, p: Optional[_Pending]) -> None:
        g = self.graph
        path = None
        if p is not None and p.nid is not None:
            d = g.shortest(g.start, p.nid)
            path = d + 1 if d is not None else None
        stats = {
            "level": (self.level or 0) + 1,
            "actions": self.a_level,
            "path": path,
            "rhat_used": round(self.rhat, 3),
            "probes": self.probes_level,
            "nodes": len(g.edges),
            "completed": p is not None,
        }
        if path:
            self.rhat = max(1.0, self.a_level / path)
        stats["rhat_next"] = round(self.rhat, 3)
        self.level_stats.append(stats)

    def _is_restart(self, p: _Pending, grid: np.ndarray) -> bool:
        """The game itself restarted the level (lost life, move budget)."""
        g = self.graph
        if g.start is None or p.grid is None:
            return False
        return self.hud.restart_like(p.grid, grid, g.grid(g.start))

    def _restart(self, p: _Pending, grid: np.ndarray, stored: Optional[np.ndarray]) -> None:
        g = self.graph
        key = (p.nid, p.local)
        explained = self._life_ended(key)
        if not explained:
            g.restarts[key] = g.restarts.get(key, 0) + 1
        if g.restarts.get(key, 0) >= 2 or g.ends[key] >= self.END_CAP:
            # consistent (or hopeless): treat this action as leading back
            g.edges.setdefault(p.nid, {})[p.local] = self._nid(grid)
            self._record(p.tkey, stored, False)
        self.life = 0
        self.anchor = 0                   # the engine's action count restarted too
        self.plan.clear()
        self.hud.new_life()
        self.hud.record(0, grid, None)
        if g.start is not None and self.hud.reset_diff(g.grid(g.start), grid):
            self._apply_mask()

    def _game_over(self, p: _Pending) -> None:
        g = self.graph
        key = (p.nid, p.local)
        if self._life_ended(key) and g.ends[key] < self.END_CAP:
            return                       # the move budget ran out; nothing to blame
        g.over[key] = g.over.get(key, 0) + 1
        if g.over[key] >= 2 or g.ends[key] >= self.END_CAP:
            # the same action ended the game twice from the same state
            g.edges.setdefault(p.nid, {})[p.local] = TERMINAL
        elif not self.hud.mask.any():
            g.weak.setdefault(p.nid, set()).add(p.local)   # retried only late

    def _life_ended(self, key: tuple) -> bool:
        """Record that the current life ended after self.life actions, through
        `key`. Lives that end at (nearly) the same, fairly long length through
        two or more different (state, action) pairs reveal a move budget.
        Returns True if this end is explained by that budget."""
        g = self.graph
        g.ends[key] = g.ends.get(key, 0) + 1
        self.end_lens.append((self.life, key))
        longest = max(n for n, _ in self.end_lens)
        best = None
        for n in sorted({n for n, _ in self.end_lens}):
            if n < self.MIN_BUDGET or n < 0.8 * longest:
                continue
            keys = {k for m, k in self.end_lens if n <= m <= n + 1}
            if len(keys) >= 2 and (best is None or len(keys) > best[0]):
                best = (len(keys), n)
        if best is not None and best[1] != self.budget:
            self.budget = best[1]
            self._forgive(self.budget)
        return self.budget is not None and self.life >= self.budget

    def _forgive(self, budget: int) -> None:
        """Undo blame on actions that only ended a life because the budget ran out."""
        g = self.graph
        for n, (nid, local) in self.end_lens:
            if n < budget:
                continue
            key = (nid, local)
            g.over.pop(key, None)
            g.restarts.pop(key, None)
            if nid in g.weak:
                g.weak[nid].discard(local)
            t = g.edges.get(nid, {}).get(local)
            if t == TERMINAL or (t is not None and t in (g.start, g.reset_target)):
                del g.edges[nid][local]

    def _apply_mask(self) -> dict[str, str]:
        mapping = self.graph.rekey(self._nid)
        if self.cur is not None:
            self.cur = mapping.get(self.cur, self.cur)
        self.end_lens = [(n, (mapping.get(k[0], k[0]), k[1])) for n, k in self.end_lens]
        self.plan.clear()
        self._rebuild_table()
        return mapping

    # ------------------------------------------------------------ table

    def _record(self, tkey: Optional[str], idx: Optional[np.ndarray], new: bool) -> None:
        if tkey is None:
            return
        self.trans.append((self.level or 0, tkey, idx, new))
        self._count(tkey, idx, new)

    def _count(self, tkey: str, idx: Optional[np.ndarray], new: bool) -> None:
        if idx is None:
            changed = True
        elif idx.size == 0:
            changed = False
        else:
            changed = bool((~self.hud.mask.ravel()[idx.astype(np.int64)]).any())
        o = self.table.setdefault(tkey, [0, 0, 0])
        o[1 if changed else 0] += 1
        if changed and new:
            o[2] += 1

    def _rebuild_table(self) -> None:
        self.table = {}
        for lvl, tkey, idx, new in self.trans:
            if self.config == "A" and lvl != self.level:
                continue
            self._count(tkey, idx, new)

    def _novelty(self, tkey: str) -> float:
        """Share of this key's transitions that reached a state not seen
        before (Laplace smoothed). Toggling something back scores low."""
        o = self.table.get(tkey)
        if o is None:
            return 1.0
        return (o[2] + 1.0) / (o[0] + o[1] + 2.0)

    def _rank(self, c: _Cand) -> tuple:
        return (self._cls(c.tkey), -self._novelty(c.tkey), c.sal)

    def _cls(self, tkey: str) -> int:
        o = self.table.get(tkey)
        if o is None:
            return UNKNOWN
        if o[1] > 0:
            return ACTIVE
        if o[0] >= (self.k_simple if tkey.startswith("a") else self.k):
            return NOOP
        return UNKNOWN

    # ------------------------------------------------------------ deciding

    def _nid(self, grid: np.ndarray) -> str:
        g = grid
        if self.hud is not None and self.hud.mask.shape == grid.shape and self.hud.mask.any():
            g = grid.copy()
            g[self.hud.mask] = MASK_VALUE
        h = blake2b(g.tobytes(), digest_size=8)
        h.update(bytes(self.avail))
        h.update(repr(grid.shape).encode())
        return h.hexdigest()

    def _cands(self, nid: str) -> list[_Cand]:
        g = self.graph
        cached = g.cands.get(nid)
        if cached is not None:
            return cached
        grid = g.grid(nid)
        avail = g.avail.get(nid) or self.avail or (1, 2, 3, 4, 5, 6)
        out = []
        for aid in SIMPLE_IDS:
            if aid in avail:
                out.append(_Cand((aid,), f"a{aid}", (0, 0, 0, 0, self.rng.random())))
        if 6 in avail:
            valid = ~self.hud.mask if self.hud is not None and self.hud.mask.shape == grid.shape \
                else np.ones(grid.shape, dtype=bool)
            comps = _components(grid, valid)
            if comps:
                area: dict[int, int] = {}
                for c in comps:
                    area[c["color"]] = area.get(c["color"], 0) + c["size"]
                bg = max(area, key=lambda k: area[k])
                big = grid.size // 8
                fg_area = sum(v for k, v in area.items() if k != bg) or 1
                clicks = []
                for c in comps:
                    share = area[c["color"]] / fg_area
                    tier = self._tier(c, bg, big, share)
                    if c["color"] == bg or share > COMMON_SHARE:
                        # background, floor and walls are cut into pieces of
                        # changing shape as objects move: one key per colour,
                        # or every state would bring new "unknown" keys
                        tkey = f"c{c['color']}:region"
                    elif c["size"] > big:
                        tkey = f"c{c['color']}:big"
                    else:
                        tkey = f"c{c['color']}:{c['h']}x{c['w']}:{c['size']}:{c['shape']:04x}"
                    sal = (1, tier, area[c["color"]], c["size"], self.rng.random())
                    clicks.append(_Cand((6, c["x"], c["y"]), tkey, sal))
                clicks.sort(key=lambda c: c.sal)
                out.extend(clicks[: self.max_clicks])
        for c in out:
            self.seen_keys.add(c.tkey)
        g.cands[nid] = out
        return out

    @staticmethod
    def _tier(c: dict[str, Any], bg: int, big: int, share: float) -> int:
        """Click priority, 0 = most likely a button or object. Five tiers by
        size, compactness and colour rarity, after the tiered click
        priorities of the graph explorer in arXiv 2512.24156 (own rules)."""
        if c["color"] == bg:
            return 3 if c["size"] <= big else 4
        if c["size"] > big:
            return 3
        if c["size"] <= 2:
            return 2
        compact = c["size"] / float(c["h"] * c["w"])
        return 0 if compact >= 0.5 and share <= COMMON_SHARE else 1

    def _untried(self, nid: str, strong: bool, unknown: bool = False) -> list[_Cand]:
        """Untried candidates at nid. strong: actions known to have an effect
        (ACTIVE), plus actions of unknown effect when `unknown` (probing is
        on). Otherwise everything untried, which is only used once no strong
        frontier is left anywhere (the agent is stuck)."""
        g = self.graph
        tried = g.edges.get(nid, {})
        weak = g.weak.get(nid, ())
        if strong:
            ok = (ACTIVE, UNKNOWN) if unknown else (ACTIVE,)
            cap = self.tier_cap
            return [c for c in self._cands(nid)
                    if c.local not in tried and c.local not in weak and self._cls(c.tkey) in ok
                    and (c.sal[0] == 0 or c.sal[1] <= cap)]
        return [c for c in self._cands(nid) if c.local not in tried]

    def _probe_ok(self) -> bool:
        j = (self.level or 0) + 1
        if self.config == "C":
            # value of information for later levels, each weighted by the
            # chance q^(i-j) of getting that far (q = 1: the original rule)
            levels = max(self.win_levels, j)
            left = self.rho * sum(i * self.q ** (i - j) for i in range(j + 1, levels + 1))
            left /= self.rstar ** 2
            right = j / (max(1, self.a_level) * self.rhat ** 2)
            return left > right
        if self.config == "CU":
            # even split of the budget; quota a level could not use carries forward
            return self.probes_total < sum(self._quota(i) for i in range(1, j + 1))
        return False

    def _quota(self, j: int) -> int:
        if self.probe_budget is None:
            return self.uniform_quota
        levels = max(1, self.win_levels)
        base, extra = divmod(self.probe_budget, levels)
        return base + (1 if j - 1 < extra else 0)

    def _decide(self) -> tuple[tuple, Optional[str], str]:
        if self.need_reset or self.cur is None:
            return RESET, None, "reset"
        if self.config in ("R", "K"):
            return self._control()
        while self.plan:
            expected, local = self.plan[0]
            if expected != self.cur or (local == RESET and self.anchor == 0):
                self.plan.clear()
                break
            self.plan.popleft()
            return local, self._tkey_of(local), "navigate"

        # Probing is a discretionary decision: without it (A, B, or when the
        # rule says no) actions of unknown effect are tried only once nothing
        # known to work is left to try anywhere in the level graph.
        probe = self.config in ("C", "CU") and self._probe_ok()
        # Click priority threshold for the whole level graph: lower-priority
        # clicks are considered only once nothing at the current threshold is
        # left untried anywhere reachable. The threshold is raised only when
        # that finds something to try; if nothing qualifies at any threshold
        # (as at the start of a game, before any action is known to work),
        # the weak phase below takes over and the threshold stays put.
        cap0 = self.tier_cap
        while True:
            live = self._untried(self.cur, strong=True, unknown=probe)
            if live:
                if probe:
                    unknown = [c for c in live if self._cls(c.tkey) == UNKNOWN]
                    if unknown:
                        c = min(unknown, key=lambda c: c.sal)
                        self.probes_level += 1
                        self.probes_total += 1
                        return c.local, c.tkey, "probe"
                c = min(live, key=self._rank)
                return c.local, c.tkey, "exploit"
            path = self._path(strong=True, unknown=probe)
            if path is not None:
                break
            if self.tier_cap >= MAX_TIER:
                self.tier_cap = cap0
                break
            self.tier_cap += 1

        if path is None:
            rest = self._untried(self.cur, strong=False)
            if rest:
                c = min(rest, key=self._rank)
                return c.local, c.tkey, "retry"
            path = self._path(strong=False)
        if path:
            self.plan = deque(path)
            _, local = self.plan.popleft()
            return local, self._tkey_of(local), "navigate"
        return self._random_action()

    def _path(self, strong: bool, unknown: bool = False) -> Optional[list[tuple[str, tuple]]]:
        """Shortest known path to the nearest node with untried actions.
        Starting over with RESET (back to the level start) is allowed when it
        is shorter by more than ARC_RESET_PENALTY actions, because a RESET
        also throws away whatever the level state has gained so far. With a
        known move budget, only frontiers whose untried action would still be
        observed before the budget runs out are considered first."""
        g = self.graph
        reset_ok = (self.anchor > 0 and g.reset_target is not None
                    and g.reset_target != self.cur and g.reset_target in g.edges)
        limits = [None]
        if self.budget is not None:
            limits = [(self.budget - self.life - 2, self.budget - 2), None]
        for lim in limits:
            lim_own, lim_reset = lim if lim is not None else (None, None)
            own = None
            if lim_own is None or lim_own >= 1:
                own = self._bfs(self.cur, strong, True, lim_own, unknown)
            via = self._bfs(g.reset_target, strong, False, lim_reset, unknown) if reset_ok else None
            if via is not None and (own is None or 1 + self.reset_penalty + len(via) < len(own)):
                return [(self.cur, RESET)] + via
            if own is not None:
                return own
        return None

    def _bfs(self, src: str, strong: bool, skip_src: bool, max_len: Optional[int] = None,
             unknown: bool = False) -> Optional[list[tuple[str, tuple]]]:
        g = self.graph
        prev: dict[str, Optional[tuple[str, tuple]]] = {src: None}
        dist = {src: 0}
        q = deque([src])
        while q:
            n = q.popleft()
            if (n != src or not skip_src) and self._untried(n, strong, unknown):
                path = []
                while prev[n] is not None:
                    pn, local = prev[n]
                    path.append((pn, local))
                    n = pn
                path.reverse()
                return path
            if max_len is not None and dist[n] >= max_len:
                continue
            for local, t in g.edges.get(n, {}).items():
                if t in g.edges and t not in prev:
                    prev[t] = (n, local)
                    dist[t] = dist[n] + 1
                    q.append(t)
        return None

    def _tkey_of(self, local: tuple) -> Optional[str]:
        if local == RESET:
            return None
        for c in self._cands(self.cur):
            if c.local == local:
                return c.tkey
        return f"a{local[0]}" if local[0] != 6 else None

    def _control(self) -> tuple[tuple, Optional[str], str]:
        """Trivial-policy controls: no graph search, no effect table, no
        probing; only RESET after a game over, as every configuration does."""
        cands = self._cands(self.cur)
        simple = [c for c in cands if c.local[0] != 6]
        clicks = [c for c in cands if c.local[0] == 6]      # already in salience order
        if self.config == "R":
            cycle = simple + clicks[:1]
            if not cycle:
                return self._random_action()
            self.r_still = self.r_still + 1 if self.last_label == "none" else 0
            if self.r_still >= 2:
                self.r_idx += 1
                self.r_still = 0
            c = cycle[self.r_idx % len(cycle)]
            return c.local, c.tkey, "control"
        i = self.k_ptr.get(self.cur, 0)
        if i < len(clicks):
            self.k_ptr[self.cur] = i + 1
            c = clicks[i]
            return c.local, c.tkey, "control"
        if simple:
            c = simple[self.r_idx % len(simple)]
            self.r_idx += 1
            return c.local, c.tkey, "control"
        self.k_ptr[self.cur] = 0
        return self._random_action()

    def _random_action(self) -> tuple[tuple, Optional[str], str]:
        avail = [a for a in (self.avail or (1, 2, 3, 4, 5, 6)) if a in (1, 2, 3, 4, 5, 6)]
        if not avail:
            return RESET, None, "random"
        aid = self.rng.choice(avail)
        if aid == 6:
            h, w = self.last_grid.shape if self.last_grid is not None else (64, 64)
            return (6, self.rng.randrange(w), self.rng.randrange(h)), None, "random"
        return (aid,), f"a{aid}", "random"

    def _fallback(self, f: FrameData) -> tuple[tuple, Optional[str], str]:
        if f is None or f.state in (GameState.NOT_PLAYED, GameState.GAME_OVER) or not f.frame:
            return RESET, None, "reset"
        return self._random_action()

    def _recover(self, f: FrameData) -> None:
        """After an internal error: drop the pending transition and the plan,
        re-anchor on the current frame, keep the level graph and counters."""
        self.pending = None
        self.plan.clear()
        grid = _to_grid(f)
        if grid is None:
            self.need_reset = True
            self.cur = None
            return
        self.last_grid = grid
        if self.hud is None or self.hud.shape != grid.shape:
            self.hud = _Hud(grid.shape)
        lc = int(f.levels_completed or 0)
        if self.graph is None or self.level is None or lc != self.level:
            if self.level is not None and self.graph is not None:
                self._finish_level(None)
            self._start_level(lc, grid)
        if f.state in (GameState.GAME_OVER, GameState.NOT_PLAYED):
            self.need_reset = True
            self.cur = None
        else:
            self.need_reset = False
            self.cur = self._nid(grid)
            self.graph.add(self.cur, grid, self.avail)

    def _send(self, local: tuple, tkey: Optional[str], reason: str) -> GameAction:
        if local == RESET:
            action = GameAction.RESET
            self._send_data = {}
            self.life = 0
            self.anchor = 0
        elif local[0] == 6:
            action = GameAction.ACTION6
            self._send_data = {"x": int(local[1]), "y": int(local[2])}
            self.life += 1
            self.anchor += 1
        else:
            action = GameAction.from_id(int(local[0]))
            self._send_data = {}
            self.life += 1
            self.anchor += 1
        self._send_reason = {"why": reason}
        self.a_level += 1
        self.steps += 1
        self.pending = _Pending(self.cur, local, tkey, reason, self.last_grid,
                                (self.level or 0) + 1, self.a_level)
        return action

    # ------------------------------------------------------------ logging

    def _load_probe_budget(self) -> Optional[int]:
        if self.config != "CU":
            return None
        if os.getenv("ARC_PROBE_BUDGET"):
            return max(0, _env_int("ARC_PROBE_BUDGET", 0))
        path = os.getenv("ARC_PROBE_BUDGETS", "")
        if path:
            try:
                with open(path) as fh:
                    budgets = json.load(fh)
                for key in (f"{self.game_key}:{self.seed}", self.game_key):
                    if key in budgets:
                        return max(0, int(budgets[key]))
            except (OSError, ValueError, TypeError):
                pass
        return None

    def _log(self, p: Optional[_Pending], label: Optional[str], f: FrameData) -> None:
        if self._log_fh is None or p is None:
            return
        local = p.local
        rec = {
            "t": self.steps,
            "lvl": p.lvl,
            "al": p.al,
            "act": "R" if local == RESET else f"A{local[0]}",
            "x": local[1] if local != RESET and local[0] == 6 else None,
            "y": local[2] if local != RESET and local[0] == 6 else None,
            "key": p.tkey,
            "why": p.reason,
            "eff": label,
            "cls": CLASS_NAMES.get(self._cls(p.tkey)) if p.tkey else None,
            "nk": len(self.table),
            "nu": sum(1 for k in self.seen_keys if self._cls(k) == UNKNOWN),
            "pl": self.probes_level,
            "pt": self.probes_total,
            "rh": round(self.rhat, 3),
            "node": self.cur,
            "st": f.state.value if f is not None else None,
        }
        try:
            self._log_fh.write(json.dumps(rec) + "\n")
        except (OSError, ValueError):
            pass

    def _write_summary(self) -> None:
        if self._summary_written:
            return
        self._summary_written = True
        current = None
        final = self.frames[-1] if self.frames else None
        won = final is not None and final.state is GameState.WIN
        in_range = self.win_levels == 0 or (self.level is not None and self.level < self.win_levels)
        if self.level is not None and not won and in_range and self.a_level > 0:
            current = {
                "level": self.level + 1,
                "actions": self.a_level,
                "path": None,
                "rhat_used": round(self.rhat, 3),
                "probes": self.probes_level,
                "nodes": len(self.graph.edges) if self.graph else 0,
                "completed": False,
            }
        summary = {
            "game": self.game_key,
            "game_id": str(self.game_id),
            "config": self.config,
            "seed": self.seed,
            "rho": self.rho,
            "rstar": self.rstar,
            "k": self.k,
            "win_levels": self.win_levels,
            "levels_completed": int(final.levels_completed) if final is not None else 0,
            "state": final.state.value if final is not None else None,
            "actions": self.steps,
            "probes": self.probes_total,
            "probe_budget": self.probe_budget,
            "levels": self.level_stats + ([current] if current else []),
            "hud_rows": sorted(self.hud.rows) if self.hud else [],
            "hud_cols": sorted(self.hud.cols) if self.hud else [],
            "table": {k: v[:] for k, v in self.table.items()},
            "errors": self.errors,
            "seconds": round(time.time() - self.t0, 2),
        }
        if self._log_fh is not None:
            try:
                self._log_fh.write(json.dumps({"summary": summary}) + "\n")
                self._log_fh.close()
            except (OSError, ValueError):
                pass
            self._log_fh = None
        if self.log_dir:
            try:
                with _FILE_LOCK, open(os.path.join(self.log_dir, "summary.jsonl"), "a") as fh:
                    fh.write(json.dumps(summary) + "\n")
            except OSError:
                pass
