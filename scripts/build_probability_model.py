"""Export compact empirical residual distributions from walk-forward predictions."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
df=pd.read_csv(ROOT/"backtests"/"game_predictions.csv")
model={}
for market,g in df.groupby("market"):
    residual=(g.actual-g.ridge).dropna().to_numpy()
    model[market]={
        "quantiles":[round(float(x),3) for x in np.quantile(residual,np.linspace(0,1,201))],
        "samples":int(len(residual)),
        "source":"walk-forward residuals",
    }
(ROOT/"probability_model.js").write_text(
    "const PROBABILITY_MODEL="+json.dumps(model,separators=(",",":"))+";\n",
    encoding="utf-8",
)
print({k:v["samples"] for k,v in model.items()})
