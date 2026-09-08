# Claude ZIP integration audit

## End goal

Help the user evaluate consistent NFL player-prop alternatives from transparent
weekly projections. The app provides projected totals, uncertainty ranges, and
role stability. A true bet recommendation additionally requires the actual line
and price offered by the sportsbook.

## Integrated

- Player search and team filtering
- Sorting by consistency, projection, or player name
- NFL team-color badges within the Bears navy/orange design
- A 0–10 proportional consistency score
- A Consistency Board covering all four prop markets
- A clear “Why this number?” panel
- Implied game context, live weather on selection, and FanDuel spread override
- Injury, snap, carry-share, depth-chart, and backfield-role data used by the
  validated rushing model

The Broadsheet/DC component was translated into plain HTML, CSS, and JavaScript
so GitHub Pages can serve it without the ZIP's private design runtime.

## Validation findings

The proposed 0–10 score is a display of proportional week-to-week steadiness.
It is not a probability and did not reliably predict smaller absolute projection
errors. The interface labels it accordingly.

The role-aware rushing model was validated separately on 9,212 player-games
from 2018–2025. It reduced rushing MAE from 23.644 to 23.207 yards versus the
basic opportunity model and improved in all eight test seasons.

## Excluded

- “Recommended Bets” wording: without sportsbook line and price history, the
  system cannot backtest expected value or call a projection a bet.
- Parlay suggestions: the ZIP grouped stable players by game but did not model
  correlations or sportsbook prices.
- Defensive pressure as a production feature: it was drafted but never trained
  or backtested. It should only be added after matched walk-forward validation.

## Remaining measurement gap

Projection accuracy is well tested, but betting performance is not. Archived
FanDuel alternative lines and prices are not available in the current free data.
Paper-test logging of the line, odds, timestamp, projection, and result during
the 2026 season will allow coverage rate, calibration, and return to be measured.
