"""Backtest offseason roster target redistribution on Weeks 1-4, 2018-2025."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
raw=pd.read_csv(ROOT.parent/"nfl_prop_consistency"/"data"/"player_stats.csv")
raw=raw.rename(columns={"recent_team":"team"})
raw=raw[raw.season_type.eq("REG") & raw.position.isin(["QB","RB","WR","TE"])].copy()
for c in ["targets","receptions","receiving_yards","attempts"]:
    raw[c]=pd.to_numeric(raw[c],errors="coerce").fillna(0)

rows=[]
for season in range(2018,2026):
    prior=raw[raw.season.eq(season-1)].groupby(["player_id","player_display_name","position"],as_index=False).agg(
        prior_games=("week","nunique"),prior_targets=("targets","sum"),prior_receptions=("receptions","sum"),prior_yards=("receiving_yards","sum"),prior_attempts=("attempts","sum"),prior_team=("team","last"))
    for c in ["targets","receptions","yards","attempts"]:prior[f"prior_{c}_pg"]=prior[f"prior_{c}"]/prior.prior_games.clip(lower=1)
    current=raw[(raw.season.eq(season)) & (raw.week.le(4))]
    roster=current.sort_values("week").drop_duplicates("player_id")[["player_id","team"]]
    actual=current.groupby(["player_id","player_display_name","team"],as_index=False).agg(actual_games=("week","nunique"),actual_receptions=("receptions","sum"),actual_yards=("receiving_yards","sum"))
    actual["actual_receptions_pg"]=actual.actual_receptions/actual.actual_games
    actual["actual_yards_pg"]=actual.actual_yards/actual.actual_games
    frame=actual.merge(roster,on=["player_id","team"]).merge(prior,on=["player_id","player_display_name"],how="left")
    frame=frame[frame.prior_games.ge(4) & frame.position.isin(["RB","WR","TE"]) & frame.prior_targets_pg.ge(1)].copy()
    demand=frame.groupby("team").prior_targets_pg.sum()
    qbs=roster.merge(prior,on="player_id",how="left");qbs=qbs[qbs.position.eq("QB")]
    capacity=qbs.groupby("team").prior_attempts_pg.max()
    frame["roster_demand"]=frame.team.map(demand)
    frame["pass_capacity"]=frame.team.map(capacity).fillna(34.0)
    frame["raw_factor"]=(frame.pass_capacity/frame.roster_demand).clip(.65,1.25)
    frame["changed_team"]=(frame.team!=frame.prior_team).astype(int);frame["season"]=season
    rows.append(frame)
df=pd.concat(rows,ignore_index=True)

metrics=[]
for alpha in np.arange(0,1.01,.05):
    factor=1+alpha*(df.raw_factor-1)
    for market,actual,base in [("receptions","actual_receptions_pg","prior_receptions_pg"),("receiving","actual_yards_pg","prior_yards_pg")]:
        pred=df[base]*factor
        metrics.append({"alpha":round(float(alpha),2),"market":market,"player_seasons":len(df),"mae":float(np.mean(np.abs(df[actual]-pred))),"baseline_mae":float(np.mean(np.abs(df[actual]-df[base]))),"changed_team_mae":float(np.mean(np.abs(df.loc[df.changed_team.eq(1),actual]-pred[df.changed_team.eq(1)])))})
metrics=pd.DataFrame(metrics)
winners=metrics.sort_values(["market","mae"]).groupby("market",as_index=False).first()
metrics.to_csv(ROOT/"backtests"/"roster_continuity_grid.csv",index=False)
winners.to_csv(ROOT/"backtests"/"roster_continuity_results.csv",index=False)
alpha=float(winners.set_index("market").loc["receptions","alpha"])
(ROOT/"roster_model.js").write_text("const ROSTER_MODEL="+json.dumps({"target_redistribution_alpha":alpha,"factor_floor":.65,"factor_ceiling":1.25,"source":"2018-2025 Week 1-4 roster-transition backtest"},separators=(",",":"))+";\n",encoding="utf-8")
print(winners.to_string(index=False));print("Selected shared alpha",alpha)
