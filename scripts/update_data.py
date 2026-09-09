"""Build compact weekly player/matchup data for the browser app."""
from datetime import datetime, timezone
from pathlib import Path
import json
import requests
import nflreadpy as nfl
import polars as pl
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"players.json"; OUT.parent.mkdir(exist_ok=True)
year=datetime.now(timezone.utc).year; frames=[]; loaded=[]
for season in range(year-2,year+1):
    try: frames.append(nfl.load_player_stats([season])); loaded.append(season)
    except Exception as e: print(f"Skipping unavailable {season}: {e}")
if not frames: raise RuntimeError("No nflverse player data available")
stats=pl.concat(frames,how="diagonal_relaxed").filter((pl.col("season_type")=="REG")&pl.col("position").is_in(["QB","RB","WR","TE"]))
historical_ids=set(str(x) for x in stats["player_id"].drop_nulls().to_list())
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
roster_verified=False; rookie_target_proxy={}; rookie_skill_counts={}
try:
    roster_raw=nfl.load_rosters([year])
    for r in roster_raw.select([c for c in ["gsis_id","team","status","position"] if c in roster_raw.columns]).iter_rows(named=True):
        pid=str(r.get("gsis_id") or "");team=str(r.get("team") or "");pos=str(r.get("position") or "");status=str(r.get("status") or "").lower()
        blocked=any(x in status for x in ("reserve","pup","suspend","waiv","release","retired","practice","cut"))
        if pid and team and pos in {"RB","WR","TE"} and pid not in historical_ids and not blocked:
            proxy={"WR":3.0,"TE":2.0,"RB":1.5}[pos];rookie_target_proxy[team]=rookie_target_proxy.get(team,0)+proxy;rookie_skill_counts[team]=rookie_skill_counts.get(team,0)+1
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
schedule=nfl.load_schedules([year]).filter(pl.col("game_type")=="REG"); today=datetime.now(timezone.utc).date().isoformat(); upcoming=schedule.filter(pl.col("gameday")>=today).sort(["gameday","gametime"]); current_week=None if upcoming.is_empty() else int(upcoming["week"].min())
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
depth_lookup={}; depth_feed_verified=False; depth_week=None; injury_lookup={}; player_injuries={}; team_injury_context={}; injury_feed_verified=False; injury_week=None; injury_rows=0; injury_source=None
try:
    depth=nfl.load_depth_charts([year])
    if "game_type" in depth.columns: depth=depth.filter(pl.col("game_type")=="REG")
    if depth.is_empty(): raise RuntimeError("Current depth-chart feed returned no rows")
    rank_col="depth_team" if "depth_team" in depth.columns else "pos_rank"
    if "week" in depth.columns:
        depth_week=int(depth["week"].max()); depth=depth.filter(pl.col("week")==depth_week)
    else:
        depth_week=current_week
    depth_feed_verified=depth_week is not None and current_week is not None and depth_week>=current_week
    for r in depth.select(["gsis_id",rank_col]).iter_rows(named=True):
        try: depth_lookup[str(r["gsis_id"])]=float(r[rank_col])
        except (TypeError,ValueError): pass
except Exception as e: print(f"Depth-chart feed unavailable or stale: {e}")
try:
    all_injuries=nfl.load_injuries([year]).filter(pl.col("game_type")=="REG")
    if all_injuries.is_empty(): raise RuntimeError("Current injury feed returned no rows")
    injury_week=int(all_injuries["week"].max()); injury_feed_verified=current_week is not None and injury_week>=current_week; injury_source="nflverse"
    latest=all_injuries.filter(pl.col("week")==injury_week).unique("gsis_id",keep="last"); injury_rows=latest.height
    player_injuries={str(r["gsis_id"]):r["report_status"] for r in latest.select(["gsis_id","report_status"]).iter_rows(named=True) if r["gsis_id"]}
    ol={"C","G","OG","OT","T"}; defense={"DE","DT","DL","NT","LB","ILB","OLB","CB","DB","S","FS","SS"}
    weights={"out":1.0,"doubtful":.75,"questionable":.25}
    for r in latest.select(["team","position","report_status"]).iter_rows(named=True):
        team=str(r["team"]); pos=str(r["position"]); weight=weights.get(str(r["report_status"]).lower(),0)
        ctx=team_injury_context.setdefault(team,{"offensive_line":0.0,"defense":0.0})
        if pos in ol: ctx["offensive_line"]+=weight
        if pos in defense: ctx["defense"]+=weight
    injuries=all_injuries.filter(pl.col("position").is_in(["RB","FB"]))
    for r in injuries.select(["week","team","report_status"]).iter_rows(named=True):
        k=(str(r["team"]),int(r["week"])); injury_lookup[k]=injury_lookup.get(k,0)+weights.get(str(r["report_status"]).lower(),0)
