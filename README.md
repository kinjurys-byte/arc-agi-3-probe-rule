# Pay for Information Early

A probe rule derived from the ARC-AGI-3 score, and a test of when it pays.

This repository holds the agent, the synthetic game suites, the results of every run reported in the paper, the figures and the pre-registration record of an ARC Prize 2026 Paper Track entry. All of it is released under CC0 1.0 (public domain dedication).

- Paper: Kaggle Writeup, ARC Prize 2026 Paper Track (link added after submission)
- Code submission: ARC-AGI-3 Kaggle notebook (link added after submission)
- Technical appendix (A to H, cited by the paper): [docs/appendix.md](docs/appendix.md)

![One step of the agent](figs/figure1_agent_loop.png)

## The idea

ARC-AGI-3 scores each completed level by the square of human over agent actions, capped at 1.15, and weights level i by i. Saving one action in level i is therefore worth i h_i^2 / a_i^3, and saving a share of the level is worth i / r_i^2, with r_i = a_i / h_i the agent's action ratio. Later levels of the 25 public games take more human actions (a median 3.9 times the first), so at equal efficiency one last-level action is worth only a median 1.5 times a first-level one, while a share of a level is worth i times as much (Figure 2). Information saves a share of later levels. A probe (one action spent to learn what an untried action does) is therefore worth buying in level j only if:

```
rho * sum_{i>j} i * q^(i-j) / r_*^2  >  j / (a_hat_j * r_hat_j^2)
```

`rho` is the fraction of a later level's actions that one settled effect saves, `q` the chance of completing each further level, `r_*` the target action ratio (2.0), `a_hat_j` the actions already spent in level j and `r_hat_j` the action ratio of the previous level. The saving is counterfactual: it is zero if the agent would try the same action anyway, for instance while stuck. The two synthetic suites vary exactly that.

## Results

Second pre-registered round and its registered replication on 16 new room games (seeds 30 to 34), 16 evaluation games per suite, five seeds each. Game counts exclude ties, except H5 (out of 8).

| Hypothesis (criterion) | Open rooms | New rooms (replication) | Mazes |
| --- | --- | --- | --- |
| H1 transfer: median B/A actions, levels 3+ (≤ 0.85) | 0.45, pass | 0.43, pass | 0.59, pass |
| H2 placement: C beats C' (≥ 60% of games, p < 0.05) | 13 of 16, p = 0.011, pass | 9 of 16, p = 0.40, fail | 7 of 14, p = 0.60, fail (predicted) |
| H4 depth: gain falls with difficulty (Spearman < 0, p < 0.05) | +0.56, fail | +0.19, fail (predicted) | -0.29, p = 0.14, fail (predicted) |
| H5 discount: C beats C1 in the 8 hardest games (≥ 60%) | 6 of 8, met | 3 of 8, not met | 3 of 8, not met |
| H6 value: C beats B (≥ 60% of games, p < 0.05) | 12 of 16, p = 0.038, pass | 13 of 16, p = 0.011, pass | 6 of 14, p = 0.79, fail (predicted) |
| C beats C'r, the same budget over the levels C reached | 10 of 16, p = 0.23 (exploratory) | 9 of 16, p = 0.40 | 7 of 14, p = 0.60 (exploratory) |
| Mean RHAE (%), B / C / C' | 0.114 / 0.580 / 0.288 | 0.175 / 0.745 / 0.563 | 1.113 / 1.040 / 1.173 |
| Levels completed per run, B / C / C' | 2.49 / 3.60 / 3.23 | 2.58 / 3.61 / 3.52 | 3.09 / 2.80 / 3.20 |

