"""Walk-forward validation for all four markets. No sportsbook lines are used."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import polars as pl
import nflreadpy as nfl
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"backtests"; OUT.mkdir(exist_ok=True)
old=pd.read_csv(ROOT.parent/"nfl_prop_consistency"/"data"/"player_stats.csv")
new=nfl.load_player_stats([2025]); tmp=OUT/"_2025.csv"; new.write_csv(tmp); newer=pd.read_csv(tmp); tmp.unlink()
old=old.rename(columns={"recent_team":"team"}); keep=["player_id","player_display_name","position","team","season","week","season_type","opponent_team","passing_yards","attempts","rushing_yards","carries","receiving_yards","receptions","targets"]
stats=pd.concat([old[keep],newer[keep]],ignore_index=True).query("season_type == 'REG'").copy()
for c in keep[8:]: stats[c]=pd.to_numeric(stats[c],errors="coerce").fillna(0)
stats=stats.sort_values(["season","week","team","player_id"])

games=pd.read_csv(ROOT.parent/"nfl_prop_consistency"/"data"/"games.csv")
if games.season.max()<2025:
    sg=nfl.load_schedules(list(range(1999,2026))); sp=OUT/"_schedule.csv"; sg.write_csv(sp); games=pd.read_csv(sp); sp.unlink()
games=games[games.game_type.eq("REG")]
home=games[["season","week","home_team","away_team","spread_line","total_line","home_rest","roof","temp","wind"]].rename(columns={"home_team":"team","away_team":"opponent_team","home_rest":"rest"}); home["home"]=1; home["favored_by"]=home.spread_line
away=games[["season","week","away_team","home_team","spread_line","total_line","away_rest","roof","temp","wind"]].rename(columns={"away_team":"team","home_team":"opponent_team","away_rest":"rest"}); away["home"]=0; away["favored_by"]=-away.spread_line
sched=pd.concat([home,away],ignore_index=True); sched["indoors"]=sched.roof.astype(str).str.lower().isin(["dome","closed"]).astype(int)
stats=stats.merge(sched[["season","week","team","home","favored_by","total_line","rest","indoors","temp","wind"]],on=["season","week","team"],how="left")

MARKETS={
 "passing":{"target":"passing_yards","usage":"attempts","positions":["QB"],"min_usage":15,"within":40},
 "rushing":{"target":"rushing_yards","usage":"carries","positions":["QB","RB","WR"],"min_usage":4,"within":15},
 "receiving":{"target":"receiving_yards","usage":"targets","positions":["RB","WR","TE"],"min_usage":3,"within":20},
 "receptions":{"target":"receptions","usage":"targets","positions":["RB","WR","TE"],"min_usage":3,"within":2},
}
all_preds=[]; summaries=[]; ranges={}; exports={}
for market,cfg in MARKETS.items():
    target,usage=cfg["target"],cfg["usage"]; df=stats[stats.position.isin(cfg["positions"])].copy()
    if market=="passing": df=df.sort_values("attempts").groupby(["season","week","team"],as_index=False).tail(1)
    df=df.sort_values(["player_id","season","week"]); grp=df.groupby("player_id",sort=False)
    for col in [target,usage]:
        prior=grp[col].shift(1)
        for w in (3,5,8): df[f"{col}_mean_{w}"]=prior.groupby(df.player_id).transform(lambda s:s.rolling(w,min_periods=2).mean())
        df[f"{col}_std_5"]=prior.groupby(df.player_id).transform(lambda s:s.rolling(5,min_periods=3).std())
    df["efficiency_mean_5"]=(grp[target].shift(1)/grp[usage].shift(1).replace(0,np.nan)).groupby(df.player_id).transform(lambda s:s.rolling(5,min_periods=2).mean())
    df["prior_games"]=grp.cumcount()
    team_game=stats.groupby(["season","week","team","opponent_team"],as_index=False)[target].sum().sort_values(["opponent_team","season","week"])
    team_game["opp_allowed_5"]=team_game.groupby("opponent_team")[target].transform(lambda s:s.shift(1).rolling(5,min_periods=2).mean())
    df=df.merge(team_game[["season","week","opponent_team","opp_allowed_5"]],on=["season","week","opponent_team"],how="left")
    feats=["week","home","favored_by","total_line","rest","indoors","temp","wind","opp_allowed_5","efficiency_mean_5",f"{target}_std_5",f"{usage}_std_5"]+[f"{col}_mean_{w}" for col in [target,usage] for w in (3,5,8)]
    df=df[(df.prior_games>=3)&(df[f"{usage}_mean_5"]>=cfg["min_usage"])].copy()
    market_preds=[]
    for season in range(2018,2026):
        tr=df[(df.season<season)&(df.season>=1999)]; te=df[df.season==season].copy()
        if te.empty: continue
        ridge=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=20)).fit(tr[feats],tr[target])
        hgb=make_pipeline(SimpleImputer(strategy="median"),HistGradientBoostingRegressor(max_iter=220,learning_rate=.045,max_leaf_nodes=18,l2_regularization=8,random_state=26)).fit(tr[feats],tr[target])
        te["ridge"]=np.maximum(0,ridge.predict(te[feats])); te["hgb"]=np.maximum(0,hgb.predict(te[feats])); te["baseline"]=.5*te[f"{target}_mean_3"]+.3*te[f"{target}_mean_5"]+.2*te[f"{target}_mean_8"]
        for model in ["baseline","ridge","hgb"]:
            err=te[target]-te[model]; summaries.append({"market":market,"season":season,"model":model,"games":len(te),"mae":mean_absolute_error(te[target],te[model]),"rmse":mean_squared_error(te[target],te[model])**.5,"bias":err.mean(),"within_threshold_pct":(err.abs()<=cfg["within"]).mean()*100})
        te["market"]=market; market_preds.append(te[["season","week","player_display_name","team",target,"baseline","ridge","hgb"]].rename(columns={target:"actual"}))
    mp=pd.concat(market_preds); all_preds.append(mp)
    pooled=mp.actual-mp.ridge; ranges[market]={"p10":round(float(pooled.quantile(.10)),2),"p25":round(float(pooled.quantile(.25)),2),"p75":round(float(pooled.quantile(.75)),2),"p90":round(float(pooled.quantile(.90)),2)}
    final=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=20)).fit(df[feats],df[target]); imp,sc,reg=final
    exports[market]={"features":feats,"medians":imp.statistics_.tolist(),"means":sc.mean_.tolist(),"scales":sc.scale_.tolist(),"coef":reg.coef_.tolist(),"intercept":float(reg.intercept_),"range":ranges[market]}

pd.DataFrame(summaries).round(4).to_csv(OUT/"season_metrics.csv",index=False)
pd.concat(all_preds,ignore_index=True).round(3).to_csv(OUT/"game_predictions.csv",index=False)
overall=pd.DataFrame(summaries).groupby(["market","model"]).apply(lambda x:pd.Series({"games":x.games.sum(),"weighted_mae":np.average(x.mae,weights=x.games),"weighted_rmse":np.sqrt(np.average(x.rmse**2,weights=x.games)),"weighted_within_pct":np.average(x.within_threshold_pct,weights=x.games)}),include_groups=False).reset_index()
overall.round(3).to_csv(OUT/"overall_metrics.csv",index=False)
(ROOT/"models.js").write_text("const PROP_MODELS="+json.dumps(exports,separators=(",",":"))+";\n",encoding="utf-8")
print(overall.round(2).to_string(index=False)); print("Ranges",ranges)
