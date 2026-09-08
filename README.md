# NFL QB Prop Consistency Tool

A browser-based, consistency-first quarterback passing-yards projection tool.
The public page automatically loads recent quarterback game logs generated from
free nflverse data. It reports a projected passing-yard total, historical
uncertainty range, and workload-stability grade. The user can independently
compare that projection with standard or alternate sportsbook lines.

## Data refresh

GitHub Actions runs `scripts/update_data.py` every Tuesday at 12:30 UTC and can
also be run manually from the Actions tab. The script attempts the current and
two prior seasons and safely skips a season before its data release exists.

## Privacy

Selections and paper-test records remain in the browser. No entered FanDuel data
is committed to this public repository.

## Important limitation

The browser model was trained on 2018–2024 data and had an average unseen-season
projection error of about 56 yards. It does not recommend or place bets.
Use it for paper testing and disciplined recordkeeping.

Data: [nflverse](https://nflverse.nflverse.com/) / CC-BY 4.0 where applicable.
