"""Matched-sample walk-forward test of lagged NFL Next Gen Stats features."""
from pathlib import Path
import numpy as np
import pandas as pd
import nflreadpy as nfl
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"backtests"; OUT.mkdir(exist_ok=True)
old=pd.read_csv(ROOT.parent/"nfl_prop_consistency/data/player_stats.csv",low_memory=False).rename(columns={"recent_team":"team"})
def as_pandas(frame,name):
    path=OUT/name; frame.write_csv(path); result=pd.read_csv(path,low_memory=False); path.unlink(); return result
new=as_pandas(nfl.load_player_stats([2025]),"_player_2025.csv")
keep=["player_id","player_display_name","position","team","season","week","season_type","opponent_team","passing_yards","attempts","rushing_yards","carries","receiving_yards","receptions","targets"]
stats=pd.concat([old[keep],new[keep]],ignore_index=True).query("season_type == 'REG' and season >= 2016").copy()
games=pd.read_csv(ROOT.parent/"nfl_prop_consistency/data/games.csv")
games=games.query("game_type == 'REG'")
home=games[["season","week","home_team","spread_line","total_line","home_rest","roof","temp","wind"]].rename(columns={"home_team":"team","home_rest":"rest"}); home["home"]=1; home["favored_by"]=home.spread_line
away=games[["season","week","away_team","spread_line","total_line","away_rest","roof","temp","wind"]].rename(columns={"away_team":"team","away_rest":"rest"}); away["home"]=0; away["favored_by"]=-away.spread_line
sched=pd.concat([home,away]); sched["indoors"]=sched.roof.astype(str).str.lower().isin(["dome","closed"]).astype(int)
stats=stats.merge(sched[["season","week","team","home","favored_by","total_line","rest","indoors","temp","wind"]],on=["season","week","team"],how="left")

SETS={
 "passing":("passing_yards","attempts",["QB"],15,"passing",["avg_time_to_throw","avg_completed_air_yards","avg_intended_air_yards","aggressiveness","avg_air_yards_to_sticks","passer_rating","expected_completion_percentage","completion_percentage_above_expectation"]),
 "rushing":("rushing_yards","carries",["QB","RB","WR"],4,"rushing",["efficiency","percent_attempts_gte_eight_defenders","avg_time_to_los","expected_rush_yards","rush_yards_over_expected_per_att","rush_pct_over_expected"]),
 "receiving":("receiving_yards","targets",["RB","WR","TE"],3,"receiving",["avg_cushion","avg_separation","avg_intended_air_yards","percent_share_of_intended_air_yards","catch_percentage","avg_yac","avg_expected_yac","avg_yac_above_expectation"]),
 "receptions":("receptions","targets",["RB","WR","TE"],3,"receiving",["avg_cushion","avg_separation","avg_intended_air_yards","percent_share_of_intended_air_yards","catch_percentage","avg_yac","avg_expected_yac","avg_yac_above_expectation"]),
}
cache={}
rows=[]
for market,(target,usage,positions,min_usage,kind,ngcols) in SETS.items():
    if kind not in cache:
        cache[kind]=as_pandas(nfl.load_nextgen_stats(seasons=list(range(2016,2026)),stat_type=kind),f"_ngs_{kind}.csv").query("season_type == 'REG'")
    ng=cache[kind].rename(columns={"player_gsis_id":"player_id"})[["player_id","season","week"]+ngcols]
    df=stats[stats.position.isin(positions)].copy()
    if market=="passing": df=df.sort_values("attempts").groupby(["season","week","team"],as_index=False).tail(1)
    df=df.merge(ng,on=["player_id","season","week"],how="left").sort_values(["player_id","season","week"])
    grp=df.groupby("player_id",sort=False)
    for col in [target,usage]:
        prior=grp[col].shift(1)
        for w in (3,5,8): df[f"{col}_mean_{w}"]=prior.groupby(df.player_id).transform(lambda s:s.rolling(w,min_periods=2).mean())
        df[f"{col}_std_5"]=prior.groupby(df.player_id).transform(lambda s:s.rolling(5,min_periods=3).std())
    df["efficiency_mean_5"]=(grp[target].shift(1)/grp[usage].shift(1).replace(0,np.nan)).groupby(df.player_id).transform(lambda s:s.rolling(5,min_periods=2).mean())
    for col in ngcols:
        df["ngs_"+col]=grp[col].shift(1).groupby(df.player_id).transform(lambda s:s.rolling(5,min_periods=2).mean())
    df["ngs_games"]=grp[ngcols[0]].shift(1).notna().groupby(df.player_id).cumsum()
    base=["week","home","favored_by","total_line","rest","indoors","temp","wind","efficiency_mean_5",f"{target}_std_5",f"{usage}_std_5"]+[f"{c}_mean_{w}" for c in [target,usage] for w in (3,5,8)]
    plus=base+["ngs_"+c for c in ngcols]
    df=df[(df.ngs_games>=2)&(df[f"{usage}_mean_5"]>=min_usage)].copy()
    for season in range(2018,2026):
        tr=df[df.season<season]; te=df[df.season==season]
        if len(te)==0: continue
        preds={}
        for name,features in [("current",base),("current_plus_ngs",plus)]:
            model=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=20)).fit(tr[features],tr[target])
            preds[name]=np.maximum(0,model.predict(te[features]))
            rows.append({"market":market,"season":season,"model":name,"games":len(te),"mae":mean_absolute_error(te[target],preds[name]),"bias":float(np.mean(te[target]-preds[name]))})

r=pd.DataFrame(rows); r.round(4).to_csv(OUT/"ngs_season_metrics.csv",index=False)
overall=r.groupby(["market","model"]).apply(lambda x:pd.Series({"games":x.games.sum(),"weighted_mae":np.average(x.mae,weights=x.games),"weighted_bias":np.average(x.bias,weights=x.games)}),include_groups=False).reset_index()
overall.round(3).to_csv(OUT/"ngs_overall_metrics.csv",index=False)
print(overall.round(3).to_string(index=False))
for market,g in r.pivot(index=["market","season"],columns="model",values="mae").reset_index().groupby("market"):
    print(market,"NGS wins",int((g.current_plus_ngs<g.current).sum()),"of",len(g),"seasons")
