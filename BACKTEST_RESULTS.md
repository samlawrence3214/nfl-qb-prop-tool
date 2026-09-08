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

## Free-data layers

The deployed model uses nflverse play/player and schedule data plus free weather
from Open-Meteo. nflverse Next Gen Stats is a promising future feature set for
expected rushing yards and efficiency, but it requires a separate, like-for-like
backtest before inclusion. Third-party projection feeds are not scraped into the
public app unless their terms permit automated production use.
