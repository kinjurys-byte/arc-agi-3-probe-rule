# Registration: replication of the open-room tests

Written on 2026-10-14 (KST) and committed before the replication games were generated or any replication run started. The agent, runner and analysis scripts are those of commit e6d6c12.

## Why

Round 2 found, in 16 open-room evaluation games, that C beat B (H6: 12 of 16, one-sided sign test p = 0.038) and C' (H2: 13 of 16, p = 0.011). Both rest on 16 games. Exploratory checks on the same games since then found two things:

- C'r, a uniform control that splits C's probe count over the levels C reached, so quota of unreached levels is not lost, came close to C: C was above it in 10 of 16 games (p = 0.23); runs/syn_rooms_spendmatched.
- CQ, which is C with q re-estimated from C's own completion rate on the calibration games, raised mean RHAE from 0.580% to 0.651% but was above C in only 5 of 12 untied games; runs/syn_rooms_qC_confirm.

This replication repeats the room tests on 16 new games with new seeds and adds these two controls as secondary tests.

## Fixed design

- Games: open rooms from scripts/make_rooms.py, sizes 12, 16, 20 and 28, new evaluation instances 10 to 13 (16 games), generated after this registration with `scripts/make_rooms.py --sizes 12,16,20,28 --eval 10,11,12,13 --calib "" --out synthetic/rooms_rep` and checked with scripts/verify_synthetic.py.
- Parameters as in round 2, without recalibration: rho = 0.01 and q per difficulty from runs/syn_rooms_q.json (1.0, 0.64, 0.55, 0.357). CQ uses runs/syn_rooms_qC.json (1.0, 1.0, 0.654, 0.471).
- Configurations: A, B, C, C1, C' (CU) and C'r (CR) in one run; CQ in a second run.
- Seeds 30 to 34, not used before. Caps as before: 1,500 actions per level, 15,000 per game.
- Commands:

```
P=.venv/bin/python
$P scripts/run_experiments.py --env-dir synthetic/rooms_rep --tags rooms,eval --configs A,B,C,C1,CU,CR --rho 0.01 --q runs/syn_rooms_q.json --seeds 30,31,32,33,34 --jobs 2 --no-step-logs --out runs/syn_rooms_rep
$P scripts/run_experiments.py --env-dir synthetic/rooms_rep --tags rooms,eval --configs C --rho 0.01 --q runs/syn_rooms_qC.json --seeds 30,31,32,33,34 --jobs 2 --no-step-logs --out runs/syn_rooms_rep_qC
```

## Tests and criteria

Primary, as in round 2 (`scripts/analyze_synthetic.py runs/syn_rooms_rep/results.jsonl`):

- H1: median B/A action ratio on levels 3 and above is at most 0.85.
- H2: C is above C' (mean RHAE per game) in at least 60% of untied games, with one-sided sign test p < 0.05.
- H4: the Spearman correlation of difficulty with the relative gain of C over B is below 0, with one-sided permutation p < 0.05.
- H5: C is above C1 in at least 60% of the 8 games of the two hardest sizes.
- H6: C is above B in at least 60% of untied games, with one-sided sign test p < 0.05.

Secondary (`scripts/analyze_extra.py`):

- S1: C is above C'r in at least 60% of untied games, with one-sided sign test p < 0.05.
- S2: CQ against C and C1: mean RHAE and game counts (descriptive).
- Pooled: the H2, H6 and S1 sign tests over the 32 games of round 2 and the replication (descriptive).

## Predictions

- H1, H2 and H6 pass.
- H4 fails, with a positive correlation as in round 2.
- H5: no prediction.
- S1: C is above C'r in more games than not, but the criterion is not met.
- S2: the mean RHAE of CQ is at least that of C; no prediction for the game counts.

## Reporting

Every result goes into the paper and the appendix, whatever it shows. If H2 or H6 fails here, the abstract says so.
