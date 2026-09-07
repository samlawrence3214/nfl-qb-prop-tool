"""Build the small browser dataset from nflverse player game logs."""
from datetime import datetime, timezone
from pathlib import Path
import json
import nflreadpy as nfl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "qbs.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

current = datetime.now(timezone.utc).year
frames = []
loaded = []
for season in range(current - 2, current + 1):
    try:
        frame = nfl.load_player_stats([season])
        frames.append(frame)
        loaded.append(season)
    except Exception as exc:
        print(f"Skipping unavailable {season}: {exc}")

if not frames:
    raise RuntimeError("No player-stat seasons could be downloaded")

import polars as pl
df = pl.concat(frames, how="diagonal_relaxed").filter(
    (pl.col("position") == "QB") & (pl.col("season_type") == "REG")
)
# Keep the primary passer for each team-game, then each player's latest eight.
df = df.sort("attempts").group_by(["season", "week", "team"]).tail(1)
records = []
for key, group in df.sort(["season", "week"], descending=True).group_by("player_id", maintain_order=True):
    games = group.head(8)
    if games.height < 3:
        continue
    first = games.row(0, named=True)
    records.append({
        "id": str(key[0] if isinstance(key, tuple) else key),
        "name": first["player_display_name"],
        "team": first["team"], "total_attempts": float(group["attempts"].sum()),
        "games": [{
            "season": int(r["season"]), "week": int(r["week"]),
            "opponent": r["opponent_team"], "yards": float(r["passing_yards"] or 0),
            "attempts": float(r["attempts"] or 0), "completions": float(r["completions"] or 0),
        } for r in games.iter_rows(named=True)]
    })

records = sorted(records, key=lambda x: x["total_attempts"], reverse=True)[:40]
for record in records:
    record.pop("total_attempts", None)
payload = {"updated_at": datetime.now(timezone.utc).isoformat(),
           "seasons_loaded": loaded, "quarterbacks": sorted(records, key=lambda x: x["name"])}
OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
print(f"Wrote {len(records)} quarterbacks to {OUT}")
