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

## Slip Builder and paper testing

After evaluating a FanDuel line and price, a leg can be added to the Slip
Builder. Multiple legs are combined only as an independence estimate. The tool
flags same-game and same-team combinations because correlated probabilities
cannot be priced by multiplying the individual estimates. Slips can be saved
to the local Paper Tracker, settled manually, and reviewed through win rate,
units, drawdown, and losing-streak summaries. No wagers are placed.

## Screenshot review

The Bet Slip Review tab accepts a cropped screenshot and attempts local
browser-based OCR using Tesseract.js. It matches exact recognized player names
to the projection tool but does not trust OCR-extracted odds automatically.
Users are warned to remove names, balances, account information, locations,
QR codes, and bet identifiers before selecting an image. Screenshots and
paper-bet records remain in the browser.

Data: [nflverse](https://nflverse.nflverse.com/) / CC-BY 4.0 where applicable.