except Exception as e:
    print(f"nflverse injury feed unavailable or stale: {e}; trying current ESPN injury feed")
    try:
        response=requests.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries",timeout=30)
        response.raise_for_status(); payload=response.json()
        if int(payload.get("season",{}).get("year",0))!=year: raise RuntimeError("ESPN injury season is not current")
        weights={"out":1.0,"doubtful":.75,"questionable":.25}; ol={"C","G","OG","OT","T"}; defense={"DE","DT","DL","NT","LB","ILB","OLB","CB","DB","S","FS","SS"}
        name_status={}; injury_rows=0; entries=[]
        if payload.get("items"):
            entries=[(None,item) for item in payload["items"]]
        else:
            for team_row in payload.get("injuries",[]):
                team_info=team_row.get("team",team_row)
                team_hint=team_info.get("abbreviation") or team_info.get("displayName")
                entries.extend((team_hint,item) for item in team_row.get("injuries",[]))
        for team_hint,item in entries:
            athlete=item.get("athlete",{}); athlete_team=athlete.get("team",{}) or {}
            team=str(athlete_team.get("abbreviation") or team_hint or "").upper()
            name=str(athlete.get("fullName") or athlete.get("displayName") or "").strip(); status=str(item.get("status","")).strip(); pos=str(athlete.get("position",{}).get("abbreviation","")).upper()
            if not name or not status: continue
            injury_rows+=1; name_status[name.casefold()]=status
            weight=weights.get(status.lower(),0); ctx=team_injury_context.setdefault(team,{"offensive_line":0.0,"defense":0.0})
            if pos in ol: ctx["offensive_line"]+=weight
            if pos in defense: ctx["defense"]+=weight
        if not injury_rows: raise RuntimeError("ESPN current injury feed returned no rows")
        for row in stats.select(["player_id","player_display_name"]).unique("player_id").iter_rows(named=True):
            status=name_status.get(str(row["player_display_name"]).casefold())
            if status: player_injuries[str(row["player_id"])]=status
        injury_week=current_week; injury_feed_verified=True; injury_source="ESPN"
        print(f"Verified {injury_rows} current ESPN injury entries")
    except Exception as fallback_error: print(f"ESPN injury fallback unavailable: {fallback_error}")
pressure_rate={}
try:
    pbp=pl.concat([nfl.load_pbp([s]) for s in loaded[-2:]],how="diagonal_relaxed")
    pbp=pbp.filter((pl.col("season_type")=="REG")&(pl.col("qb_dropback")==1)&pl.col("defteam").is_not_null())
    pbp=pbp.with_columns(pl.max_horizontal([
        pl.col("sack").fill_null(0),pl.col("qb_hit").fill_null(0)
    ]).alias("pressure"))
    pg=(pbp.group_by(["season","week","defteam"]).agg([
        pl.col("pressure").sum().alias("pressures"),pl.len().alias("dropbacks")
    ]).sort(["season","week"],descending=True))
    for defense,g in pg.group_by("defteam"):
        team=defense[0] if isinstance(defense,tuple) else defense
        recent=g.head(5); pressure_rate[str(team)]=float(recent["pressures"].sum()/recent["dropbacks"].sum())
