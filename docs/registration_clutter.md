# Registration: cluttered rooms (third family)

Written on 2026-10-14 (KST) and committed before the evaluation games were generated or any evaluation run started. Agent, runner and analysis scripts are those of this commit.

## Why

In open rooms the probe rule (C) beat its rule-free version (B); in mazes it did not. Our account: B tries actions of unknown effect only when stuck, and in mazes it is stuck so often that it learns the switch in level 1 anyway (free learning), while in open rooms it learns the switch late or never. Rooms and mazes differ in more than that, so this family varies free learning within one suite: open rooms of one size (16 x 16 floor) with a share of the floor turned into wall ("clutter"), keeping the floor connected (scripts/make_clutter.py). Games with the same instance number share their base room and differ only in clutter. More clutter means more dead ends, so B should be stuck, and learn the switch, more often, and C's gain over B should shrink.

## Pilots and calibration (before this registration)

Pilot games used instance numbers 20 to 23, which no evaluation game uses.

- Pilot 1, B only, clutter 0, 0.1, 0.2, 0.3, 0.4, 0.5 (game ids k1.. to k6..), seeds 0 to 2: B saw the switch work in level 1 in 0, 3, 7, 6, 12 and 8 of 12 runs. runs/syn_clutter_pilot1.
- Pilot 2, B and C (rho 0.01, q 0.5), clutter 0, 0.15, 0.3, 0.45 (k1.. to k4..), seeds 0 to 4: C above B in 4 of 4 games at every level; relative gain of the level means 6.4, 5.9, 24.1 and 1.2. runs/syn_clutter_pilot2.
- Pilot 3, the same at clutter 0.55, 0.6, 0.65, 0.7 (k1.. to k4..; the connectivity rule stops near 0.6, so the last two reach 0.57 to 0.62): C above B in 3, 1, 2 and 1 of 4 games. runs/syn_clutter_pilot3.
- Pilot games: `scripts/make_clutter.py --size 16 --clutter <shares> --eval "" --calib "" --pilot 20,21,22,23`.

From these we chose clutter 0, 0.2, 0.4 and 0.6 (difficulty d1 to d4; 0.6 is about the most the rule allows, 0.55 to 0.60 per level).

Calibration followed the registered procedure of round 2 on 12 calibration games (instances 5 to 7, `--clutter 0,0.2,0.4,0.6 --eval "" --calib 5,6,7`), seeds 0 to 2:

- q per clutter level from B's completion rate: 0.733, 0.767, 0.933, 1.0 (runs/syn_clutter_q.json, runs/syn_clutter_calibB).
- rho from {1e-4, 3e-4, 1e-3, 3e-3, 1e-2} by C's mean RHAE: 1.409, 0.645, 1.032, 0.972, 0.859, so rho = 1e-4 (runs/syn_clutter_calibC). At this rho C first probes after 82 to 220 actions of level 1 (median 103), or not at all before level 1 ends (7 of 36 calibration runs).
- At rho = 1e-4 on the calibration games: C above B in 10 of 12; K1 = -0.47 (p = 0.10, 3 base rooms), K2 = +0.61 (p = 0.013).

## Fixed design

- Games: 48 evaluation games, 12 base rooms (instances 30 to 41) at the four clutter levels, generated after this registration with `scripts/make_clutter.py --size 16 --clutter 0,0.2,0.4,0.6 --eval 30,31,32,33,34,35,36,37,38,39,40,41 --calib "" --out synthetic/clutter` and checked with scripts/verify_synthetic.py. We use 12 base rooms instead of 4 because the main test is a correlation within base rooms.
- Parameters from calibration, unchanged: rho = 1e-4, q per level from runs/syn_clutter_q.json.
- Configurations: A, B, C, C1, C' (CU), C'r (CR) and the always-probe control CA in one run; B and C again with step logs for the diagnosis (the runs are deterministic, so these rows must equal those of the first run).
- Seeds 40 to 44, not used before. Caps as before: 1,500 actions per level, 15,000 per game.
- Commands:

```
P=.venv/bin/python
$P scripts/run_experiments.py --env-dir synthetic/clutter --tags clutter,eval --configs A,B,C,C1,CU,CR,CA --rho 0.0001 --q runs/syn_clutter_q.json --seeds 40,41,42,43,44 --jobs 2 --no-step-logs --out runs/syn_clutter_confirm
$P scripts/run_experiments.py --env-dir synthetic/clutter --tags clutter,eval --configs B,C --rho 0.0001 --q runs/syn_clutter_q.json --seeds 40,41,42,43,44 --jobs 2 --out runs/syn_clutter_diag
```

## Tests and criteria

Primary (`scripts/analyze_clutter.py runs/syn_clutter_confirm/results.jsonl runs/syn_clutter_diag`), per game on mean RHAE over the five seeds, relative gain (C - B) / max(B, 0.01):

- K1 dose: the mean over base rooms of the Spearman correlation between clutter and the relative gain is below 0, with one-sided permutation p < 0.05 (clutter permuted within base rooms, 20,000 draws, seed 0).
- K2 free learning: the same statistic between clutter and the share of B runs that saw the switch work in level 1 is above 0, with one-sided p < 0.05.
- H6: C is above B in at least 60% of untied games, with one-sided sign test p < 0.05.

Secondary (`scripts/analyze_synthetic.py runs/syn_clutter_confirm/results.jsonl`, difficulty = clutter level): H1, H2, H4 (the pooled version of K1), H5 as before. K3, the within-room correlation between that switch share and the relative gain, is descriptive. Exploratory (`scripts/analyze_extra.py`): C against CA and C'r, CA against B, and `--same B` and `--same C` between runs/syn_clutter_confirm and runs/syn_clutter_diag.

## Predictions

- K1 passes: the gain falls with clutter.
- K2 passes: B learns the switch in level 1 more often with more clutter.
- H6 passes.
- H1 passes; H4 passes; K3 is negative.
- H2, H5 and the exploratory comparisons: no prediction.

## Reporting

Every result goes into the paper and the appendix, whatever it shows. If K1 or K2 fails, the paper says so where it states the account.
