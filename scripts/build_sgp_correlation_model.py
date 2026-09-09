"""Estimate shrinkage correlations between walk-forward player-prop residuals."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import multivariate_normal, norm

ROOT=Path(__file__).resolve().parents[1]
pred=pd.read_csv(ROOT/"backtests"/"game_predictions.csv")
stats=pd.read_csv(ROOT.parent/"nfl_prop_consistency"/"data"/"player_stats.csv",usecols=["season","week","player_display_name","position","recent_team","opponent_team"])
stats=stats.rename(columns={"recent_team":"team"}).drop_duplicates(["season","week","player_display_name","team"])
pred=pred.merge(stats,on=["season","week","player_display_name","team"],how="left")
pred["residual"]=pred.actual-pred.ridge
scale=pred.groupby("market").residual.std().to_dict()
pred["z"]=pred.apply(lambda r:r.residual/scale[r.market],axis=1)
pred["game"]=pred.apply(lambda r:f"{r.season}|{r.week}|{'-'.join(sorted([str(r.team),str(r.opponent_team)]))}",axis=1)

def relation(a,b):
    if a.player_display_name==b.player_display_name:return "same_player"
    if a.team==b.team:
        if (a.position=="QB" and b.market in ("receiving","receptions")) or (b.position=="QB" and a.market in ("receiving","receptions")):return "qb_receiver"
        return "same_team"
    if a.market==b.market=="passing":return "opposing_qb"
    return "opponents"

pairs=[]
for _,g in pred.groupby("game"):
    rows=list(g.itertuples(index=False))
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            ma,mb=sorted([a.market,b.market]);za,zb=(a.z,b.z) if a.market<=b.market else (b.z,a.z)
            pairs.append((a.season,relation(a,b),ma,mb,za,zb))
pairs=pd.DataFrame(pairs,columns=["season","relation","market_a","market_b","z_a","z_b"])
model={}
for key,g in pairs.groupby(["relation","market_a","market_b"]):
    n=len(g);raw=float(g.z_a.corr(g.z_b)) if n>2 else 0.0
    if not np.isfinite(raw):raw=0.0
    rho=float(np.clip(raw*(n/(n+150)),-.65,.80))
    model["|".join(key)]={"rho":round(rho,4),"raw":round(raw,4),"samples":n}
payload={"method":"walk-forward residual Pearson correlation with n/(n+150) shrinkage","minimum_samples":100,"markets":sorted(pred.market.unique()),"relationships":model}
(ROOT/"correlation_model.js").write_text("const SGP_CORRELATION_MODEL="+json.dumps(payload,separators=(",",":"))+";\n",encoding="utf-8")
pairs.to_csv(ROOT/"backtests"/"sgp_residual_pairs.csv",index=False)
summary=pd.DataFrame([{"relationship":k,"samples":v["samples"],"raw_rho":v["raw"],"shrunk_rho":v["rho"]} for k,v in model.items()]).sort_values("samples",ascending=False)
summary.to_csv(ROOT/"backtests"/"sgp_correlation_summary.csv",index=False)

# Hold out 2024-25 and test joint hit probabilities at several marginal levels.
tests=[]
for key,g in pairs.groupby(["relation","market_a","market_b"]):
    train=g[g.season<=2023]; test=g[g.season>=2024]
    if len(train)<100 or len(test)<50:continue
    raw=float(train.z_a.corr(train.z_b));raw=0 if not np.isfinite(raw) else raw
    rho=float(np.clip(raw*(len(train)/(len(train)+150)),-.65,.80))
    for marginal in (.55,.65,.75):
        ta=float(train.z_a.quantile(1-marginal));tb=float(train.z_b.quantile(1-marginal))
        pa=float((train.z_a>ta).mean());pb=float((train.z_b>tb).mean())
        actual=((test.z_a>ta)&(test.z_b>tb)).astype(float)
        joint=float(1-norm.cdf(norm.ppf(1-pa))-norm.cdf(norm.ppf(1-pb))+multivariate_normal.cdf([norm.ppf(1-pa),norm.ppf(1-pb)],mean=[0,0],cov=[[1,rho],[rho,1]]))
        independent=pa*pb
        tests.append({"relationship":"|".join(key),"target_marginal":marginal,"train_pairs":len(train),"test_pairs":len(test),"actual_rate":actual.mean(),"correlated_probability":joint,"independent_probability":independent,"correlated_brier":np.mean((actual-joint)**2),"independent_brier":np.mean((actual-independent)**2)})
validation=pd.DataFrame(tests)
validation.to_csv(ROOT/"backtests"/"sgp_joint_validation.csv",index=False)
print(summary.head(30).to_string(index=False))
if not validation.empty:
    print("\nHeld-out 2024-25 weighted Brier:",round(float(np.average(validation.correlated_brier,weights=validation.test_pairs)),5),"vs independence",round(float(np.average(validation.independent_brier,weights=validation.test_pairs)),5))
