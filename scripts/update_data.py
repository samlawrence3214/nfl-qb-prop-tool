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
MARKET_STATS={"passing":"passing_yards","rushing":"rushing_yards","receiving":"receiving_yards","receptions":"receptions"}
# Last five team-games allowed by each defense. This is computed from prior games
# only and becomes the matchup-strength input to the browser model.
allowed={}
for market,stat in MARKET_STATS.items():
    tg=(stats.group_by(["season","week","team","opponent_team"]).agg(pl.col(stat).sum().alias("value"))
        .sort(["season","week"]))
    for defense,g in tg.group_by("opponent_team"):
        key=defense[0] if isinstance(defense,tuple) else defense
        vals=g.sort(["season","week"],descending=True).head(5)["value"].to_list()
        allowed.setdefault(key,{})[market]=sum(vals)/len(vals) if vals else None

# --- NEW: latest injury report per player. Wrapped in try/except so a schema
# change or an unavailable week doesn't break the whole data build.
injuries={}
try:
    inj=nfl.load_injuries([year])
    latest=inj.sort(["week"],descending=True).unique("gsis_id",keep="first")
    injuries={r["gsis_id"]:r["report_status"] for r in latest.iter_rows(named=True) if r["gsis_id"]}
except Exception as e:
    print(f"Injuries unavailable: {e}")

# --- NEW: rolling 5-game offense snap share per player (pfr_player_id keyed).
snap_share={}
try:
    snaps=nfl.load_snap_counts([year]).sort(["season","week"],descending=True)
    for pid,g in snaps.group_by("pfr_player_id"):
        key=pid[0] if isinstance(pid,tuple) else pid
        vals=g.head(5)["offense_pct"].drop_nulls().to_list()
        if vals: snap_share[key]=sum(vals)/len(vals)
except Exception as e:
    print(f"Snap counts unavailable: {e}")

COORDS={"ARI":[33.5276,-112.2626],"ATL":[33.7554,-84.4008],"BAL":[39.278,-76.6227],"BUF":[42.7738,-78.787],"CAR":[35.2258,-80.8528],"CHI":[41.8623,-87.6167],"CIN":[39.0954,-84.516],"CLE":[41.5061,-81.6995],"DAL":[32.7473,-97.0945],"DEN":[39.7439,-105.0201],"DET":[42.34,-83.0456],"GB":[44.5013,-88.0622],"HOU":[29.6847,-95.4107],"IND":[39.7601,-86.1639],"JAX":[30.3239,-81.6373],"KC":[39.0489,-94.4839],"LA":[33.9535,-118.3392],"LAC":[33.9535,-118.3392],"LV":[36.0908,-115.183],"MIA":[25.958,-80.2389],"MIN":[44.9736,-93.2575],"NE":[42.0909,-71.2643],"NO":[29.9511,-90.0812],"NYG":[40.8135,-74.0745],"NYJ":[40.8135,-74.0745],"PHI":[39.9008,-75.1675],"PIT":[40.4468,-80.0158],"SEA":[47.5952,-122.3316],"SF":[37.403,-121.97],"TB":[27.9759,-82.5033],"TEN":[36.1665,-86.7713],"WAS":[38.9076,-76.8645]}
def matchup(team):
    rows=upcoming.filter((pl.col("away_team")==team)|(pl.col("home_team")==team))
    if rows.is_empty(): return None
    g=rows.row(0,named=True); home=g["home_team"]==team; opp=g["away_team"] if home else g["home_team"]; margin=g["spread_line"]
    mfb=None if margin is None else float(margin if home else -margin)
    total=None if g["total_line"] is None else float(g["total_line"])
    implied=None if (mfb is None or total is None) else total/2+mfb/2  # NEW: implied team total (game-script proxy)
    return {"week":int(g["week"]),"date":g["gameday"],"time_et":g["gametime"],"opponent":opp,"home":home,"stadium":g["stadium"],"indoors":str(g["roof"]).lower() in ("dome","closed"),"rest":int(g["home_rest"] if home else g["away_rest"]),"market_favored_by":mfb,"fanduel_favored_by":None,"total":total,"implied_team_total":implied,"coordinates":COORDS.get(g["home_team"]),"opp_allowed":allowed.get(opp,{})}
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
    pid=str(key[0] if isinstance(key,tuple) else key)
    players.append({"id":pid,"name":first["player_display_name"],"position":first["position"],"team":team,"markets":markets,"games":games,"upcoming":game,
        "injury_status":injuries.get(pid),  # NEW
        "snap_pct_mean_5":snap_share.get(first.get("pfr_player_id")),  # NEW — pfr id may not always match; refine if it comes back empty
        "scores":{"passing":av["attempts"],"rushing":av["carries"],"receiving":av["targets"],"receptions":av["targets"]}})
selected={p["id"]:p for p in players if p["team"]=="CHI"}
for market,limit in [("passing",40),("rushing",55),("receiving",75),("receptions",75)]:
    eligible=sorted((p for p in players if market in p["markets"]),key=lambda p:p["scores"][market],reverse=True)[:limit]
    selected.update({p["id"]:p for p in eligible})
players=list(selected.values())
for p in players:p.pop("scores",None)
OUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"seasons_loaded":loaded,"players":sorted(players,key=lambda p:p["name"])},separators=(",",":")),encoding="utf-8")
print(f"Wrote {len(players)} players to {OUT}")
