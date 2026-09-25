"""Walk-forward backtest of same-expiry cross-contract mean reversion.

No look-ahead: the z-score on day t uses only spreads observed on days < t; a signal on
day t is executed at the settlement of day t+1. Positions are tracked per
(pair, expiry) -- never on a continuous near-month series.

Costs are charged on the settlement prices of the two contracts actually held.
Settlement is NOT an executable price, so each fill pays a modelled half-spread, an
exchange/brokerage fee, and a participation-based impact term that gets large on thin days.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd

from .spreads import PAIRS

TRADABLE = [(a, b) for a, b in PAIRS if a != "GOLDM"]  # GOLDM leg needs interpolation -> monitor only

# Assumed one-way costs (bps of notional per leg). Placeholders to be stress-tested, not facts.
HALF_SPREAD_BPS = {"GOLDM": 0.5, "GOLDPETAL": 1.0, "GOLDTEN": 2.0, "GOLDGUINEA": 3.0}
FEE_BPS = 0.5               # exchange + brokerage + taxes, per leg per fill
IMPACT_BPS_AT_FULL = 10.0   # impact when our size equals 100% of day volume (linear), capped
IMPACT_CAP_BPS = 50.0


@dataclass(frozen=True)
class Params:
    entry_z: float = 2.0
    exit_z: float = 0.5
    window: int = 250        # trading days of past spreads used for mean / std
    max_hold: int = 15
    min_dte: int = 10        # no new entries this close to expiry
    exit_dte: int = 6        # be flat before the tender / expiry window
    min_obs: int = 150       # past observations required before trading


@dataclass(frozen=True)
class CostModel:
    scale: float = 1.0
    grams: float = 1000.0    # per leg

    def leg_bps(self, sym: str, vol_g: float) -> float:
        part = self.grams / vol_g if vol_g and vol_g > 0 else np.inf
        impact = min(IMPACT_CAP_BPS, IMPACT_BPS_AT_FULL * part)
        return self.scale * (HALF_SPREAD_BPS[sym] + FEE_BPS + impact)


def add_zscores(sp: pd.DataFrame, p: Params, dte_lo: int = 7, dte_hi: int = 120) -> pd.DataFrame:
    """Rolling pooled mean/std of the pair's spread using ONLY earlier dates."""
    sp = sp.sort_values(["date", "expiry"]).copy()
    ok = sp[(sp.dte >= dte_lo) & (sp.dte <= dte_hi) & sp.traded_a & (sp.vol_b_g > 0)]
    daily = ok.groupby("date")["spread_bps"].agg(
        n="count", s="sum", ss=lambda x: (x ** 2).sum())
    days = pd.Index(sorted(sp["date"].unique()))
    daily = daily.reindex(days).fillna(0.0)
    csum = daily.cumsum()
    lag = csum.shift(1).fillna(0.0)                       # everything strictly before day t
    old = csum.shift(p.window + 1).fillna(0.0)            # drop days that fell out of the window
    n, s, ss = (lag["n"] - old["n"]), (lag["s"] - old["s"]), (lag["ss"] - old["ss"])
    mu = s / n.where(n > 0)
    var = (ss / n.where(n > 0) - mu ** 2).clip(lower=0)
    st = pd.DataFrame({"n_hist": n, "mu": mu, "sd": np.sqrt(var)})
    sp = sp.join(st, on="date")
    valid = (sp["n_hist"] >= p.min_obs) & (sp["sd"] > 0)
    sp["z"] = np.where(valid, (sp["spread_bps"] - sp["mu"]) / sp["sd"], np.nan)
    return sp


def simulate(sp: pd.DataFrame, a: str, b: str, p: Params, cost: CostModel):
    """Returns a trades DataFrame; each trade carries its daily P&L path [(date, gross, cost), ...] in Rs."""
    sp = add_zscores(sp, p)
    trades = []
    for expiry, g in sp.groupby("expiry"):
        g = g.sort_values("date").reset_index(drop=True)
        n = len(g)
        date, pa, pb = g["date"].values, g["px_a"].values, g["px_b"].values
        z, dte = g["z"].values, g["dte"].values
        va, vb = g["vol_a_g"].values, g["vol_b_g"].values
        tradable = g["traded_a"].values & (vb > 0)
        pos, pending, e_i, hold, tr_cost, tr_gross, path = 0, None, -1, 0, 0.0, 0.0, []

        def fill_cost(i):
            return cost.grams * (pa[i] * cost.leg_bps(a, va[i]) + pb[i] * cost.leg_bps(b, vb[i])) / 1e4

        def close(i, d):
            nonlocal pos, hold, tr_cost, tr_gross, path
            c = fill_cost(i)
            path.append((d, 0.0, c))
            tr_cost += c
            trades.append(dict(pair=f"{a}/{b}", expiry=expiry, entry=pd.Timestamp(date[e_i]), exit=d,
                               direction=pos, hold=hold, gross=tr_gross, cost=tr_cost,
                               net=tr_gross - tr_cost, path=path))
            pos, hold, tr_cost, tr_gross, path = 0, 0, 0.0, 0.0, []

        for i in range(n):
            d = pd.Timestamp(date[i])
            if pos != 0 and i > 0:                       # mark the held position to today's settlement
                x = pos * cost.grams * ((pa[i] - pa[i - 1]) - (pb[i] - pb[i - 1]))
                path.append((d, x, 0.0))
                tr_gross += x
                hold += 1
            if pending is not None:                      # execute yesterday's signal at today's settlement
                act, direction = pending
                pending = None
                if act == "exit":
                    close(i, d)
                elif act == "enter" and tradable[i]:
                    c = fill_cost(i)
                    path = [(d, 0.0, c)]
                    pos, e_i, hold, tr_cost, tr_gross = direction, i, 0, c, 0.0
            last = i == n - 1
            if pos != 0:
                need_exit = ((np.isfinite(z[i]) and abs(z[i]) < p.exit_z)
                             or hold >= p.max_hold or dte[i] <= p.exit_dte + 1)
                if need_exit:
                    if last:                             # nothing after today: close at today's settlement
                        close(i, d)
                    else:
                        pending = ("exit", 0)
            elif (not last and np.isfinite(z[i]) and abs(z[i]) > p.entry_z
                  and dte[i] >= p.min_dte and tradable[i]):
                pending = ("enter", -int(np.sign(z[i])))  # z>0: A rich -> short A, long B
    return pd.DataFrame(trades)


