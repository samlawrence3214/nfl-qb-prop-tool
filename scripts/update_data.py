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
team_carries=(stats.filter(pl.col("position").is_in(["QB","RB","WR"]))
    .group_by(["season","week","team"]).agg(pl.col("carries").sum().alias("team_carries")))
stats=stats.join(team_carries,on=["season","week","team"],how="left")
stats=stats.with_columns(pl.col("carries").rank(method="min",descending=True).over(["season","week","team"]).alias("carry_rank"))
try:
    snap_frames=[nfl.load_snap_counts([s]).filter(pl.col("game_type")=="REG") for s in loaded]
    snaps=pl.concat(snap_frames,how="diagonal_relaxed").select(["season","week","team","player","offense_pct"]).unique(["season","week","team","player"])
    stats=stats.join(snaps,left_on=["season","week","team","player_display_name"],right_on=["season","week","team","player"],how="left")
except Exception:
    stats=stats.with_columns(pl.lit(None).cast(pl.Float64).alias("offense_pct"))
roster_verified=False
try:
    roster_raw=nfl.load_rosters([year])
    roster_cols=[c for c in ["gsis_id","team","status"] if c in roster_raw.columns]
    roster=(roster_raw.select(roster_cols).drop_nulls("gsis_id")
        .unique("gsis_id",keep="last"))
    if "status" not in roster.columns:
        roster=roster.with_columns(pl.lit(None).cast(pl.String).alias("status"))
    roster=roster.rename({"team":"roster_team","status":"roster_status"})
    # Inner join is intentional: a historical stat line is not enough evidence
    # that a player is on a current NFL roster.
    stats=stats.join(roster,left_on="player_id",right_on="gsis_id",how="inner")
    stats=stats.with_columns(pl.col("roster_team").alias("current_team"))
    roster_verified=True
except Exception as e:
    # Fail conservatively if the roster feed is temporarily unavailable. Only
    # players with statistics in the newest available season remain eligible.
    print(f"Current roster verification unavailable: {e}")
    newest=int(stats["season"].max())
    stats=stats.filter(pl.col("season")==newest).with_columns([
        pl.col("team").alias("current_team"),
        pl.lit(None).cast(pl.String).alias("roster_status"),
    ])
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
rush_eff={}
rtg=(stats.filter(pl.col("position").is_in(["QB","RB","WR"]))
    .group_by(["season","week","team","opponent_team"])
    .agg([pl.col("rushing_yards").sum().alias("yards"),pl.col("carries").sum().alias("uses")]))
for defense,g in rtg.group_by("opponent_team"):
    key=defense[0] if isinstance(defense,tuple) else defense
    rows=g.sort(["season","week"],descending=True).head(5)
    uses=rows["uses"].sum(); rush_eff[key]=None if not uses else float(rows["yards"].sum()/uses)
depth_lookup={}; injury_lookup={}; player_injuries={}
try:
    depth=nfl.load_depth_charts([year]).filter(pl.col("game_type")=="REG")
    for r in depth.select(["week","gsis_id","depth_team"]).iter_rows(named=True):
        try: depth_lookup[(str(r["gsis_id"]),int(r["week"]))]=float(r["depth_team"])
        except (TypeError,ValueError): pass
except Exception: pass
try:
    all_injuries=nfl.load_injuries([year]).filter(pl.col("game_type")=="REG")
    latest=all_injuries.sort("week",descending=True).unique("gsis_id",keep="first")
    player_injuries={str(r["gsis_id"]):r["report_status"] for r in latest.select(["gsis_id","report_status"]).iter_rows(named=True) if r["gsis_id"]}
    injuries=all_injuries.filter(pl.col("position").is_in(["RB","FB"]))
    weights={"out":1.0,"doubtful":.75,"questionable":.25}
    for r in injuries.select(["week","team","report_status"]).iter_rows(named=True):
        k=(str(r["team"]),int(r["week"])); injury_lookup[k]=injury_lookup.get(k,0)+weights.get(str(r["report_status"]).lower(),0)
