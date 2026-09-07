# NFL QB Prop Consistency Tool

A browser-based, consistency-first quarterback passing-yards projection tool.
The public page automatically loads recent quarterback game logs generated from
free nflverse data. The user manually enters the current FanDuel line and game
conditions.

## Data refresh

GitHub Actions runs `scripts/update_data.py` every Tuesday at 12:30 UTC and can
also be run manually from the Actions tab. The script attempts the current and
two prior seasons and safely skips a season before its data release exists.

## Privacy

Selections and paper-test records remain in the browser. No entered FanDuel data
is committed to this public repository.

## Important limitation

The model was trained on 2018–2024 data and had an average historical projection
error of roughly 58 passing yards. It does not guarantee profit or place bets.
Use it for paper testing and disciplined recordkeeping.

Data: [nflverse](https://nflverse.nflverse.com/) / CC-BY 4.0 where applicable.
