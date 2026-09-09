# Walk-forward backtest results

Test window: 2018–2025 regular seasons. Training expands from 1999 through the
season immediately before each test season, preventing future-game leakage.
Eligibility requires at least three prior games and meaningful recent usage.

| Market | Player-games | Rolling baseline MAE | Ridge MAE | Improvement | Ridge RMSE |
|---|---:|---:|---:|---:|---:|
| Passing yards | 4,046 | 62.15 | 57.24 | 7.9% | 71.60 |
| Rushing yards | 9,292 | 24.47 | 23.79 | 2.8% | 31.07 |
| Receiving yards | 19,529 | 24.90 | 24.01 | 3.6% | 31.15 |
| Receptions | 19,529 | 1.78 | 1.71 | 4.0% | 2.18 |

The Ridge model beat the rolling baseline on MAE in every tested season for all
four markets (32 of 32 market-seasons). Gradient boosting was also tested; its
pooled MAE was 57.72, 23.77, 23.93, and 1.70 respectively. Ridge was selected
for the browser because it was essentially tied overall, more transparent, and
small enough to run locally without a server.

“Within” rates use descriptive thresholds of 40 passing yards, 15 rushing
yards, 20 receiving yards, and 2 receptions. They do not represent sportsbook
win rates because archived FanDuel alternative lines and prices were not used.
The full raw prediction file is generated locally by
`python scripts/backtest_all_props.py`; season-level and pooled results are
stored under `backtests/`.

## Next Gen Stats test

NFL Next Gen Stats was tested on a matched sample with the same walk-forward
method. Every NGS value was shifted and rolled from prior games, so the current
game's tracking data could not leak into its prediction.

| Market | Matched player-games | Current MAE | Current + NGS MAE | NGS seasons won |
|---|---:|---:|---:|---:|
| Passing yards | 4,055 | 57.103 | 57.058 | 5 of 8 |
| Rushing yards | 6,983 | 25.432 | 25.400 | 6 of 8 |
| Receiving yards | 15,421 | 25.491 | 25.526 | 3 of 8 |
| Receptions | 15,421 | 1.729 | 1.729 | 4 of 8 |

The gains for passing (0.08%) and rushing (0.13%) are too small to justify the
extra dependency, while receiving slightly worsened and receptions were flat.
NGS is therefore **not deployed**. This keeps the production model simpler and
more robust while retaining the test for future re-evaluation.

Third-party projection feeds are not scraped into the public app unless their
terms permit automated production use.

## Opportunity-first test

A second walk-forward experiment split each projection into expected opportunity
and expected efficiency: attempts × yards per attempt, carries × yards per carry,
targets × yards per target, or targets × catch rate.

| Market | Player-games | Direct MAE | Two-stage MAE | Seasons won |
|---|---:|---:|---:|---:|
| Passing yards | 4,046 | 57.282 | 57.528 | 1 of 8 |
| Rushing yards | 9,292 | 23.788 | 23.610 | 8 of 8 |
| Receiving yards | 19,529 | 24.005 | 24.052 | 1 of 8 |
| Receptions | 19,529 | 1.714 | 1.717 | 2 of 8 |

Only rushing improved consistently. Its MAE gain was 0.178 yards (0.75%), with
a row-bootstrap 95% interval of 0.103–0.252 yards. Passing, receiving, and
receptions remain on the direct model. The opportunity-first rushing model is a
promising targeted upgrade, but the practical gain is modest and should be
combined with better role/injury inputs before being treated as a major change.

## Rushing role upgrade

The rushing opportunity model was extended with prior carry share, carry-share
trend, prior offensive snap rate, snap trend, depth-chart position, and weekly
backfield injury counts. All game-result features remain lagged.

| Model | Matched player-games | Rushing MAE | Carry MAE | Seasons won |
|---|---:|---:|---:|---:|
| Opportunity × efficiency | 9,212 | 23.644 | 3.973 | — |
| Opportunity × efficiency + role | 9,212 | 23.207 | 3.843 | 8 of 8 |

The role model reduced rushing error by 0.437 yards (1.85%) versus the basic
two-stage model and by about 2.4% versus the original direct rushing model. It
improved every test season from 2018 through 2025 and is now used for rushing
projections in the site. Other markets continue to use their direct models.

## Consistency-score check

The imported 0–10 score combines recent usage and production variation relative
to the player's average. A matched historical check found that higher scores do
not consistently produce smaller absolute errors; high-volume players can be
steady proportionally while still missing by more raw yards. The site therefore
uses the score for sorting and role context only. It is not displayed as a win
probability or betting edge.
## SGP correlation validation

The SGP component estimates pairwise correlations from walk-forward model
residuals and shrinks each estimate by `n / (n + 150)`. A Gaussian-copula
simulation combines the calibrated marginal probabilities. The correlation
fit used seasons through 2023 and was evaluated on 2024–2025 pairs at 55%, 65%,
and 75% marginal hit-rate thresholds.

Across 333,504 weighted held-out pair tests, the correlation-aware probability
had a Brier score of **0.23498**, compared with **0.23588** for independence.
This is a real but modest improvement. The model therefore reports the joint
estimate with a warning and never treats it as proof that an SGP is valuable.
Full results are in `backtests/sgp_joint_validation.csv`; fitted relationships
are in `backtests/sgp_correlation_summary.csv`.

## Offseason roster continuity

For every season from 2018 through 2025, the roster-transition test inferred
the new team's skill-position roster and used only each player's prior-season
usage. It compared the roster's imported target demand with the current QB
room's prior passing capacity, then evaluated Weeks 1–4. A shared 55% shrinkage
factor performed best across 1,760 eligible player-seasons.

| Market | Prior-usage MAE | Roster-adjusted MAE | Improvement |
|---|---:|---:|---:|
| Receptions | 1.105 | 1.084 | 1.8% |
| Receiving yards | 14.05 | 13.86 | 1.4% |

The improvement is modest, so the model partially reallocates opportunity and
shows the adjustment in “Why this number?” rather than treating roster turnover
as certain. Full grid results are in
`backtests/roster_continuity_grid.csv` and the selected settings are in
`backtests/roster_continuity_results.csv`.
