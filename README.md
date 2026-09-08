# Bear Down Prop Lab

A Bears-themed, browser-based player-prop projection tool with tabs for passing
yards, rushing yards, receiving yards, receptions, and a Chicago Bears weekly
projection board. Player logs, matchups, consensus spread, total, rest, venue,
and available weather load automatically.

## Data refresh

GitHub Actions runs `scripts/update_data.py` every Tuesday at 12:30 UTC and can
also be run manually from the Actions tab. The script attempts the current and
two prior seasons and safely skips a season before its data release exists.

## Privacy

Selections and paper-test records remain in the browser. No entered FanDuel data
is committed to this public repository.

## Backtesting

The browser uses compact Ridge models trained on historical player usage and
production, opponent production allowed, game total, spread, rest, venue, and
weather. Validation is walk-forward by season: each 2018–2025 test season was
predicted using prior seasons only. See [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md)
and `backtests/season_metrics.csv` for the complete season-level results.

The models do not recommend or place bets. Use them for paper testing and
disciplined recordkeeping; projections can miss injuries and late role changes.

Data: [nflverse](https://nflverse.nflverse.com/) / CC-BY 4.0 where applicable.