- Predictions were recorded before the runs. Round 2: everything passes in rooms; H2, H4 and H6 fail in mazes. Eight of the ten held: H4 failed in rooms, because early information also made later levels reachable, and H5 was not met in mazes. Replication (docs/registration_replication.md, committed before its games were generated): H1, H2 and H6 pass, H4 fails, no prediction for H5, C does not meet the criterion against C'r, and CQ's mean is at least C's. Five of the six held; H2 did not replicate. H3 (choosing probe targets by information gain) was not run.
- What held up: probing before being stuck. Pooled over the 32 room games, C beat B in 25 (p = 0.001), C' in 22 (p = 0.025) and C'r in 19 (p = 0.19), and C' and C'r each beat B in 25 or more. The timing the rule chooses mattered less than probing at all.
- Two trivial controls, R (repeat an action until the frame stops changing) and K (click every object once), completed no level in any synthetic game (320 runs). On the 10 held-out public games they completed 8 levels in 100 runs, all by K in one click game (vc33), while B and C completed 31 and 36 levels in 50 runs each.
- Kaggle (ARC-AGI-3 public leaderboard): the submitted agent, C with rho = 3e-4 and q = 0.5, scores 0.37 (RHAE in percent).
- On the 10 held-out public games, calibrated on the other 15 (rho = 3e-4, q = 0.5), C was no better than B or C' (mean RHAE 0.082% for B, 0.079% for C, 0.110% for C'). The agent completes under one level per game there, so H1 could not be tested.
- C' could not spend its whole allotment, because the quota of a level it never reached lapsed and, in mazes, little was left unknown: it used 61% in rooms, 31% in mazes and 30% on real games. C'r, which splits the same allotment over the levels C reached, used 86% in rooms (Appendix E).
- The reach discount q did not help: C1 (q = 1) had a higher mean RHAE than C in both suites, the replication and on real games, and in rooms so did CQ, C with q re-estimated from its own completion rate (Appendix E).
- Two thirds of C's room gain over B came in levels 1 and 2 (47% in the replication), and with rho at the top of its grid the rule held within six actions in most room levels, so the rooms test early probing more than the rule's exact threshold (Appendix H).
- Exploratory follow-ups: in rooms, most of C's gain came from learning its four moves early rather than from the designed switch (step-log replays). An ablation that gives every agent its moves and removes the door before level 3 isolates the switch: C beat B on levels 3 to 6 in 12 of 14 untied games, but level-1 probe costs offset this in total RHAE (C above B in 9 of 16).

The first round (mazes only) failed H2 and H4 because of two bugs: the click-priority threshold rose to its maximum at the first action of every game, and floor and wall pieces got a new type key at every state, so most probes went to floor tiles. Its agent is kept in `archive/round1/` and its results in `runs/syn_r1_*`.

## Layout

```
agent/my_agent.py        the agent: configurations A, B, C, C1, CU (C'), CR (C'r) and the controls R, K
scripts/                 run, generate, verify, calibrate and analyze
synthetic/               the generated suites, in the local ARC-AGI-3 game format
  mazes_round1/          six-level mazes n = 6, 8, 10, 12; evaluation 00-03, calibration 05-07
  mazes_round2/          same generator; evaluation 10-13, calibration 05-07
  rooms/                 six-level open rooms n = 12, 16, 20, 28; evaluation 00-03, calibration 05-07
  rooms_ablation/        rooms evaluation games without a door before level 3
  rooms_rep/             new room evaluation games 10-13 for the registered replication
runs/                    one results.jsonl per run (plus console.log where kept)
figs/                    figures 1 to 3, the level-3 replay GIF and the scripts that draw them
docs/appendix.md         technical appendix A to H (protocol, agent, rule, hyperparameters, suites, history)
docs/registration_ko.md  the pre-registration record (Korean, as written before the runs)
docs/registration_replication.md  the replication's registration, committed before its games existed
archive/round1/          the round-1 agent and its q values
splits.json              frozen design / held-out split of the 25 public games
```

## Configurations

Set with `ARC_AGENT_CONFIG` (run_experiments.py does this).

