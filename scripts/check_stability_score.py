"""Check whether the proposed 0–10 display score predicts lower model error."""
from pathlib import Path
import numpy as np
import pandas as pd
import nflreadpy as nfl

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"backtests"
old=pd.read_csv(ROOT.parent/"nfl_prop_consistency/data/player_stats.csv",low_memory=False).rename(columns={"recent_team":"team"})
tmp=OUT/"_2025_stability.csv"; nfl.load_player_stats([2025]).write_csv(tmp); new=pd.read_csv(tmp,low_memory=False); tmp.unlink()
cols=["player_id","player_display_name","position","team","season","week","season_type","passing_yards","attempts","rushing_yards","carries","receiving_yards","receptions","targets"]
s=pd.concat([old[cols],new[cols]],ignore_index=True).query("season_type == 'REG'").sort_values(["player_id","season","week"])
pred=pd.read_csv(OUT/"game_predictions.csv")
cfg={"passing":("passing_yards","attempts"),"rushing":("rushing_yards","carries"),"receiving":("receiving_yards","targets"),"receptions":("receptions","targets")}
rows=[]
for market,(target,usage) in cfg.items():
    d=s.copy(); g=d.groupby("player_id",sort=False)
    for c in [target,usage]:
        prior=g[c].shift(1)
        d[c+"_mean5"]=prior.groupby(d.player_id).transform(lambda x:x.rolling(5,min_periods=2).mean())
        d[c+"_sd5"]=prior.groupby(d.player_id).transform(lambda x:x.rolling(5,min_periods=3).std())
    cv=d[usage+"_sd5"]/(d[usage+"_mean5"].abs()+1)
    vv=d[target+"_sd5"]/(d[target+"_mean5"].abs()+1)
    d["score"]=np.clip(np.rint(10-5*((cv/.28+vv/.55)/2)),0,10)
    p=pred[pred.market==market].merge(d[["season","week","player_display_name","team","score"]],on=["season","week","player_display_name","team"],how="left")
    p["abs_error"]=(p.actual-p.ridge).abs(); p["relative_error"]=p.abs_error/(p.ridge.abs()+1); p["market"]=market; rows.append(p)
r=pd.concat(rows); r["band"]=pd.cut(r.score,[-.1,3,5,7,10],labels=["0–3","4–5","6–7","8–10"])
summary=(r.dropna(subset=["band"]).groupby(["market","band"],observed=True).agg(games=("abs_error","size"),mae=("abs_error","mean"),p75_error=("abs_error",lambda x:x.quantile(.75)),mean_relative_error=("relative_error","mean")).reset_index())
summary.round(3).to_csv(OUT/"stability_score_check.csv",index=False)
print(summary.round(2).to_string(index=False))