except Exception: pass
COORDS={"ARI":[33.5276,-112.2626],"ATL":[33.7554,-84.4008],"BAL":[39.278,-76.6227],"BUF":[42.7738,-78.787],"CAR":[35.2258,-80.8528],"CHI":[41.8623,-87.6167],"CIN":[39.0954,-84.516],"CLE":[41.5061,-81.6995],"DAL":[32.7473,-97.0945],"DEN":[39.7439,-105.0201],"DET":[42.34,-83.0456],"GB":[44.5013,-88.0622],"HOU":[29.6847,-95.4107],"IND":[39.7601,-86.1639],"JAX":[30.3239,-81.6373],"KC":[39.0489,-94.4839],"LA":[33.9535,-118.3392],"LAC":[33.9535,-118.3392],"LV":[36.0908,-115.183],"MIA":[25.958,-80.2389],"MIN":[44.9736,-93.2575],"NE":[42.0909,-71.2643],"NO":[29.9511,-90.0812],"NYG":[40.8135,-74.0745],"NYJ":[40.8135,-74.0745],"PHI":[39.9008,-75.1675],"PIT":[40.4468,-80.0158],"SEA":[47.5952,-122.3316],"SF":[37.403,-121.97],"TB":[27.9759,-82.5033],"TEN":[36.1665,-86.7713],"WAS":[38.9076,-76.8645]}
def matchup(team):
    rows=upcoming.filter((pl.col("away_team")==team)|(pl.col("home_team")==team))
    if rows.is_empty(): return None
    g=rows.row(0,named=True); home=g["home_team"]==team; opp=g["away_team"] if home else g["home_team"]; margin=g["spread_line"]
    mfb=None if margin is None else float(margin if home else -margin); total=None if g["total_line"] is None else float(g["total_line"])
    return {"week":int(g["week"]),"date":g["gameday"],"time_et":g["gametime"],"opponent":opp,"home":home,"stadium":g["stadium"],"indoors":str(g["roof"]).lower() in ("dome","closed"),"rest":int(g["home_rest"] if home else g["away_rest"]),"market_favored_by":mfb,"fanduel_favored_by":None,"total":total,"implied_team_total":None if (mfb is None or total is None) else total/2+mfb/2,"coordinates":COORDS.get(g["home_team"]),"opp_allowed":allowed.get(opp,{}),"opp_rush_eff":rush_eff.get(opp)}
cols=["passing_yards","attempts","rushing_yards","carries","receiving_yards","receptions","targets"]
players=[]
def availability(roster_status,injury_status):
    rs=str(roster_status or "").strip().lower()
    inj=str(injury_status or "").strip().lower()
    blocked_roster=("reserve","injured reserve","pup","suspend","waiv","released","retired","practice")
    if any(x in rs for x in blocked_roster) or rs in {"res","dev"}:
        return "unavailable"
    if inj=="out": return "out"
    if inj=="doubtful": return "doubtful"
    if inj=="questionable": return "questionable"
    return "available" if roster_verified else "unverified"
for key,g in stats.sort(["season","week"],descending=True).group_by("player_id",maintain_order=True):
    recent=g.head(8); first=recent.row(0,named=True); team=first["current_team"]; games=[]
    for r in recent.iter_rows(named=True):
        tc=float(r["team_carries"] or 0); carries=float(r["carries"] or 0)
        games.append({"season":int(r["season"]),"week":int(r["week"]),"opponent":r["opponent_team"],"carry_share":None if not tc else carries/tc,"carry_rank":None if r["carry_rank"] is None else float(r["carry_rank"]),"offense_pct":None if r["offense_pct"] is None else float(r["offense_pct"]),**{c:float(r[c] or 0) for c in cols}})
    av={c:sum(x[c] for x in games)/len(games) for c in cols}; markets=[]
    if av["attempts"]>=10: markets.append("passing")
    if av["carries"]>=3: markets.append("rushing")
    if av["targets"]>=3: markets.extend(["receiving","receptions"])
    game=matchup(team)
    if not markets or game is None: continue
    pid=str(key[0] if isinstance(key,tuple) else key); week=game["week"]
    injury_status=player_injuries.get(pid)
    availability_status=availability(first.get("roster_status"),injury_status)
    if availability_status in {"unavailable","out","doubtful"}: continue
    players.append({"id":pid,"name":first["player_display_name"],"position":first["position"],"team":team,"markets":markets,"games":games,"upcoming":game,"injury_status":injury_status,"availability":{"status":availability_status,"roster_verified":roster_verified,"roster_status":first.get("roster_status")},"role":{"depth_team":depth_lookup.get((pid,week)),"backfield_injury_count":injury_lookup.get((team,week),0)},"scores":{"passing":av["attempts"],"rushing":av["carries"],"receiving":av["targets"],"receptions":av["targets"]}})
selected={p["id"]:p for p in players if p["team"]=="CHI"}
for market,limit in [("passing",40),("rushing",55),("receiving",75),("receptions",75)]:
    eligible=sorted((p for p in players if market in p["markets"]),key=lambda p:p["scores"][market],reverse=True)[:limit]
    selected.update({p["id"]:p for p in eligible})
players=list(selected.values())
for p in players:p.pop("scores",None)
OUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"seasons_loaded":loaded,"players":sorted(players,key=lambda p:p["name"])},separators=(",",":")),encoding="utf-8")
print(f"Wrote {len(players)} players to {OUT}")