def paths_to_daily(trades: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
    """Sum the daily P&L paths of a set of trades onto the trading calendar."""
    rows = [r for path in trades["path"] for r in path] if len(trades) else []
    if rows:
        df = pd.DataFrame(rows, columns=["date", "gross", "cost"]).groupby("date").sum()
    else:
        df = pd.DataFrame(columns=["gross", "cost"], dtype=float)
    df = df.reindex(index).fillna(0.0)
    df["net"] = df["gross"] - df["cost"]
    return df


def metrics(d: pd.DataFrame, trades: pd.DataFrame | None = None) -> dict:
    net = d["net"]
    sd = net.std()
    out = dict(gross=d["gross"].sum(), cost=d["cost"].sum(), net=net.sum(),
               sharpe=(net.mean() / sd * np.sqrt(252)) if sd and sd > 0 else np.nan,
               max_dd=(net.cumsum() - net.cumsum().cummax()).min() if len(net) else 0.0)
    if trades is not None and len(trades):
        out.update(trades=len(trades), hit=(trades["net"] > 0).mean(), avg_hold=trades["hold"].mean(),
                   net_per_trade=trades["net"].mean())
    else:
        out.update(trades=0, hit=np.nan, avg_hold=np.nan, net_per_trade=np.nan)
    return out


GRID = [Params(entry_z=e, exit_z=x, window=w)
        for e, x, w in product([1.5, 2.0, 2.5, 3.0], [0.0, 0.5], [120, 250])]


def run_grid(spreads: pd.DataFrame, a: str, b: str, cost: CostModel, grid=GRID):
    sp = spreads[spreads.pair == f"{a}/{b}"]
    return {p: simulate(sp, a, b, p, cost) for p in grid}


def walk_forward(res: dict, index: pd.Index, first_test: pd.Timestamp, min_trades: int = 5):
    """Quarterly walk-forward. Before each test quarter pick the parameter set with the best
    NET P&L over trades already CLOSED before the quarter starts (needs >= min_trades and
    net > 0); otherwise stay flat. The quarter then trades that parameter set's entries.
    Returns (taken trades, daily P&L on `index`, per-quarter choices)."""
    taken, chosen = [], []
    for q in pd.period_range(first_test, index.max(), freq="Q"):
        lo, hi = q.start_time, q.end_time
        best, best_v = None, 0.0
        for p, tr in res.items():
            if not len(tr):
                continue
            closed = tr[tr["exit"] < lo]
            v = closed["net"].sum()
            if len(closed) >= min_trades and v > best_v:
                best, best_v = p, v
        chosen.append((str(q), best, best_v))
        if best is not None and len(res[best]):
            t = res[best]
            taken.append(t[(t["entry"] >= lo) & (t["entry"] <= hi)])
    taken = pd.concat(taken, ignore_index=True) if taken else pd.DataFrame(columns=["net", "hold", "path", "exit"])
    return taken, paths_to_daily(taken, index), chosen


def gold_attribution(pnl: pd.Series, gold_move: pd.Series, grams: float) -> dict:
    """OLS of daily net P&L on the daily gold price move (Rs/g * grams)."""
    x = (gold_move.reindex(pnl.index) * grams).astype(float)
    ok = x.notna() & pnl.notna()
    x, y = x[ok], pnl[ok]
    if len(x) < 10 or x.std() == 0:
        return dict(alpha_per_day=np.nan, beta=np.nan, t_beta=np.nan, r2=np.nan)
    X = np.column_stack([np.ones(len(x)), x.values])
    coef, *_ = np.linalg.lstsq(X, y.values, rcond=None)
    resid = y.values - X @ coef
    s2 = resid @ resid / (len(y) - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    ss_tot = ((y - y.mean()) ** 2).sum()
    return dict(alpha_per_day=coef[0], beta=coef[1], t_beta=coef[1] / np.sqrt(cov[1, 1]),
                r2=1 - (resid @ resid) / ss_tot if ss_tot > 0 else np.nan)
