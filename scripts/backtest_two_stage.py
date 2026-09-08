"""Walk-forward matched test: direct projection versus opportunity × efficiency."""
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
tmp=OUT/"_2025.csv"; nfl.load_player_stats([2025]).write_csv(tmp); new=pd.read_csv(tmp,low_memory=False); tmp.unlink()
cols=["player_id","player_display_name","position","team","season","week","season_type","opponent_team","passing_yards","attempts","rushing_yards","carries","receiving_yards","receptions","targets"]
stats=pd.concat([old[cols],new[cols]],ignore_index=True).query("season_type == 'REG'").copy()
games=pd.read_csv(ROOT.parent/"nfl_prop_consistency/data/games.csv").query("game_type == 'REG'")
home=games[["season","week","home_team","spread_line","total_line","home_rest","roof","temp","wind"]].rename(columns={"home_team":"team","home_rest":"rest"}); home["home"]=1; home["favored_by"]=home.spread_line
away=games[["season","week","away_team","spread_line","total_line","away_rest","roof","temp","wind"]].rename(columns={"away_team":"team","away_rest":"rest"}); away["home"]=0; away["favored_by"]=-away.spread_line
sched=pd.concat([home,away]); sched["indoors"]=sched.roof.astype(str).str.lower().isin(["dome","closed"]).astype(int)
stats=stats.merge(sched[["season","week","team","home","favored_by","total_line","rest","indoors","temp","wind"]],on=["season","week","team"],how="left")
SETS={"passing":("passing_yards","attempts",["QB"],15),"rushing":("rushing_yards","carries",["QB","RB","WR"],4),"receiving":("receiving_yards","targets",["RB","WR","TE"],3),"receptions":("receptions","targets",["RB","WR","TE"],3)}
results=[]; predictions=[]
for market,(target,usage,positions,min_usage) in SETS.items():
    df=stats[stats.position.isin(positions)].copy()
    if market=="passing": df=df.sort_values("attempts").groupby(["season","week","team"],as_index=False).tail(1)
    df=df.sort_values(["player_id","season","week"]); grp=df.groupby("player_id",sort=False)
    df["efficiency"]=df[target]/df[usage].replace(0,np.nan)
    for col in [target,usage,"efficiency"]:
        prior=grp[col].shift(1)
        for w in (3,5,8): df[f"{col}_mean_{w}"]=prior.groupby(df.player_id).transform(lambda s:s.rolling(w,min_periods=2).mean())
        df[f"{col}_std_5"]=prior.groupby(df.player_id).transform(lambda s:s.rolling(5,min_periods=3).std())
    df["prior_games"]=grp.cumcount()
    tg=stats.groupby(["season","week","team","opponent_team"],as_index=False)[[target,usage]].sum().sort_values(["opponent_team","season","week"])
    tg["opp_eff"]=tg[target]/tg[usage].replace(0,np.nan)
    tg["opp_allowed_5"]=tg.groupby("opponent_team")[target].transform(lambda s:s.shift(1).rolling(5,min_periods=2).mean())
    tg["opp_eff_5"]=tg.groupby("opponent_team").opp_eff.transform(lambda s:s.shift(1).rolling(5,min_periods=2).mean())
    df=df.merge(tg[["season","week","opponent_team","opp_allowed_5","opp_eff_5"]],on=["season","week","opponent_team"],how="left")
    context=["week","home","favored_by","total_line","rest","indoors","temp","wind"]
    direct=context+["opp_allowed_5",f"{target}_std_5",f"{usage}_std_5"]+[f"{c}_mean_{w}" for c in [target,usage] for w in (3,5,8)]+["efficiency_mean_5"]
    usage_features=context+[f"{usage}_std_5"]+[f"{usage}_mean_{w}" for w in (3,5,8)]
    efficiency_features=context+["opp_eff_5","efficiency_std_5"]+[f"efficiency_mean_{w}" for w in (3,5,8)]
    df=df[(df.prior_games>=3)&(df[f"{usage}_mean_5"]>=min_usage)].copy()
    for season in range(2018,2026):
        tr=df[(df.season<season)&(df.season>=1999)]; te=df[df.season==season].copy()
        if te.empty: continue
        def fit(features,y,rows=None):
            sample=tr if rows is None else tr[rows]
            return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=20)).fit(sample[features],sample[y])
        direct_model=fit(direct,target); usage_model=fit(usage_features,usage); eff_model=fit(efficiency_features,"efficiency",tr[usage]>0)
        te["direct"]=np.maximum(0,direct_model.predict(te[direct]))
        te["projected_usage"]=np.maximum(0,usage_model.predict(te[usage_features]))
        ep=eff_model.predict(te[efficiency_features]); ep=np.clip(ep,0,1 if market=="receptions" else np.inf)
        te["two_stage"]=te.projected_usage*ep
        for name in ["direct","two_stage"]:
            results.append({"market":market,"season":season,"model":name,"games":len(te),"mae":mean_absolute_error(te[target],te[name]),"bias":float((te[target]-te[name]).mean()),"usage_mae":mean_absolute_error(te[usage],te.projected_usage)})
        predictions.append(te.assign(market=market)[["market","season","week","player_display_name","team",target,usage,"direct","two_stage","projected_usage"]].rename(columns={target:"actual",usage:"actual_usage"}))
r=pd.DataFrame(results); r.round(4).to_csv(OUT/"two_stage_season_metrics.csv",index=False)
pd.concat(predictions,ignore_index=True).round(3).to_csv(OUT/"two_stage_predictions.csv",index=False)
overall=r.groupby(["market","model"]).apply(lambda x:pd.Series({"games":x.games.sum(),"weighted_mae":np.average(x.mae,weights=x.games),"weighted_bias":np.average(x.bias,weights=x.games),"usage_mae":np.average(x.usage_mae,weights=x.games)}),include_groups=False).reset_index()
overall.round(3).to_csv(OUT/"two_stage_overall_metrics.csv",index=False)
print(overall.round(3).to_string(index=False))
p=r.pivot(index=["market","season"],columns="model",values="mae").reset_index()
for market,g in p.groupby("market"): print(market,"two-stage wins",int((g.two_stage<g.direct).sum()),"of",len(g),"seasons")
