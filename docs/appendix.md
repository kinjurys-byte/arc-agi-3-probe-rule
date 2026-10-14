# Technical appendix

Appendix to *Pay for Information Early: a probe rule derived from the ARC-AGI-3 score, and a test of when it pays* (ARC Prize 2026 Paper Track). The paper cites these sections as Appendix A to H. Reference numbers follow the paper's list, repeated at the end.

## A. Interaction protocol notes

- Frames are grids up to 64x64 with values 0-15, and one response can carry several frames when the game animates before settling ([game schema](https://docs.arcprize.org/game-schema)). The agent plans on the settled frame and keeps transient frames as evidence.
- On GAME_OVER only RESET is accepted ([actions](https://docs.arcprize.org/actions.md)). RESET after at least one action restarts the current level, while RESET with no action since the last level transition restarts the whole game, so two consecutive RESETs are forbidden ([RESET](https://docs.arcprize.org/api-reference/commands/start-or-reset-game-instance.md)). Each in-play RESET is counted as one action, as in Tycho [3] and Rodionov [8].
- `available_actions` restricts the action set each turn, and ACTION6 availability does not reveal which coordinates are active ([actions](https://docs.arcprize.org/actions.md)). Coordinates are (x, y) with (0, 0) at the top left.
- `win_levels` in each frame states the level threshold for a win, so the agent should know the number of levels L, and hence the level weights, in advance ([API reference](https://docs.arcprize.org/api-reference/commands/execute-simple-action-1.md)).
- A free ARC API key unlocks all 25 public games ([available games](https://docs.arcprize.org/available-games.md)). After the first download, games are cached and local runs are offline ([starter kit](https://docs.arcprize.org/arc-prize-2026)).
- The agent acts only through the documented actions and does not rely on engine bugs. Human baselines are used only for scoring; the agent never reads them.

## B. Base agent

- State graph: a node is the hash of the settled frame (status-bar lines blanked) plus the available actions; an edge is an (action, click target) transition. Untried actions at the current node come first; otherwise the agent follows the shortest known path to the nearest node with untried actions. RESET is a virtual edge back to the level start, used only when it is shorter by more than 10 actions, and never when no action has been taken since the level started, because that RESET restarts the whole game.
- Click targets: 4-connected single-color components of unmasked cells, at most 48 per state, one click per component. Five priority tiers after [11], with our own rules: 0, a compact component (fill at least 0.5) of a rare color (at most 34% of the foreground area); 1, any other non-background component; 2, components of 2 pixels or fewer; 3, non-background components larger than 1/8 of the frame, and background pockets; 4, large background regions. A level-wide threshold admits a lower tier only when nothing at the current threshold is left to try anywhere reachable, and only if raising it finds something.
- Status bars: border lines leave the state identity when (1) their color histogram changes in at least 75% of transitions (counters, energy bars), (2) they show the same content at the same step count in two lives that took different actions (clocks), or (3) after a RESET they are the only lines that differ from the level start (lives displays). Statistics restart whenever the mask grows.
- Restarts and move budgets: a frame that returns to the level start after an ordinary action, up to masked lines, is a restart by the game. Lives that end at nearly the same length (8 actions or more) through two or more different state-action pairs reveal a move budget; such ends are not blamed on the last action, and planning prefers frontiers reachable within the budget. An action that ends a life four times, or the game twice from the same state, is given up.

## C. Action-effect table

- Type key: ACTION1-5 by id; a click by the clicked component's color and shape (bounding box, size, shape hash). Components of the background color, or of any color above 34% of the foreground area, share one key per color (`c<color>:region`), because floor and walls are cut into new shapes whenever objects move; other components larger than 1/8 of the frame share `c<color>:big`.
- Counts per type: transitions that changed the frame outside masked cells, that did not, and that reached a new state.
- Classes: active (at least one change); no-op (no change in k = 2 clicks, or in k_simple = 4 tries of a simple action, since walls often block moves); unknown (otherwise). Candidates rank by class, then by novelty (the Laplace-smoothed share of a type's transitions that reached a new state), then by tier.
- A rebuilds the table from the current level's transitions only; B, C, C1 and C' keep all of them.

## D. Algorithm

```text
each step:
    follow the current plan while it is still valid
    probe = (C or C1: rule of Appendix E holds) or (C': probes so far < cumulative quota) or CA
    repeat:
        S = untried actions here that are active (or unknown, if probe) within the tier threshold
        if S is not empty:
            if probe and S has unknown actions: take the most salient unknown one   (probe)
            else: take the best ranked action in S                                  (exploit)
        else if a path to a node with such actions exists: follow it
        else if the threshold is below 4: raise it and repeat (kept only if this finds something)
        else: stop
    weak phase: try any untried action here, else walk to the nearest node that has one
level end: r_hat = actions used in the level / shortest winning path in the level graph
caps: 1,500 actions per level, 15,000 per game; every RESET counts as an action
```

## E. Probe rule

Write the action ratio as r = a/h and assume a settled effect saves a fraction ρ of a later level's actions. Saving ρa_i actions in level i is worth (i/W)·2ρ/r_i², one action in level j costs (j/W)·2/(a_j r_j²), and level i is reached with probability q^(i−j). After W and the factor 2 cancel, a probe is taken when

```latex
\rho\sum_{i>j}\frac{i\,q^{\,i-j}}{r_*^{2}}\;>\;\frac{j}{\hat a_j\,\hat r_j^{2}}
```

â_j is the number of actions already spent in level j, r̂_j the efficiency proxy from the previous level (5.0 in level 1), r\* the target ratio for later levels (2.0), and q the completion rate of B on calibration games (levels completed over levels attempted). The left side shrinks as levels pass and the right side shrinks as a level drags on, so probes concentrate early. C1 is C with q = 1. C' is allotted as many probes as C used on the same game and seed, split evenly over the game's levels with unused quota carried forward. The quota of a level it never reaches lapses, and it cannot probe where nothing unknown is left, so it spent 61% of its allotment in rooms, 31% in mazes and 30% on the held-out real games (15.4 probes per room run against 25.2 for C). Unreached levels account for 89% of the unspent quota in rooms and all of it on real games; in mazes 70% of it lay in levels C' did reach, where the stuck agent had already tried the unknown actions. C'r (exploratory on the round-2 games, registered for the replication) gets the same allotment but splits it over the levels C played in that game and seed (those it completed plus the one it stopped in), so less of it lapses: it spent 86% in rooms and 49% in mazes on the round-2 games, and 84% in the replication (C' 65%). CQ is C with q re-estimated from C's own completion rate on the calibration games: in rooms 1.0, 1.0, 0.654 and 0.471. In mazes C's rate equals B's, so CQ would repeat C exactly and was not run. CA (exploratory) always probes: whenever an action of unknown effect is untried in the current state, it comes first.

Figure 2 uses the per-level human baselines of the 25 public games. The last level takes a median 3.9 times the human actions of the first (more in 21 of 25 games). For an agent equally slow in every level, saving one action in level i is worth i·h_1/h_i times saving one in level 1: a median 1.54 in the last level (quartiles 0.86 to 4.32). Saving a fixed share of a level is worth i times as much, whatever the level's length, and that is what the rule assumes information buys.

The discount did not help on average: C1 had a higher mean RHAE than C in rooms (0.590% against 0.580%; 0.940% against 0.745% in the replication), mazes (1.078% against 1.040%) and the held-out real games (0.093% against 0.079%), although C was above C1 in 9 of 12 untied round-2 rooms. CQ also had a higher mean than C (0.651% and 0.886% against 0.580% and 0.745%) but was above it in only 12 of 24 untied games over both room sets.

## F. Hyperparameters

| Parameter | Value | How it was set |
| --- | --- | --- |
| k for clicks / k_simple for ACTION1-5 | 2 / 4 | fixed before the experiments |
| Target ratio r\* / level-1 proxy r̂ | 2.0 / 5.0 | assumed |
| ρ | rooms 1e-2, mazes 3e-4, cluttered rooms 1e-4, real games 3e-4 | best of a five- or six-value grid on calibration games; for rooms the top of the grid (1e-4 to 1e-2), for cluttered rooms its bottom |
| q (difficulty 1 to 4) | rooms 1.000, 0.640, 0.550, 0.357; mazes 1.000, 0.923, 0.654, 0.182; cluttered rooms 0.733, 0.767, 0.933, 1.000; real games 0.5 | B on calibration games |
| q for CQ (difficulty 1 to 4) | rooms 1.000, 1.000, 0.654, 0.471 | C on the room calibration games at ρ = 1e-2 (exploratory) |
| Action caps | 1,500 per level, 15,000 per game | per-level cap as in [8] |
| Click candidates per state / RESET penalty | 48 / 10 actions | fixed |
| Status-bar threshold | 0.75 | fixed |
| Seeds | 3 for calibration, 5 for evaluation, shared across configurations so runs are paired | fixed |

The Kaggle submission runs C with ρ = 3e-4 and q = 0.5, the values calibrated on the 15 public design games.

## G. Logging

Each step logs the step, level, actions in the level, action, click coordinates, type key, reason (probe, exploit, navigate, retry or reset), effect, class, table size, probes in the level and in total, r̂, node and game state. summary.jsonl holds per-level statistics. The mechanism tables and the free-learning diagnosis come from these logs.

## H. Synthetic suites and round history

- Mazes (scripts/make_synthetic.py): six levels of random perfect n×n mazes, n = 6, 8, 10, 12, with the exit at the far end. In levels 1 and 2 the door closes a side branch; from level 3 it sits on the main path, 55 to 80% of the way to the exit. Switch and decoys sit on wall tiles next to reachable floor. Evaluation instances 00-03 (round 1) and 10-13 (round 2), calibration 05-07.
- Rooms (scripts/make_rooms.py): six levels of open n×n rooms, n = 12, 16, 20, 28, chosen by a B-only pilot on calibration instances to match q of about 1.0, 0.85, 0.6 and 0.25. The registration listed candidates n = 6 to 20; none came near 0.25, so 22 to 28 were added before calibration and 28 (q = 0.357) was the closest. The avatar starts near the centre with four open directions; the exit sits in a walled pen in a random corner with two entrances, one closed by the door, and the other is open in levels 1 and 2 only. Switch and decoys sit on the outer wall. Evaluation instances 00-03, calibration 05-07. scripts/verify_synthetic.py replays every level's shortest solution.
- Cluttered rooms (scripts/make_clutter.py): the open rooms above at one size (16x16 floor), with 0, 20, 40 or 60% of the room floor outside the exit pen turned into wall, one random cell at a time, skipping cells whose removal would split the floor; the start, its four neighbours and the cells in front of the pen entrances stay free. At 60% the connectivity rule stops at 55 to 60% per level. The four games of a base room share its layout and the order in which cells are tried, so they differ only in clutter. Pilots on base rooms 20 to 23 (runs/syn_clutter_pilot1 to 3) chose the levels; calibration on base rooms 05 to 07 (seeds 0 to 2) gave q = 0.733, 0.767, 0.933 and 1.000 and ρ = 1e-4 (C's mean RHAE 1.409, 0.645, 1.032, 0.972 and 0.859 for ρ = 1e-4 to 1e-2). At this ρ C first probes after a median 105 actions of level 1 (quartiles 88 and 193), or not before level 1 ends (54 of 240 evaluation runs).
- Round 1 (mazes, instances 00-03, seeds 10-14): H1 passed (0.55); H2 failed (C beat C' in 3 of 10 untied games); H4 failed (Spearman −0.07); H5 below criterion (3 of 8). Two bugs: the click threshold rose to its maximum at the first action of every game, and floor and wall pieces received a new type at every state, so most of C's 83 probes per run were clicks on floor, walls and the border (56 of 67 in one replayed run), and C' spent 17% of its allotment.
- Round 2 (predictions recorded in the working document before the runs, docs/registration_ko.md; runs/syn_rooms_confirm and runs/syn_r2_mazes_confirm, seeds 20 to 24): rooms passed H1 (0.45), H2 (C above C' in 13 of 16, p = 0.011) and H6 (C above B in 12 of 16, p = 0.038), failed H4 (+0.56) and met H5 (C above C1 in 6 of the 8 games of the two largest sizes). Mazes passed H1 (0.59), failed H2 (7 of 14, p = 0.60), H4 (−0.29, p = 0.14) and H6 (6 of 14, p = 0.79), as predicted, and did not meet H5 (3 of 8), which was predicted to be met. Eight of the ten predictions held; the two misses are H4 in rooms and H5 in mazes.
- Mechanism (rooms, replayed with step logs, identical to the evaluation runs): B knew all four moves after level 1 in 33 of 80 runs (9, 13, 11 and 0 of 20 by size) and never used the switch before level 3; C knew all four moves within its first 17 actions and used the switch in level 1 in all 80 runs.
- Ablation (exploratory; rooms without a door in levels 1 and 2, all agents starting with the four moves; 240 runs): C cleared level 3 in 20 of 20 runs in 16x16 rooms against 5 of 20 for B, and 10 of 20 against 0 of 20 in 20x20 rooms; C beat B on levels 3 to 6 in 12 of 14 untied games and in total RHAE in 9 of 16 (mean 1.147 against 0.783).
- Where the room gain came from (figs/figureA1_where_gains_come_from.png): two thirds of C's mean RHAE gain over B (0.31 of 0.47 points) came in levels 1 and 2, and level 1 alone gave 29%; in 28x28 rooms all of it did. With ρ = 1e-2, the top of its calibration grid, the rule held from the first action in 130 of 288 room level-plays and within six actions in 189 of the 248 that were not a game's last level (computed from the rule and the per-level statistics in runs/syn_rooms_confirm). The room results therefore test early probing more than the rule's exact threshold. In the replication 47% of the gain (0.27 of 0.57 points) came in levels 1 and 2.
- Trivial controls (R: repeat an action until the frame stops changing, then the next; K: click every object once, then cycle the simple actions) completed no level in any synthetic game (320 runs). On the 10 held-out public games they completed 8 levels in 100 runs, all by K in one click game (vc33), against 31 and 36 levels for B and C in 50 runs each.
- Spend-matched control and CQ (exploratory, round-2 games and seeds; runs/syn_rooms_spendmatched, runs/syn_r2_mazes_spendmatched, runs/syn_rooms_qC_confirm): C was above C'r in 10 of 16 rooms (p = 0.23; mean RHAE 0.580% against 0.522%) and in 7 of 14 untied mazes. C'r was above B in 13 of 16 rooms (p = 0.011) and C' in 12 of 16 (p = 0.038), so most of the room gain comes from probing before being stuck, almost however the probes are spread. The C and C' runs of this check reproduced the stored round-2 runs exactly (80 of 80 each, in both suites).
- Replication, registered in docs/registration_replication.md and committed (7690e4a, 2026-10-14 14:02 KST) before its games were generated (16 new rooms, instances 10 to 13; seeds 30 to 34; runs/syn_rooms_rep and runs/syn_rooms_rep_qC): H1 passed (0.43), H2 failed (C above C' in 9 of 16, p = 0.40), H4 failed (Spearman +0.19), H5 was not met (3 of 8) and H6 passed (C above B in 13 of 16, p = 0.011). Mean RHAE: A 0.101%, B 0.175%, C 0.745%, C1 0.940%, C' 0.563%, C'r 0.585%. S1: C above C'r in 9 of 16 (p = 0.40); S2: CQ 0.886%, above C in 7 of 12 untied games. Five of the six predictions held; the one for H2 did not. Pooled over the 32 room games: C above B in 25 (p = 0.001), above C' in 22 (p = 0.025), above C'r in 19 (p = 0.19) and above C1 in 13 of 24 untied (C1's mean is higher, 0.765% against 0.662%).
- Always probing (CA, exploratory; runs/syn_rooms_alwaysprobe, runs/syn_rooms_rep_alwaysprobe, runs/syn_r2_mazes_alwaysprobe; the games and seeds of round 2 and the replication): in rooms CA matched C. C was above CA in 9 and below it in 5 round-2 games, 5 and 9 in the replication (14 and 14 of 28 untied pooled; mean RHAE 0.662% for C, 0.756% for CA), and CA beat B in 13 and 15 of 16 (28 of 32 pooled). With ρ = 1e-2 the rule seldom says no in rooms: C1 tied CA in 10 of 16 games in each room set, and CA spent 27.9 probes per room run against 26.1 for C. In mazes CA was above B in 7 and below in 6 of 13 untied games (mean 1.056% against 1.113%), and C was above CA in 8 of 14.
- Free learning (scripts/diagnose_free_learning.py on B and C rerun with step logs, identical to the stored round-2 runs; runs/free_learning_synthetic.json): of the action types C saw work in level 1, B also saw work in level 1 64% in rooms (moves 80%, the switch in 0 of 80 runs) and 98% in mazes (moves 99%, the switch 95%). The rest reached B in rooms in level 2 (38 types), level 3 (43) or never (63). Stuck steps (B trying untried actions after some type had worked) were few in both: a median of 3 per level 1 in rooms and 32 in mazes (0.4% and 3% of B's level-1 actions).
- Cluttered rooms, registered in docs/registration_clutter.md and committed (e931231, 2026-10-14 15:40 KST) before the evaluation games were generated (base rooms 30 to 41 at four levels, seeds 40 to 44; runs/syn_clutter_confirm, runs/syn_clutter_diag): all six predictions held. K1: the mean within-room Spearman correlation of clutter and C's relative gain over B was −0.400 (stratified permutation p = 0.0093); C was above B in 11, 11, 10 and 6 of the 12 rooms at 0, 20, 40 and 60%. K2: B saw the switch work in level 1 in 0, 33, 50 and 67% of runs (+0.781, p < 0.0001). K3: −0.340. H6: C above B in 38 of 48 (p < 0.0001); H1: 0.51; H4: −0.408 (p = 0.0024). Without prediction: H2, C above C' in 30 of 48 (p = 0.056); H5, C above C1 in 4 and below in 8 of the 24 games at 40 and 60% (C equals C1 at 60%, where q = 1). Of the types C saw work in level 1, B also did 77, 78, 88 and 92% by level. Mean RHAE: A 0.233%, B 0.684%, C 1.179%, C1 1.285%, C' 0.993%, C'r 0.992%, CA 1.556%. The absolute gain in mean RHAE did not fall (+0.26, +0.41, +0.66 and +0.65 points by level), because B itself scored higher with more clutter (0.33% to 1.67%); K1 is about the relative gain, as registered. All of C's gain came in levels 3 to 6 (+0.53 points; levels 1 and 2: −0.04), unlike in open rooms. Exploratory: CA was above C in 30 of 48 games and above B in 42 (8 of 12 at 60%). The B and C rows of runs/syn_clutter_diag equal those of runs/syn_clutter_confirm (240 of 240 each).
- Real games, exploratory (seeds 10 to 14; runs/real_diag_heldout, runs/real_diag_design, runs/real_alwaysprobe_heldout, runs/free_learning_real.json): B and C rerun with step logs reproduced the stored held-out runs exactly (100 of 100). Over all 25 public games C was above B in 6 and below in 9 (mean RHAE 0.410% against 0.434%). Of the action types C saw work in level 1, B also saw work in level 1 79% on the held-out and 70% on the design games (clicks 60% and 53%), and it never learned 46 of the 51 held-out types it missed. B cleared level 1 in 52% of held-out and 55% of design runs, C in 60% and 56%. Always probing (CA) on the held-out games: mean RHAE 0.115% (B 0.082%, C 0.079%), above B in 5 and below in 2 of 7 untied games (p = 0.23), 0.82 levels per run (B 0.62, C 0.72).
- Registration: the predictions and decision rules of both rounds were written in a dated working document before the runs; docs/registration_ko.md reproduces them as written (in Korean). It is not a public registry, and this repository was created after the round-2 runs. The replication and the cluttered rooms were registered in this repository before their evaluation games existed (see above).

## References

1. ARC Prize Foundation (2026). [ARC-AGI-3: A New Challenge for Frontier Agentic Intelligence](https://arxiv.org/html/2603.24621v1). arXiv:2603.24621.
2. ARC Prize. [ARC-AGI-3 Scoring Methodology](https://docs.arcprize.org/methodology).
3. Lehmann, J., Aioanei, A., Vahdati, S. (2026). [Tycho: Active Abstraction with Programmatic World Models for ARC-AGI-3](https://arxiv.org/html/2607.28287). arXiv:2607.28287.
4. Zeng, G. et al. (2026). [Schema: Discovering Unknown Environments via Agentic Program Induction](https://arxiv.org/pdf/2609.39140). arXiv:2609.39140.
5. Wu, W. (2026). [Kepler: Auditable World Models for ARC-AGI-3](https://arxiv.org/pdf/2610.00834). arXiv:2610.00834.
6. Tufa Labs (2026). [The Duck: ARC-AGI-3 inference harness](https://github.com/Tufalabs/duck-harness), winning solution to ARC-AGI-3 Milestone 1.
7. Tang, H., Key, D., Ellis, K. (2024). [WorldCoder, a Model-Based LLM Agent: Building World Models by Writing Code and Interacting with the Environment](https://arxiv.org/abs/2402.12275). NeurIPS 2024.
8. Rodionov, S. (2026). [Executable World Models for ARC-AGI-3 in the Era of Coding Agents](https://arxiv.org/html/2605.05138v2). arXiv:2605.05138.
9. Courtis, D., Li, W., Sanner, S. (2026). [OPINE-World: Programmatic World Modeling with Ontology-error-Prioritized Interactive Exploration for ARC-AGI-3](https://arxiv.org/html/2607.01531v2). arXiv:2607.01531.
10. Liew, K. H. (2026). [Explore Before You Solve: The Speed-Depth Trade-off in Epistemic Agents for ARC-AGI-3](https://arxiv.org/pdf/2605.25931). arXiv:2605.25931.
11. Rudakov, E., Shock, J., Cowley, B. U. (2025). [Graph-Based Exploration for ARC-AGI-3 Interactive Reasoning Tasks](https://arxiv.org/abs/2512.24156). arXiv:2512.24156.