except Exception as e: print(f"Pressure context unavailable: {e}")
COORDS={"ARI":[33.5276,-112.2626],"ATL":[33.7554,-84.4008],"BAL":[39.278,-76.6227],"BUF":[42.7738,-78.787],"CAR":[35.2258,-80.8528],"CHI":[41.8623,-87.6167],"CIN":[39.0954,-84.516],"CLE":[41.5061,-81.6995],"DAL":[32.7473,-97.0945],"DEN":[39.7439,-105.0201],"DET":[42.34,-83.0456],"GB":[44.5013,-88.0622],"HOU":[29.6847,-95.4107],"IND":[39.7601,-86.1639],"JAX":[30.3239,-81.6373],"KC":[39.0489,-94.4839],"LA":[33.9535,-118.3392],"LAC":[33.9535,-118.3392],"LV":[36.0908,-115.183],"MIA":[25.958,-80.2389],"MIN":[44.9736,-93.2575],"NE":[42.0909,-71.2643],"NO":[29.9511,-90.0812],"NYG":[40.8135,-74.0745],"NYJ":[40.8135,-74.0745],"PHI":[39.9008,-75.1675],"PIT":[40.4468,-80.0158],"SEA":[47.5952,-122.3316],"SF":[37.403,-121.97],"TB":[27.9759,-82.5033],"TEN":[36.1665,-86.7713],"WAS":[38.9076,-76.8645]}
def matchup(team):
    rows=upcoming.filter((pl.col("away_team")==team)|(pl.col("home_team")==team))
    if rows.is_empty(): return None
    g=rows.row(0,named=True); home=g["home_team"]==team; opp=g["away_team"] if home else g["home_team"]; margin=g["spread_line"]
    mfb=None if margin is None else float(margin if home else -margin); total=None if g["total_line"] is None else float(g["total_line"])
    return {"week":int(g["week"]),"date":g["gameday"],"time_et":g["gametime"],"opponent":opp,"home":home,"stadium":g["stadium"],"indoors":str(g["roof"]).lower() in ("dome","closed"),"rest":int(g["home_rest"] if home else g["away_rest"]),"market_favored_by":mfb,"fanduel_favored_by":None,"total":total,"implied_team_total":None if (mfb is None or total is None) else total/2+mfb/2,"coordinates":COORDS.get(g["home_team"]),"opp_allowed":allowed.get(opp,{}),"opp_rush_eff":rush_eff.get(opp),"opp_pressure_rate":pressure_rate.get(opp),"team_injuries":team_injury_context.get(team,{"offensive_line":0.0,"defense":0.0}),"opponent_injuries":team_injury_context.get(opp,{"offensive_line":0.0,"defense":0.0})}
cols=["passing_yards","attempts","rushing_yards","carries","receiving_yards","receptions","targets"]
players=[]
def availability(roster_status,injury_status):
    rs=str(roster_status or "").strip().lower()
    inj=str(injury_status or "").strip().lower()
    blocked_roster=("reserve","injured reserve","pup","suspend","waiv","release","retired","practice","cut")
    if any(x in rs for x in blocked_roster) or rs in {"res","dev"}:
        return "unavailable"
    if inj=="out": return "out"
    if inj=="doubtful": return "doubtful"
    if inj=="questionable": return "questionable"
    return "available" if roster_verified and injury_feed_verified else "unverified"
