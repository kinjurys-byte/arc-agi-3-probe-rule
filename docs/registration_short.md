# Registration: short first levels (fourth family)

Written on 2026-10-28 (KST) and committed before the evaluation games were generated or any evaluation run started. Agent, runner and analysis scripts are those of this commit.

## Why

On the 25 public games, always probing (CA) lost score mainly in the levels our explorer clears within a few times the human actions, which earned most of its score, while the probe rule (C) made no probe in those level 1s (exploratory; runs/real_seeds15_34/where_probing_lost.txt, docs/appendix.md H). By the score, an action in level j costs in proportion to j / (a_j r_j^2), so a probe costs most in a level the agent clears fast; the rule's cost side, j / (a_hat_j r_hat_j^2), is high while few actions have been spent in a level, so the rule waits. The synthetic suites had almost no such levels (B cleared 0 to 3% of its completed levels within three times the human actions), and there always probing did at least as well as the rule on average.

This family adds one such level under control. Arm d1 is the 16 x 16 open room of the cluttered-room suite without clutter. Arm d2 is the same room with level 1 shrunk to a pocket: only the floor within two moves of the exit stays open and the avatar starts two moves away (scripts/make_short.py, --first-dist 2). Levels 2 to 6 are identical in the two arms, so a base room's two games differ only in level 1. The prediction: in d2, always probing spends its probes in level 1, where an action is dearest, while the rule waits and probes later, so the rule beats always probing there, and by more than in d1.

## Pilots and calibration (before this registration)

Pilot games used instance numbers 20 to 23, which no evaluation game uses.

- Pilot 1, an earlier version of the generator that only moved the level-1 start 2, 3, 4 or 6 moves from the exit and left the room open, B and CA, seeds 0 and 1 (runs/syn_short_pilot1): B still wandered the room before finding the exit (median level-1 actions 29 to 567 times the human ones), so moving the start alone does not make level 1 fast. We switched to shrinking the room.
- Pilot 2, the generator of this commit with pocket radius 0, 2 and 3 (game ids f1.., f2.., f3..), B, CA and C at rho = 1e-4 and 1e-2 with q = 0.8, seeds 0 and 1 (runs/syn_short_pilot2): with radius 2, B cleared level 1 in a median 4 actions (twice the human 2) and CA in a median 30.5 (28.5 probes); C made no level-1 probe at rho = 1e-4 and a median of 26.5 at 1e-2. C was above CA in 4 of 4 radius-2 games at both rho, and below it in 4 of 4 (rho = 1e-4) or 2 of 4 (1e-2) open-room games. Radius 3 left level 1 slow for B (median 17 times the human actions), so we chose radius 2.
- Pilot games: `scripts/make_short.py --size 16 --first-dist 0,2,3 --pilot 20,21,22,23`.

Calibration followed the registered procedure on 12 calibration games (base rooms 5 to 10 in both arms, `scripts/make_short.py --size 16 --first-dist 0,2 --calib 5,6,7,8,9,10 --out synthetic/short`), seeds 0 to 2:

- q per arm from B's completion rate: d1 0.754, d2 0.684 (runs/syn_short_q.json, runs/syn_short_calibB).
- rho from {1e-4, 3e-4, 1e-3, 3e-3, 1e-2} by C's mean RHAE: 1.084, 1.227, 1.271, 1.686 and 0.989, so rho = 3e-3 (runs/syn_short_calibC). With this rho and q, the rule (r_hat = 5 in level 1) first allows a level-1 probe after 7 actions in d1 and after 9 in d2. On the calibration games C made a median of 25.5 level-1 probes in d1 and 0 in d2, and its mean RHAE was 1.318 in d1 and 2.054 in d2 (B: 0.151 and 1.633).

## Fixed design

- Games: 24 evaluation games, 12 base rooms (instances 50 to 61) in both arms, generated after this registration with `scripts/make_short.py --size 16 --first-dist 0,2 --eval 50,51,52,53,54,55,56,57,58,59,60,61 --out synthetic/short` and checked with scripts/verify_synthetic.py.
- Parameters from calibration, unchanged: rho = 3e-3, q per arm from runs/syn_short_q.json.
- Configurations: B, C and the always-probe control CA.
- Seeds 60 to 64, not used before. Caps as before: 1,500 actions per level, 15,000 per game.
- Command:

```
P=.venv/bin/python
$P scripts/run_experiments.py --env-dir synthetic/short --tags short,eval --configs B,C,CA --rho 0.003 --q runs/syn_short_q.json --seeds 60,61,62,63,64 --jobs 2 --no-step-logs --out runs/syn_short_confirm
```

## Tests and criteria

`scripts/analyze_short.py runs/syn_short_confirm/results.jsonl`. Per game, each configuration's mean RHAE over the five seeds. One-sided sign tests, ties dropped; a test passes when the first configuration is above the second in at least 60% of the untied games (or base rooms) and p < 0.05.

Primary:

- S1: in arm d2, C is above CA.
- S2: within base rooms, C minus CA is larger in d2 than in d1.

Secondary:

- S3: in arm d2, the median number of level-1 probes over runs is 0 for C and at least 5 for CA.
- S4: in arm d1, C is above CA.
- S5: in arm d2, C is above B.

Descriptive: mean RHAE, levels completed and level 1's part of the score per configuration and arm, CA against B and C against B in each arm, level-1 actions and probes.

## Predictions

- S1 and S2 pass: with a short first level, the rule beats always probing, and by more than with the open first level.
- S3 passes: the rule waits in the short level 1 and always probing does not.
- S4 fails: with the open first level the rule probes early too (after 7 actions), as in the other room suites, and does not beat always probing.
- S5 passes.

## Reporting

Every result goes into the paper and the appendix, whatever it shows. If S1 or S2 fails, the paper says so where it states the account of when probing pays.
