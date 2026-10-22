# Registration: probing on the 25 public games, new seeds

Written on 2026-10-22 (KST) and committed before any run with the seeds below. Agent, runner and analysis script are those of this commit.

## Why

On real games the probe rule (C) did not raise RHAE over its rule-free version (B), and our explorer completes under one level per game. Runs already made at seeds 10 to 14 (B and C on all 25 public games, always probing (CA) on the 10 held-out games) suggest that probing raises the number of levels completed while leaving RHAE almost unchanged:

- Levels completed, game by game: CA above B in 4 held-out games and below in none (6 tied); C above B in 6 of the 25 games and below in 1 (18 tied).
- Game-seed pairs: CA completed more levels than B in 11 of 50 and fewer in 1; C more than B in 9 of 125 and fewer in 2.
- RHAE: CA above B in 5 held-out games, below in 2; C above B in 6 of 25 games, below in 9.

Our explorer takes 7 to 9 times the human actions on the levels it completes, so each extra level adds almost nothing to RHAE. This test checks, on new seeds and all 25 games, whether probing raises the levels completed (reach), and whether it raises RHAE. Those earlier runs motivated it and are not part of it.

## Fixed design

- Games: the 25 public ARC-AGI-3 games (splits.json: 15 design, 10 held-out). The design games were used to choose C's parameters (seeds 0 to 2); B and CA have none.
- Configurations: B; C with rho = 3e-4 and q = 0.5 (the values calibrated on the design games and used by the Kaggle submission); CA.
- Seeds 15 to 34 (20 seeds), not used for real games before. Caps as before: 1,500 actions per level, 15,000 per game.
- Command (on the machine that holds the public games):

```
P=.venv/bin/python
$P scripts/run_experiments.py --configs B,C,CA --rho 0.0003 --q 0.5 --seeds 15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34 --jobs 4 --no-step-logs --out runs/real_seeds15_34
```

## Tests and criteria

`scripts/analyze_real.py runs/real_seeds15_34/results.jsonl`. Per game, each configuration's mean over the 20 seeds of levels completed and of RHAE. One-sided sign tests, ties dropped; a test passes when the first configuration is above the second in at least 60% of the untied games and p < 0.05.

Primary:

- R1: CA completes more levels than B (games).
- R2: C completes more levels than B (games).

Secondary:

- R3: CA has a higher RHAE than B (games).
- R4: C has a higher RHAE than B (games).
- R5, R6: in game-seed pairs whose levels differ, CA (R5) and C (R6) complete more levels than B more often than fewer (one-sided sign test over pairs, p < 0.05). Pairs of one game are not independent, so these describe these 25 games rather than games in general.

Descriptive: C against CA, the held-out and design games separately, totals per configuration.

## Predictions

- R1 and R2 pass: probing raises the levels completed. Uncertain, because many games tie (no configuration clears level 1, or all clear the same levels).
- R3 and R4 fail: no RHAE gain.
- R5 and R6 pass.

## Also reported (exploratory)

A Kaggle submission of CA (the same agent with ARC_AGENT_CONFIG defaulting to CA) is scored on the hidden games and reported whatever it scores, next to the C submission's 0.37.

## Reporting

Every result goes into the paper and the appendix, whatever it shows.
