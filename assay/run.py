"""End-to-end: raw Bhavcopy -> normalized -> spreads -> diagnostics + walk-forward backtest -> results/."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .backtest import (TRADABLE, CostModel, Params, add_zscores, gold_attribution, metrics,
                       paths_to_daily, run_grid, simulate, walk_forward)
from .config import ROOT
from .ingest import load_raw
from .normalize import normalize
from .spreads import all_spreads

OUT = ROOT / "results"
COST_SCALES = [0.0, 0.5, 1.0, 2.0]
WARMUP_MONTHS = 9


def gold_move(df: pd.DataFrame) -> pd.Series:
    """Daily gold price move in Rs/g: mean change in settlement across all live contracts."""
    return (df["px_g"] - df["prev_px_g"]).groupby(df["date"]).mean()


def signal_diagnostic(sp: pd.DataFrame, a: str, b: str, cost: CostModel, horizon: int = 5) -> list[dict]:
    """Model-free check of the *tradable* edge. After |z| is large on day t, we can only trade
    at the settlement of day t+1, so reversion is measured from t+1 to t+1+horizon.
    z uses only past data (see add_zscores). t-stats are clustered by date because
    overlapping windows and same-day expiries are not independent observations."""
    z = add_zscores(sp[sp.pair == f"{a}/{b}"], Params()).sort_values(["expiry", "date"])
    g = z.groupby("expiry")["spread_bps"]
    z["fwd"] = g.shift(-(1 + horizon)) - g.shift(-1)
    z = z[np.isfinite(z["z"]) & z["fwd"].notna() & (z["dte"] >= 10) & z["traded_a"] & (z["vol_b_g"] > 0)].copy()
    z["edge"] = -np.sign(z["z"]) * z["fwd"]                       # >0 means the spread reverted
    z["rt_cost"] = 2 * (z.apply(lambda r: cost.leg_bps(a, r.vol_a_g) + cost.leg_bps(b, r.vol_b_g), axis=1))
    out = []
    for lo, hi in [(1.5, 2.0), (2.0, 3.0), (3.0, 99.0)]:
        m = (z["z"].abs() >= lo) & (z["z"].abs() < hi)
        if m.sum() < 5:
            continue
        per_day = z.loc[m].groupby("date")["edge"].mean()
        t = per_day.mean() / (per_day.std() / np.sqrt(len(per_day))) if len(per_day) > 2 else np.nan
        out.append(dict(z_bucket=f"{lo}-{hi if hi < 99 else 'inf'}", n=int(m.sum()), days=int(len(per_day)),
                        mean_reversion_bps=round(z.loc[m, "edge"].mean(), 1), t_by_date=round(t, 2),
                        median_bps=round(z.loc[m, "edge"].median(), 1),
                        roundtrip_cost_bps=round(z.loc[m, "rt_cost"].mean(), 1),
                        net_after_cost_bps=round(z.loc[m, "edge"].mean() - z.loc[m, "rt_cost"].mean(), 1)))
    return out


def fixed_param_sensitivity(sp: pd.DataFrame, a: str, b: str, first_test: pd.Timestamp) -> dict:
    """Default parameters, no selection: how much edge is there before costs and how much cost
    can it bear? Cost scales linearly with CostModel.scale, so one run covers every scale."""
    tr = simulate(sp[sp.pair == f"{a}/{b}"], a, b, Params(), CostModel(scale=1.0))
    tr = tr[tr["entry"] >= first_test] if len(tr) else tr
    if not len(tr):
        return dict(trades=0)
    g, c = tr["gross"].sum(), tr["cost"].sum()
    return dict(trades=len(tr), hit_gross=_r((tr["gross"] > 0).mean()), gross=_r(g), cost_at_1x=_r(c),
                net_at={str(s): _r(g - s * c) for s in COST_SCALES}, breakeven_cost_scale=_r(g / c) if c > 0 else None)


def _r(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 4)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df = normalize(load_raw())
    sp = all_spreads(df)
    sp.to_parquet(ROOT / "data" / "spreads.parquet", index=False)
    index = pd.Index(sorted(df["date"].unique()))
    gm = gold_move(df)

    summary = dict(data=dict(first=str(index.min().date()), last=str(index.max().date()), days=len(index),
                             contracts=int(df.groupby(["symbol", "expiry"]).ngroups)),
                   assumptions=dict(grams_per_leg=CostModel().grams, warmup_months=WARMUP_MONTHS), pairs={})
    all_taken = {s: [] for s in COST_SCALES}
    first_by_pair = {}

    for a, b in TRADABLE:
        name = f"{a}/{b}"
        rows = sp[sp.pair == name]
        if rows.empty:
            continue
        ok = rows[(rows.dte >= 7) & rows.traded_a]["spread_bps"]
        first_test = rows.date.min() + pd.DateOffset(months=WARMUP_MONTHS)
        first_by_pair[name] = first_test
        entry = dict(obs=len(rows), spread_mean_bps=_r(ok.mean()), spread_sd_bps=_r(ok.std()),
                     first=str(rows.date.min().date()), first_test=str(first_test.date()),
                     diagnostic=signal_diagnostic(sp, a, b, CostModel()),
                     fixed_params=fixed_param_sensitivity(sp, a, b, first_test), scenarios={})
        for scale in COST_SCALES:
            cost = CostModel(scale=scale)
            res = run_grid(sp, a, b, cost)
            taken, daily, chosen = walk_forward(res, index, first_test)
            active = daily[daily.index >= first_test]
            m = metrics(active, taken)
            att = gold_attribution(active["net"], gm, cost.grams)
            entry["scenarios"][str(scale)] = {**{k: _r(v) for k, v in m.items()},
                                              "gold_beta": _r(att["beta"]), "gold_t": _r(att["t_beta"]),
                                              "gold_r2": _r(att["r2"]),
                                              "quarters_traded": sum(1 for _, p, _ in chosen if p is not None),
                                              "quarters": len(chosen)}
            all_taken[scale].append(taken)
            if scale == 1.0:
                active.to_csv(OUT / f"walkforward_{a}_{b}.csv")
                if len(taken):
                    taken.drop(columns=["path"]).to_csv(OUT / f"trades_{a}_{b}.csv", index=False)
                pd.DataFrame([(q, str(p), v) for q, p, v in chosen],
                             columns=["quarter", "params", "insample_net_rs"]).to_csv(OUT / f"params_{a}_{b}.csv", index=False)
        summary["pairs"][name] = entry

    start = min(first_by_pair.values())
    summary["portfolio"] = {"from": str(start.date())}
    for scale in COST_SCALES:
        taken = pd.concat([t for t in all_taken[scale] if len(t)], ignore_index=True) if any(len(t) for t in all_taken[scale]) else pd.DataFrame()
        daily = paths_to_daily(taken, index)
        active = daily[daily.index >= start]
        att = gold_attribution(active["net"], gm, 1000.0)
        m = metrics(active, taken)
        summary["portfolio"][str(scale)] = {**{k: _r(v) for k, v in m.items()},
                                            "gold_beta": _r(att["beta"]), "gold_t": _r(att["t_beta"])}
        if scale == 1.0:
            active.to_csv(OUT / "portfolio_net.csv")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
    print((OUT / "summary.json").read_text())
