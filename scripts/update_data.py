"""Build compact weekly player/matchup data for the browser app."""
from datetime import datetime, timezone
from pathlib import Path
import json
import nflreadpy as nfl
import polars as pl
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"players.json"; OUT.parent.mkdir(exist_ok=True)
year=datetime.now(timezone.utc).year; frames=[]; loaded=[]
for season in range(year-2,year+1):
    try: frames.append(nfl.load_player_stats([season])); loaded.append(season)
    except Exception as e: print(f"Skipping unavailable {season}: {e}")
if not frames: raise RuntimeError("No nflverse player data available")
stats=pl.concat(frames,how="diagonal_relaxed").filter((pl.col("season_type")=="REG")&pl.col("position").is_in(["QB","RB","WR","TE"]))
try:
    roster=nfl.load_rosters([year]).select(["gsis_id","team"]).drop_nulls().unique("gsis_id",keep="last")
    stats=stats.join(roster,left_on="player_id",right_on="gsis_id",how="left",suffix="_roster").with_columns(pl.coalesce(["team_roster","team"]).alias("current_team"))
except Exception: stats=stats.with_columns(pl.col("team").alias("current_team"))
schedule=nfl.load_schedules([year]).filter(pl.col("game_type")=="REG"); today=datetime.now(timezone.utc).date().isoformat(); upcoming=schedule.filter(pl.col("gameday")>=today).sort(["gameday","gametime"])
COORDS={"ARI":[33.5276,-112.2626],"ATL":[33.7554,-84.4008],"BAL":[39.278,-76.6227],"BUF":[42.7738,-78.787],"CAR":[35.2258,-80.8528],"CHI":[41.8623,-87.6167],"CIN":[39.0954,-84.516],"CLE":[41.5061,-81.6995],"DAL":[32.7473,-97.0945],"DEN":[39.7439,-105.0201],"DET":[42.34,-83.0456],"GB":[44.5013,-88.0622],"HOU":[29.6847,-95.4107],"IND":[39.7601,-86.1639],"JAX":[30.3239,-81.6373],"KC":[39.0489,-94.4839],"LA":[33.9535,-118.3392],"LAC":[33.9535,-118.3392],"LV":[36.0908,-115.183],"MIA":[25.958,-80.2389],"MIN":[44.9736,-93.2575],"NE":[42.0909,-71.2643],"NO":[29.9511,-90.0812],"NYG":[40.8135,-74.0745],"NYJ":[40.8135,-74.0745],"PHI":[39.9008,-75.1675],"PIT":[40.4468,-80.0158],"SEA":[47.5952,-122.3316],"SF":[37.403,-121.97],"TB":[27.9759,-82.5033],"TEN":[36.1665,-86.7713],"WAS":[38.9076,-76.8645]}
def matchup(team):
    rows=upcoming.filter((pl.col("away_team")==team)|(pl.col("home_team")==team))
    if rows.is_empty(): return None
    g=rows.row(0,named=True); home=g["home_team"]==team; opp=g["away_team"] if home else g["home_team"]; margin=g["spread_line"]
    return {"week":int(g["week"]),"date":g["gameday"],"time_et":g["gametime"],"opponent":opp,"home":home,"stadium":g["stadium"],"indoors":str(g["roof"]).lower() in ("dome","closed"),"rest":int(g["home_rest"] if home else g["away_rest"]),"market_favored_by":None if margin is None else float(margin if home else -margin),"fanduel_favored_by":None,"total":None if g["total_line"] is None else float(g["total_line"]),"coordinates":COORDS.get(g["home_team"])}
cols=["passing_yards","attempts","rushing_yards","carries","receiving_yards","receptions","targets"]
players=[]
for key,g in stats.sort(["season","week"],descending=True).group_by("player_id",maintain_order=True):
    recent=g.head(8); first=recent.row(0,named=True); team=first["current_team"]; games=[]
    for r in recent.iter_rows(named=True): games.append({"season":int(r["season"]),"week":int(r["week"]),"opponent":r["opponent_team"],**{c:float(r[c] or 0) for c in cols}})
    av={c:sum(x[c] for x in games)/len(games) for c in cols}; markets=[]
    if av["attempts"]>=10: markets.append("passing")
    if av["carries"]>=3: markets.append("rushing")
    if av["targets"]>=3: markets.extend(["receiving","receptions"])
    game=matchup(team)
    if not markets or game is None: continue
    players.append({"id":str(key[0] if isinstance(key,tuple) else key),"name":first["player_display_name"],"position":first["position"],"team":team,"markets":markets,"games":games,"upcoming":game,"scores":{"passing":av["attempts"],"rushing":av["carries"],"receiving":av["targets"],"receptions":av["targets"]}})
selected={p["id"]:p for p in players if p["team"]=="CHI"}
for market,limit in [("passing",40),("rushing",55),("receiving",75),("receptions",75)]:
    eligible=sorted((p for p in players if market in p["markets"]),key=lambda p:p["scores"][market],reverse=True)[:limit]
    selected.update({p["id"]:p for p in eligible})
players=list(selected.values())
for p in players:p.pop("scores",None)
OUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"seasons_loaded":loaded,"players":sorted(players,key=lambda p:p["name"])},separators=(",",":")),encoding="utf-8")
print(f"Wrote {len(players)} players to {OUT}")
