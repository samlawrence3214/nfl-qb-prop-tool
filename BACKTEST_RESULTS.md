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
