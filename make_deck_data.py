"""Export the real numbers the slide deck uses (assets/deck_data.json)."""
import json
import numpy as np
import pandas as pd
from assay.backtest import Params, add_zscores

sp = pd.read_parquet("data/spreads.parquet")
summ = json.load(open("results/summary.json"))

pair = "GOLDTEN/GOLDPETAL"
z = add_zscores(sp[sp.pair == pair], Params())
ok = z[(z.dte >= 10) & (z.dte <= 90) & z.traded_a & (z.vol_b_g > 0)]
d = ok[ok.n_hist >= 150].groupby("date").agg(spread=("spread_bps", "mean"), mu=("mu", "first"), sd=("sd", "first")).dropna()
d["hi"], d["lo"] = d.mu + 3 * d.sd, d.mu - 3 * d.sd
out = dict(
    series=dict(labels=[x.strftime("%Y-%m-%d") for x in d.index], spread=d.spread.round(1).tolist(),
                hi=d.hi.round(1).tolist(), lo=d.lo.round(1).tolist()),
    diag={k: v["diagnostic"] for k, v in summ["pairs"].items()},
    fixed={k: v["fixed_params"] for k, v in summ["pairs"].items()},
    wf=summ["portfolio"]["1.0"], data=summ["data"],
)
json.dump(out, open("assets/deck_data.json", "w"))
print(len(d), d.index.min().date(), d.index.max().date(), d.spread.min(), d.spread.max())
