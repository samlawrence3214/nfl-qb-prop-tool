"""Validate alternative-line probabilities with prior-season residuals only."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
pred=pd.read_csv(ROOT/"backtests"/"game_predictions.csv")
steps={"passing":25,"rushing":10,"receiving":10,"receptions":1}
def calibrate(p,market):
    if market in {"rushing","receiving"} and p>.6: p=.6+.72*(p-.6)
    if market=="receptions" and p>.8: p=.8+.82*(p-.8)
    return min(.995,max(.005,p))
rows=[]
for market,g in pred.groupby("market"):
    step=steps[market]
    for season in sorted(g.season.unique()):
        train=g[g.season<season]
        test=g[g.season==season]
        if train.empty: continue
        residual=np.sort((train.actual-train.ridge).dropna().to_numpy())
        for rec in test.itertuples():
            base=max(.5 if market=="receptions" else 0, int(rec.ridge//step)*step-.5)
            for line in (base-2*step,base-step,base):
                if line<0: continue
                threshold=line-rec.ridge
                p=calibrate(1-np.searchsorted(residual,threshold,side="right")/len(residual),market)
                rows.append({"market":market,"season":season,"probability":p,
                    "won":float(rec.actual>line)})
out=pd.DataFrame(rows)
out["band"]=pd.cut(out.probability,[0,.6,.7,.8,.9,1],include_lowest=True)
summary=(out.groupby(["market","band"],observed=True)
    .agg(samples=("won","size"),estimated=("probability","mean"),actual=("won","mean"))
    .reset_index())
summary["gap_pct"]=(summary.actual-summary.estimated)*100
summary.to_csv(ROOT/"backtests"/"probability_calibration.csv",index=False,float_format="%.4f")
print(summary.to_string(index=False))
