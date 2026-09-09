# Slaws Betting Tool

A Bears-themed, browser-based player-prop projection tool with tabs for passing
yards, rushing yards, receiving yards, receptions, and a Chicago Bears weekly
projection board. Player logs, matchups, consensus spread, total, rest, venue,
and available weather load automatically. Player cards now require a current
roster match when the roster feed is available; explicit out, doubtful,
reserve, suspended, released, and practice-squad statuses are withheld.

The Browse screen includes player search, team filters, market and consistency
sorting, team-color cards, and a plain-language projection breakdown. The
Consistency Board surfaces steady recent roles while clearly separating role
stability from sportsbook value. See `CLAUDE_INTEGRATION_AUDIT.md` for the
design and viability review that shaped these choices.

The interface also includes player search, team filters, projection/consistency
sorting, a cross-market Consistency Board, and a transparent “Why this number?”
panel. See [CLAUDE_INTEGRATION_AUDIT.md](CLAUDE_INTEGRATION_AUDIT.md) for the
design import and viability decisions.

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
weather. Rushing also uses a tested opportunity × efficiency model with carry
share, snaps, depth chart, and backfield injury context. Validation is
walk-forward by season: each 2018–2025 test season was predicted using prior
seasons only. See [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md) and the files under
`backtests/` for the complete season-level results.

The models do not recommend or place bets. Use them for paper testing and
disciplined recordkeeping; projections can miss injuries and late role changes.

Each player detail also shows three lower alternative-line examples with an
estimated over probability and model-implied fair odds. These estimates use the
walk-forward residual distribution and are a research aid, not a substitute for
the actual FanDuel line and price.

The price evaluator accepts the current FanDuel alternative line and American
odds, calculates the sportsbook break-even probability, and compares it with
the calibrated model estimate. The line and odds stay in the browser and are
not uploaded. Automatic NFL FanDuel player-prop prices are intentionally not
claimed: the documented provider examined during development requires a paid
business feed for NFL props.

## Weekly context and risk screen

The free weekly refresh also collects current depth position, projected snap
participation from the last three games, weighted offensive-line injuries,
weighted opponent defensive injuries, and the opponent's recent quarterback
hit/sack rate when play-by-play is available. These fields appear in “Why this
number?” and can force the price evaluator to pass when availability, starter
status, or expected participation is weak.

These new context fields are not silently inserted into the existing yardage
coefficients. They must first be added to walk-forward training and demonstrate
out-of-sample improvement. Routes run, late inactive announcements, coaching
changes, and sportsbook line movement remain explicitly unverified because the
project does not currently have dependable free feeds for them.

## Offseason roster adjustment

Receiving-yard and reception projections include a roster target-redistribution
layer. It sums the recent target demand brought by the current RB/WR/TE room,
compares that demand with the current quarterback room's recent passing
capacity, and partially scales each player's projection. The adjustment also
records whether the player changed teams, how many recent games came with the
current team, and how many skill-position additions joined the roster.

The adjustment strength is 55%, selected from a 2018–2025 Week 1–4 transition
backtest rather than applied at full force. It improved receptions MAE from
1.105 to 1.084 and receiving-yards MAE from 14.05 to 13.86 across 1,760 player
seasons. This handles target competition such as an established receiver
joining a crowded room, but it cannot fully predict a new coaching scheme or an
unannounced Week 1 snap rotation.

## Slip Builder and paper testing

The main page includes a compact Best Model Spot and two-leg paper-parlay
banner. Candidates must clear roster, participation, and consistency screens.
The two-leg example excludes same-team and same-game combinations, and every
leg shows the minimum FanDuel price needed to preserve a five-percentage-point
model edge. A banner selection is not labeled as value until its live price is
entered and evaluated.

The Slip Builder also contains a complete projected-line catalog. It ranks
player props by modeled over probability by default, can be filtered or sorted
by team, and supports one-click `+` additions without first opening each player.
Users then enter current FanDuel prices for the selected legs and submit the
whole slip for feedback. The feedback checks consistency, availability,
modeled probability, price edge, number of legs, and same-team or same-game
correlation. Multiple legs are combined only as an independence estimate when
no correlation warning is present. Slips can be saved to the local Paper
Tracker, settled manually, and reviewed through win rate, units, drawdown, and
losing-streak summaries. No wagers are placed.

## SGP Builder

The SGP Builder lets a user select a matchup and request two through five legs.
It recommends the highest-rated eligible props from that game using individual
model probability, role consistency, availability, starter status, and expected
participation. It favors different players before repeating a player.

Joint SGP estimates use a Gaussian-copula simulation whose correlation matrix
is learned from walk-forward prediction residuals. Relationships distinguish
same-player props, QB-to-receiver stacks, other teammates, opposing QBs, and
other opponents. Correlations are shrunk toward zero based on sample size and
are ignored below the published minimum sample. See
`backtests/sgp_correlation_summary.csv`. The resulting estimate is still not a
guarantee and requires comparison with the current FanDuel line and price.
Recommended legs can be sent directly to the Slip Builder for that check.

## Screenshot review

The Bet Slip Review tab accepts a cropped screenshot and attempts local
browser-based OCR using Tesseract.js. It matches exact recognized player names
to the projection tool but does not trust OCR-extracted odds automatically.
Users are warned to remove names, balances, account information, locations,
QR codes, and bet identifiers before selecting an image. Screenshots and
paper-bet records remain in the browser.

Data: [nflverse](https://nflverse.nflverse.com/) / CC-BY 4.0 where applicable.