| Config | Behaviour |
| --- | --- |
| A | action-effect table rebuilt from the current level only |
| B | table kept across levels; unknown actions are tried only when the agent is stuck |
| C | B plus the probe rule |
| C1 | C with q = 1 (no reach discount) |
| CU (C') | as many probes as C used on the same game and seed, spread evenly over the levels |
| CR (C'r) | as CU, but spread over the levels C reached in that game and seed, so quota of unreached levels is not lost |
| R | trivial control: repeat one action until the frame stops changing twice, then the next |
| K | trivial control: click every object of a state once, then cycle the simple actions |

CQ in the results is C run with q re-estimated from C's own completion rate (`scripts/calibrate.py qc`, `runs/syn_rooms_qC.json`). The Kaggle submission runs C with the agent's defaults, rho = 3e-4 and q = 0.5, the values calibrated on the 15 public design games. The agent acts only through the documented actions and does not rely on engine bugs; human baselines are used only for scoring and are never read by the agent.

![Level 3 of an open room, B and C side by side](figs/replay_level3_r203_s20.gif)

Level 3 of an open room (16x16, game r203, seed 20), replayed from the confirmation runs. C, which clicked the switch in level 1, clears the level in 29 actions; B, which tries unknown actions only when stuck, needs 1,094.

## Setup

Python 3.12. The agent plugs into the official ARC-AGI-3 agent template (MIT), which is not included here.

```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
git clone https://github.com/arcprize/ARC-AGI-3-Agents vendor/ARC-AGI-3-Agents
git -C vendor/ARC-AGI-3-Agents checkout 4743e7d0aaae0ded0d98a89a7e282e63564cd58b
```

Runs are deterministic: the same game, configuration and seed give the same actions. Rerunning sample games from a clean copy of this repository reproduced the stored results.

## Reproduce

Synthetic suites (already included; regenerating gives the same games):

```
P=.venv/bin/python
$P scripts/make_synthetic.py --sizes 6,8,10,12 --out synthetic/mazes_round1
$P scripts/make_synthetic.py --sizes 6,8,10,12 --eval 10,11,12,13 --out synthetic/mazes_round2
$P scripts/make_rooms.py --sizes 12,16,20,28 --out synthetic/rooms
$P scripts/make_rooms.py --sizes 12,16,20,28 --calib "" --door-from 3 --out synthetic/rooms_ablation
$P scripts/verify_synthetic.py synthetic/rooms
```

Open rooms, second round (calibration, then confirmation):

```
$P scripts/run_experiments.py --env-dir synthetic/rooms --tags rooms,calib --configs B --seeds 0,1,2 --jobs 4 --no-step-logs --out runs/syn_rooms_calibB
$P scripts/calibrate.py q runs/syn_rooms_calibB/results.jsonl > runs/syn_rooms_q.json
$P scripts/run_experiments.py --env-dir synthetic/rooms --tags rooms,calib --configs C --rho 0.0001,0.0003,0.001,0.003,0.01 --q runs/syn_rooms_q.json --seeds 0,1,2 --jobs 4 --no-step-logs --out runs/syn_rooms_calibC
$P scripts/calibrate.py rho runs/syn_rooms_calibC/results.jsonl
$P scripts/run_experiments.py --env-dir synthetic/rooms --tags rooms,eval --configs A,B,C,C1,CU --rho 0.01 --q runs/syn_rooms_q.json --seeds 20,21,22,23,24 --jobs 4 --no-step-logs --out runs/syn_rooms_confirm
$P scripts/analyze_synthetic.py runs/syn_rooms_confirm/results.jsonl
```

Mazes, second round: the same commands with `--env-dir synthetic/mazes_round2 --tags synthetic,calib` (calibration) and `--tags synthetic,eval` (confirmation), the `syn_r2_mazes_` run names, and `--rho 0.0003` in the confirmation run.

Ablation and trivial controls:

```
ARC_PRIOR_MOVES=1 $P scripts/run_experiments.py --env-dir synthetic/rooms_ablation --tags rooms,eval --configs B,C,CU --rho 0.01 --q runs/syn_rooms_q.json --seeds 20,21,22,23,24 --jobs 4 --no-step-logs --out runs/syn_rooms_ablation
$P scripts/run_experiments.py --env-dir synthetic/rooms --tags rooms,eval --configs R,K --seeds 20,21,22,23,24 --jobs 4 --no-step-logs --out runs/syn_rooms_controls
$P scripts/compare_controls.py runs/syn_rooms_confirm/results.jsonl runs/syn_rooms_controls/results.jsonl
```

Exploratory robustness checks on the round-2 games, then the registered replication (`docs/registration_replication.md`):

```
$P scripts/run_experiments.py --env-dir synthetic/rooms --tags rooms,eval --configs C,CU,CR --rho 0.01 --q runs/syn_rooms_q.json --seeds 20,21,22,23,24 --jobs 2 --no-step-logs --out runs/syn_rooms_spendmatched
$P scripts/run_experiments.py --env-dir synthetic/mazes_round2 --tags synthetic,eval --configs C,CU,CR --rho 0.0003 --q runs/syn_r2_mazes_q.json --seeds 20,21,22,23,24 --jobs 2 --no-step-logs --out runs/syn_r2_mazes_spendmatched
$P scripts/calibrate.py qc runs/syn_rooms_calibC/results.jsonl 0.01 > runs/syn_rooms_qC.json
$P scripts/run_experiments.py --env-dir synthetic/rooms --tags rooms,eval --configs C --rho 0.01 --q runs/syn_rooms_qC.json --seeds 20,21,22,23,24 --jobs 2 --no-step-logs --out runs/syn_rooms_qC_confirm
$P scripts/make_rooms.py --sizes 12,16,20,28 --eval 10,11,12,13 --calib "" --out synthetic/rooms_rep
$P scripts/run_experiments.py --env-dir synthetic/rooms_rep --tags rooms,eval --configs A,B,C,C1,CU,CR --rho 0.01 --q runs/syn_rooms_q.json --seeds 30,31,32,33,34 --jobs 2 --no-step-logs --out runs/syn_rooms_rep
$P scripts/run_experiments.py --env-dir synthetic/rooms_rep --tags rooms,eval --configs C --rho 0.01 --q runs/syn_rooms_qC.json --seeds 30,31,32,33,34 --jobs 2 --no-step-logs --out runs/syn_rooms_rep_qC
$P scripts/analyze_synthetic.py runs/syn_rooms_rep/results.jsonl
$P scripts/analyze_extra.py C=runs/syn_rooms_rep/results.jsonl CR=runs/syn_rooms_rep/results.jsonl B=runs/syn_rooms_rep/results.jsonl CQ=runs/syn_rooms_rep_qC/results.jsonl:C --pairs C-CR,CQ-C,C-B
```

`scripts/analyze_extra.py` compares any configurations from any result files game by game and pools files joined with `+`; `--same X,Y` checks that two sets of runs are identical (the C and C' runs of the robustness checks reproduce the stored round-2 runs).

Mechanism (which information C bought early): rerun the confirmation command for B and C without `--no-step-logs`, then `$P scripts/analyze_mechanism.py runs/<dir>/results.jsonl`.

Round 1: copy `archive/round1/my_agent.py` over `agent/my_agent.py` and run `--env-dir synthetic/mazes_round1 --tags synthetic,eval --configs A,B,C,C1,CU --rho 0.0001 --q archive/round1/q_synthetic.json --seeds 10,11,12,13,14`.

Real games: the 25 public ARC-AGI-3 games are not redistributed. Download them into `environment_files/` as described in the [ARC Prize 2026 starter kit](https://docs.arcprize.org/arc-prize-2026); `splits.json` fixes the design and held-out games.

```
$P scripts/run_experiments.py --split design --configs B,C --rho 0.00003,0.0001,0.0003,0.001,0.003,0.01 --q auto --seeds 0,1,2 --jobs 4 --no-step-logs --out runs/real_calib
$P scripts/run_experiments.py --split heldout --configs A,B,C,C1,CU --rho 0.0003 --q 0.5 --seeds 10,11,12,13,14 --jobs 4 --no-step-logs --out runs/real_heldout
$P scripts/run_experiments.py --split heldout --configs R,K --seeds 10,11,12,13,14 --jobs 4 --no-step-logs --out runs/real_controls
$P scripts/compare_controls.py runs/real_heldout/results.jsonl runs/real_controls/results.jsonl
```

Figures: `python figs/make_charts.py` (figures 2 and 3, matplotlib; figure 2 reads the public games' human baselines stored in `runs/real_calib` and `runs/real_heldout`), `python figs/make_figure1.py` (figure 1; the PNG needs Playwright) and `$P figs/make_replay_gif.py` (the replay GIF; it replays the two runs and checks their level-3 action counts against `runs/syn_rooms_confirm`). They use the Inter font when it is installed.

Some result rows record a rho or q that their configuration does not use (A and B ignore both, C' ignores q). Those fields hold the agent's defaults at the time of the run (rho 0.02 and q 1.0 before the Kaggle defaults were set), so a rerun shows different values there; every other field reproduces exactly.

## Known issues

- Level cap: when a level is completed with exactly its 1,500th action, the agent stops before it sees the level change. This happened in 2 of 3,294 recorded runs (rooms A r103 seed 23, round-1 mazes C1 w302 seed 12). It only lowers those scores and changes no reported conclusion. The code is left as run.
- A move blocked by walls in its first four tries is classed as a no-op (k_simple = 4), so in corridors a direction can go unused for a while.

## License

CC0 1.0 Universal; see `LICENSE`. The ARC-AGI-3 agent template used as the harness is MIT-licensed by ARC Prize and is not included. The public ARC-AGI-3 games are not redistributed.
