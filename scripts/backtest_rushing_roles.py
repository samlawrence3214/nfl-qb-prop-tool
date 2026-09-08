"""Walk-forward rushing test with carry share, snaps, depth and injury context."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import nflreadpy as nfl
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"backtests"; OUT.mkdir(exist_ok=True)
def frame(loader,seasons,name):
    path=OUT/("_"+name+".csv"); loader(seasons).write_csv(path)
    result=pd.read_csv(path,low_memory=False); path.unlink(); return result

old=pd.read_csv(ROOT.parent/"nfl_prop_consistency/data/player_stats.csv",low_memory=False).rename(columns={"recent_team":"team"})
new=frame(nfl.load_player_stats,[2025],"stats25")
cols=["player_id","player_display_name","position","team","season","week","season_type","opponent_team","rushing_yards","carries"]
stats=pd.concat([old[cols],new[cols]],ignore_index=True).query("season_type == 'REG' and position in ['QB','RB','WR'] and season >= 2012").copy()
for c in ["rushing_yards","carries"]: stats[c]=pd.to_numeric(stats[c],errors="coerce").fillna(0)

games=pd.read_csv(ROOT.parent/"nfl_prop_consistency/data/games.csv").query("game_type == 'REG'")
home=games[["season","week","home_team","spread_line","total_line","home_rest","roof","temp","wind"]].rename(columns={"home_team":"team","home_rest":"rest"}); home["home"]=1; home["favored_by"]=home.spread_line
away=games[["season","week","away_team","spread_line","total_line","away_rest","roof","temp","wind"]].rename(columns={"away_team":"team","away_rest":"rest"}); away["home"]=0; away["favored_by"]=-away.spread_line
sched=pd.concat([home,away]); sched["indoors"]=sched.roof.astype(str).str.lower().isin(["dome","closed"]).astype(int)
stats=stats.merge(sched[["season","week","team","home","favored_by","total_line","rest","indoors","temp","wind"]],on=["season","week","team"],how="left")

# Pregame-known injury and depth chart signals.
inj=frame(nfl.load_injuries,list(range(2012,2026)),"injuries").query("game_type == 'REG'")
inj["status_weight"]=inj.report_status.str.lower().map({"out":1.0,"doubtful":.75,"questionable":.25}).fillna(0)
rb_inj=(inj[inj.position.isin(["RB","FB"])].groupby(["season","week","team"],as_index=False)
        .agg(backfield_injury_count=("status_weight","sum")))
depth=frame(nfl.load_depth_charts,list(range(2012,2026)),"depth").query("game_type == 'REG'")
depth["depth_team_num"]=pd.to_numeric(depth.depth_team,errors="coerce")
depth=depth.sort_values("depth_team_num").drop_duplicates(["season","week","gsis_id"])
depth=depth[["season","week","gsis_id","depth_team_num"]]

# Snap values are shifted before rolling; a game cannot use its own snap result.
snaps=frame(nfl.load_snap_counts,list(range(2012,2026)),"snaps").query("game_type == 'REG'")
snaps=snaps[["season","week","team","player","offense_pct"]].drop_duplicates(["season","week","team","player"])
stats=stats.merge(snaps,left_on=["season","week","team","player_display_name"],right_on=["season","week","team","player"],how="left")
stats=stats.merge(depth,left_on=["season","week","player_id"],right_on=["season","week","gsis_id"],how="left")
stats=stats.merge(rb_inj,on=["season","week","team"],how="left")
stats["backfield_injury_count"]=stats.backfield_injury_count.fillna(0)

team_game=stats.groupby(["season","week","team"],as_index=False).carries.sum().rename(columns={"carries":"team_carries"})
stats=stats.merge(team_game,on=["season","week","team"],how="left")
stats["carry_share"]=stats.carries/stats.team_carries.replace(0,np.nan)
stats["carry_rank"]=stats.groupby(["season","week","team"]).carries.rank(method="min",ascending=False)
stats["efficiency"]=stats.rushing_yards/stats.carries.replace(0,np.nan)
stats=stats.sort_values(["player_id","season","week"]); grp=stats.groupby("player_id",sort=False)
for col in ["rushing_yards","carries","efficiency","carry_share","carry_rank","offense_pct"]:
    prior=grp[col].shift(1)
    for w in (3,5,8): stats[f"{col}_mean_{w}"]=prior.groupby(stats.player_id).transform(lambda s:s.rolling(w,min_periods=2).mean())
    stats[f"{col}_last"]=prior
    stats[f"{col}_std_5"]=prior.groupby(stats.player_id).transform(lambda s:s.rolling(5,min_periods=3).std())
stats["carry_share_trend"]=stats.carry_share_mean_3-stats.carry_share_mean_8
stats["snap_trend"]=stats.offense_pct_mean_3-stats.offense_pct_mean_8
stats["prior_games"]=grp.cumcount()
stats["is_qb"]=(stats.position=="QB").astype(int); stats["is_rb"]=(stats.position=="RB").astype(int)

tg=stats.groupby(["season","week","team","opponent_team"],as_index=False)[["rushing_yards","carries"]].sum().sort_values(["opponent_team","season","week"])
tg["opp_eff"]=tg.rushing_yards/tg.carries.replace(0,np.nan)
tg["opp_eff_5"]=tg.groupby("opponent_team").opp_eff.transform(lambda s:s.shift(1).rolling(5,min_periods=2).mean())
stats=stats.merge(tg[["season","week","opponent_team","opp_eff_5"]],on=["season","week","opponent_team"],how="left")

context=["week","home","favored_by","total_line","rest","indoors","temp","wind","is_qb","is_rb"]
base_usage=context+["carries_std_5"]+[f"carries_mean_{w}" for w in (3,5,8)]
role_usage=base_usage+["carry_share_last","carry_share_mean_3","carry_share_mean_5","carry_share_mean_8","carry_share_trend","carry_rank_last","offense_pct_last","offense_pct_mean_3","offense_pct_mean_5","snap_trend","depth_team_num","backfield_injury_count"]
eff_features=context+["opp_eff_5","efficiency_std_5"]+[f"efficiency_mean_{w}" for w in (3,5,8)]
df=stats[(stats.prior_games>=3)&(stats.carries_mean_5>=4)].copy()
rows=[]; pred_rows=[]
for season in range(2018,2026):
    tr=df[df.season<season]; te=df[df.season==season].copy()
    def fit(features,y,sample=None):
        d=tr if sample is None else tr[sample]
        return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=20)).fit(d[features],d[y])
    eff=fit(eff_features,"efficiency",tr.carries>0)
    ep=np.maximum(0,eff.predict(te[eff_features]))
    for name,features in [("two_stage_base",base_usage),("two_stage_roles",role_usage)]:
        usage_model=fit(features,"carries"); up=np.maximum(0,usage_model.predict(te[features])); yp=up*ep
        rows.append({"season":season,"model":name,"games":len(te),"mae":mean_absolute_error(te.rushing_yards,yp),"carry_mae":mean_absolute_error(te.carries,up),"bias":float((te.rushing_yards-yp).mean())})
        if name=="two_stage_roles": pred_rows.append(pd.DataFrame({"season":season,"actual":te.rushing_yards,"base_usage":np.nan,"role_prediction":yp,"role_usage":up},index=te.index))
r=pd.DataFrame(rows); r.round(4).to_csv(OUT/"rushing_roles_season_metrics.csv",index=False)
overall=r.groupby("model").apply(lambda x:pd.Series({"games":x.games.sum(),"weighted_mae":np.average(x.mae,weights=x.games),"carry_mae":np.average(x.carry_mae,weights=x.games),"weighted_bias":np.average(x.bias,weights=x.games)}),include_groups=False).reset_index()
overall.round(3).to_csv(OUT/"rushing_roles_overall_metrics.csv",index=False)
print(overall.round(3).to_string(index=False))
p=r.pivot(index="season",columns="model",values="mae"); print(p.round(3).to_string()); print("role wins",int((p.two_stage_roles<p.two_stage_base).sum()),"of",len(p))

def export(model,features):
    imp,scale,reg=model
    return {"features":features,"medians":imp.statistics_.tolist(),"means":scale.mean_.tolist(),"scales":scale.scale_.tolist(),"coef":reg.coef_.tolist(),"intercept":float(reg.intercept_)}
def train(features,y,sample):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=20)).fit(sample[features],sample[y])
usage_final=train(role_usage,"carries",df)
eff_final=train(eff_features,"efficiency",df[df.carries>0])
payload={"usage":export(usage_final,role_usage),"efficiency":export(eff_final,eff_features)}
(ROOT/"rushing_role_model.js").write_text("const RUSHING_ROLE_MODEL="+json.dumps(payload,separators=(",",":"))+";\n",encoding="utf-8")