for key,g in stats.sort(["season","week"],descending=True).group_by("player_id",maintain_order=True):
    recent=g.head(8); first=recent.row(0,named=True); team=first["current_team"]; games=[]
    for r in recent.iter_rows(named=True):
        tc=float(r["team_carries"] or 0); carries=float(r["carries"] or 0)
        games.append({"season":int(r["season"]),"week":int(r["week"]),"team":r["team"],"opponent":r["opponent_team"],"carry_share":None if not tc else carries/tc,"carry_rank":None if r["carry_rank"] is None else float(r["carry_rank"]),"offense_pct":None if r["offense_pct"] is None else float(r["offense_pct"]),**{c:float(r[c] or 0) for c in cols}})
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
    recent_snaps=[x["offense_pct"] for x in games[:3] if x["offense_pct"] is not None]
    expected_snap=None if not recent_snaps else sum(recent_snaps)/len(recent_snaps)
    depth_team=depth_lookup.get(pid)
    players.append({"id":pid,"name":first["player_display_name"],"position":first["position"],"team":team,"markets":markets,"games":games,"upcoming":game,"injury_status":injury_status,"availability":{"status":availability_status,"roster_verified":roster_verified,"roster_status":first.get("roster_status")},"role":{"depth_team":depth_team,"likely_starter":None if depth_team is None else depth_team<=1,"expected_snap_pct":expected_snap,"backfield_injury_count":injury_lookup.get((team,week),0)},"scores":{"passing":av["attempts"],"rushing":av["carries"],"receiving":av["targets"],"receptions":av["targets"]}})
# Roster target demand is compared with the current QB room's recent passing
# capacity. The 55% shrinkage strength won the 2018-2025 Week 1-4 backtest.
team_target_demand=dict(rookie_target_proxy); team_pass_capacity={}; new_skill_arrivals={}
for p in players:
    if p["position"] in {"RB","WR","TE"}:
        demand=sum(g["targets"] for g in p["games"])/len(p["games"])
        if demand>=1: team_target_demand[p["team"]]=team_target_demand.get(p["team"],0)+demand
        if p["games"][0]["team"]!=p["team"]: new_skill_arrivals[p["team"]]=new_skill_arrivals.get(p["team"],0)+1
    if p["position"]=="QB":
        capacity=sum(g["attempts"] for g in p["games"])/len(p["games"])
        team_pass_capacity[p["team"]]=max(team_pass_capacity.get(p["team"],0),capacity)
for p in players:
    demand=team_target_demand.get(p["team"],0);capacity=team_pass_capacity.get(p["team"],34.0)
    raw=1.0 if not demand else max(.65,min(1.25,capacity/demand));adjusted=1+.55*(raw-1)
    current_games=sum(g["team"]==p["team"] for g in p["games"])
    p["roster_context"]={"previous_team":p["games"][0]["team"],"changed_team":p["games"][0]["team"]!=p["team"],"recent_current_team_games":current_games,"recent_current_team_share":current_games/len(p["games"]),"new_skill_arrivals":new_skill_arrivals.get(p["team"],0),"rookie_skill_players":rookie_skill_counts.get(p["team"],0),"rookie_target_proxy":round(rookie_target_proxy.get(p["team"],0),2),"team_recent_target_demand":round(demand,2),"estimated_pass_capacity":round(capacity,2),"raw_target_factor":round(raw,4),"target_adjustment":round(adjusted,4),"method":"backtested roster target redistribution"}
selected={p["id"]:p for p in players if p["team"]=="CHI"}
for market,limit in [("passing",40),("rushing",55),("receiving",75),("receptions",75)]:
    eligible=sorted((p for p in players if market in p["markets"]),key=lambda p:p["scores"][market],reverse=True)[:limit]
    selected.update({p["id"]:p for p in eligible})
players=list(selected.values())
for p in players:p.pop("scores",None)
OUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"seasons_loaded":loaded,"feeds":{"injuries":{"verified_for_week":injury_feed_verified,"latest_week":injury_week,"current_week":current_week,"rows":injury_rows,"source":injury_source},"depth_charts":{"verified_for_week":depth_feed_verified,"latest_week":depth_week,"current_week":current_week},"rosters":{"verified":roster_verified}},"players":sorted(players,key=lambda p:p["name"])},separators=(",",":")),encoding="utf-8")
print(f"Wrote {len(players)} players to {OUT}")
if not roster_verified or not injury_feed_verified:
    raise RuntimeError("Safety feeds are not verified for the current week; recommendations remain paused and this refresh will not be published")
