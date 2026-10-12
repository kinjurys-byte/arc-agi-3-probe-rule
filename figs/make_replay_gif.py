"""Media-gallery GIF: B and C playing level 3 of the same open room.

Replays one confirmation run of each configuration (game r203, 16x16 room,
seed 20; C with rho = 0.01 and q = 0.64 as in runs/syn_rooms_confirm), checks
that the level-3 action counts match the stored results, and draws both
players side by side in the game's own colours.

usage: python figs/make_replay_gif.py   (needs the setup of the README)
"""
from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME, SEED, LEVEL = "r203", 20, 3
SETTINGS = {"B": {}, "C": {"ARC_RHO": "0.01", "ARC_Q": "0.64"}}
OUT = ROOT / "figs" / f"replay_level{LEVEL}_{GAME}_s{SEED}.gif"

# ARC-AGI-3 palette (arc_agi/rendering.py)
PALETTE = ["#FFFFFF", "#CCCCCC", "#999999", "#666666", "#333333", "#000000", "#E53AA3", "#FF7BCC",
           "#F93C31", "#1E93FF", "#88D8F1", "#FFDC00", "#FF851B", "#921231", "#4FCC30", "#A356D6"]
INK, INK2, RULE = (26, 26, 26), (92, 92, 92), (227, 227, 227)


def record(config: str, out_path: str) -> None:
    """Child process: play the whole game and pickle the settled frames."""
    import importlib.util
    import logging

    sys.path.insert(0, str(ROOT / "vendor" / "ARC-AGI-3-Agents"))
    env_dir = str(ROOT / "synthetic" / "rooms")
    os.environ.update({"OPERATION_MODE": "offline", "ENVIRONMENTS_DIR": env_dir,
                       "ARC_AGENT_CONFIG": config, "ARC_SEED": str(SEED), **SETTINGS[config]})
    os.environ.pop("ARC_LOG_DIR", None)
    logging.basicConfig(level=logging.ERROR)
    import arc_agi
    from arc_agi import OperationMode

    spec = importlib.util.spec_from_file_location("user_agent", ROOT / "agent" / "my_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    arc = arc_agi.Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=env_dir)
    arc.logger.setLevel(logging.ERROR)
    env = arc.make(GAME)
    frames = []                       # the agent keeps only its last few frames, so record them here

    def recording(fn):
        def wrapped(*args, **kwargs):
            fr = fn(*args, **kwargs)
            if fr is not None and fr.frame:
                frames.append((fr.levels_completed, [list(row) for row in fr.frame[-1]]))
            return fr
        return wrapped

    env.step, env.reset = recording(env.step), recording(env.reset)
    agent = mod.MyAgent(card_id="gif", game_id=GAME, agent_name=f"gif.{GAME}", ROOT_URL="http://localhost",
                        record=False, arc_env=env, tags=["gif"])
    agent.main()
    stats = [(s["level"], s["actions"], s["completed"]) for s in agent.level_stats]
    Path(out_path).write_bytes(pickle.dumps({"frames": frames, "stats": stats}))


def level_segment(frames, level):
    """Frames seen while `level` is played: its start, then the result of every action but the
    last one (the action that clears the level returns the next level's first frame)."""
    return [g for lc, g in frames if lc == level - 1]


def main() -> None:
    from PIL import Image, ImageDraw, ImageFont

    import tempfile

    data = {}
    with tempfile.TemporaryDirectory() as tmp:
        for cfg in ("B", "C"):
            path = Path(tmp) / f"{cfg}.pkl"
            subprocess.run([sys.executable, __file__, "--record", cfg, str(path)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            data[cfg] = pickle.loads(path.read_bytes())
    stored = {(r["label"], r["seed"]): r for r in map(json.loads, open(ROOT / "runs/syn_rooms_confirm/results.jsonl"))
              if r["game"] == GAME}
    n = {}
    for cfg in ("B", "C"):
        lv = {s["level"]: s["actions"] for s in stored[(cfg, SEED)]["levels"]}
        mine = {lvl: a for lvl, a, _ in data[cfg]["stats"]}
        assert mine[LEVEL] == lv[LEVEL], (cfg, mine[LEVEL], lv[LEVEL])
        n[cfg] = lv[LEVEL]
    segs = {cfg: level_segment(data[cfg]["frames"], LEVEL) for cfg in ("B", "C")}
    for cfg in ("B", "C"):
        assert len(segs[cfg]) == n[cfg], (cfg, len(segs[cfg]), n[cfg])

    def font(weight, size):
        path = Path(f"/usr/share/fonts/opentype/inter/Inter-{weight}.otf")
        return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()

    f_title, f_label, f_small = font("SemiBold", 22), font("SemiBold", 18), font("Regular", 15)
    scale, gap, top, foot = 5, 32, 116, 74
    pw = 64 * scale
    width, height = 3 * gap + 2 * pw, top + pw + foot
    rgb = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in PALETTE]

    def grid_img(g):
        im = Image.new("P", (64, 64))
        im.putpalette([v for c in rgb for v in c])
        im.putdata([v for row in g for v in row])
        return im.convert("RGB").resize((pw, pw), Image.NEAREST)

    names = {"B": "B, no probe rule", "C": "C, probe rule"}
    # timeline: one action per frame while C plays, then 12 actions per frame
    fast_from, fast_step = n["C"] + 8, 12
    ticks = list(range(0, fast_from)) + list(range(fast_from, n["B"] + 1, fast_step))
    if ticks[-1] != n["B"]:
        ticks.append(n["B"])
    frames, durations = [], []
    for t in ticks:
        im = Image.new("RGB", (width, height), "white")
        d = ImageDraw.Draw(im)
        d.text((gap, 22), f"Level 3 of an open room (16\u00d716), seed {SEED}", font=f_title, fill=INK)
        d.text((gap, 56), "The exit (blue) is behind a door (dark) that the switch (light blue, left wall) opens.",
               font=f_small, fill=INK2)
        d.text((gap, 78), "C clicked the switch in level 1. B tries unknown actions only when stuck.",
               font=f_small, fill=INK2)
        for k, cfg in enumerate(("B", "C")):
            x0 = gap + k * (pw + gap)
            seg = segs[cfg]
            i = min(t, len(seg) - 1)
            im.paste(grid_img(seg[i]), (x0, top))
            d.rectangle([x0 - 1, top - 1, x0 + pw, top + pw], outline=RULE)
            done = t >= n[cfg]
            d.text((x0, top + pw + 12), names[cfg], font=f_label, fill=INK)
            status = f"cleared in {n[cfg]:,} actions" if done else f"{min(t, n[cfg]):,} actions"
            d.text((x0, top + pw + 40), status, font=f_small, fill=INK if done else INK2)
        speed = "1 action per frame" if t < fast_from else f"{fast_step} actions per frame"
        d.text((width - gap, 28), speed, font=f_small, fill=INK2, anchor="ra")
        frames.append(im)
        durations.append(90 if t < fast_from else 60)
    durations[-1] = 2500
    # one fixed palette for every frame: the 16 game colours plus a grey ramp for the text
    ramp = [(v, v, v) for v in range(0, 256, 8)]
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette([v for c in rgb + ramp for v in c] + [0, 0, 0] * (256 - len(rgb) - len(ramp)))
    pal = [im.quantize(palette=pal_img, dither=Image.Dither.NONE) for im in frames]
    pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(frames)} frames, level 3 in {n['C']} (C) and {n['B']} (B) actions")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--record":
        record(sys.argv[2], sys.argv[3])
    else:
        main()
