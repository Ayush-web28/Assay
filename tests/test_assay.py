import numpy as np
import pandas as pd
import pytest

from assay.backtest import CostModel, Params, add_zscores, paths_to_daily, simulate
from assay.ingest import parse_response
from assay.normalize import normalize


def _raw(rows):
    return pd.DataFrame(rows, columns=["date", "symbol", "expiry", "close", "prev_close", "volume", "oi"])


def test_normalization_matches_hand_calculation():
    raw = _raw([
        (pd.Timestamp("2026-09-24"), "GOLDM", pd.Timestamp("2026-10-05"), 150617.0, 151292.0, 37021, 32243),
        (pd.Timestamp("2026-09-24"), "GOLDPETAL", pd.Timestamp("2026-09-30"), 15126.0, 15200.0, 169541, 127054),
        (pd.Timestamp("2026-09-24"), "GOLDGUINEA", pd.Timestamp("2026-09-30"), 121094.0, 121720.0, 7073, 7692),
        (pd.Timestamp("2026-09-24"), "GOLDTEN", pd.Timestamp("2026-09-30"), 150973.0, 151684.0, 16226, 15921),
    ])
    n = normalize(raw).set_index("symbol")
    assert n.loc["GOLDM", "px_g"] == pytest.approx(150617 / 10 * 999 / 995)   # 995 -> 999 fineness
    assert n.loc["GOLDPETAL", "px_g"] == pytest.approx(15126)                 # quoted per 1 g
    assert n.loc["GOLDGUINEA", "px_g"] == pytest.approx(121094 / 8)           # quoted per 8 g
    assert n.loc["GOLDTEN", "px_g"] == pytest.approx(15097.3)                 # quoted per 10 g
    assert n.loc["GOLDM", "dte"] == 11
    assert n.loc["GOLDM", "volume_g"] == 37021 * 100                          # lots -> grams
    px = n["px_g"]
    assert px.max() / px.min() - 1 < 0.01     # all four contracts agree to within 1% after normalization


def _api_row(date_str, symbol="GOLDM  "):
    return dict(Date=date_str, Symbol=symbol, ExpiryDate="05OCT2026", Open=1, High=1, Low=1, Close=1,
                PreviousClose=1, Volume=1, OpenInterest=1, Value=1)


def test_parse_accepts_matching_date_in_mmddyyyy():
    from datetime import date
    df = parse_response([_api_row("09/24/2026"), _api_row("09/24/2026", "SILVER")], date(2026, 9, 24))
    assert len(df) == 1 and df.symbol.iloc[0] == "GOLDM"               # padding stripped, non-gold dropped
    assert df.expiry.iloc[0] == pd.Timestamp("2026-10-05")


def test_parse_rejects_fallback_day_for_wrong_request():
    from datetime import date
    # MCX serves the latest day when asked for a bad / holiday / future date: must be rejected
    assert parse_response([_api_row("09/24/2026")], date(2026, 12, 25)) is None
    # DD/MM vs MM/DD confusion: 03/09 requested (3 Sep) but 03/09 read as 9 Mar would not match
    assert parse_response([_api_row("03/09/2026")], date(2026, 9, 3)) is None


def _synthetic(n_days=400, seed=0, expiry_every=25):
    """Two contracts with a mean-reverting spread over rolling expiries."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n_days)
    rows = []
    base = 10000 + np.cumsum(rng.normal(0, 30, n_days))
    dev = np.zeros(n_days)
    for i in range(1, n_days):
        dev[i] = 0.8 * dev[i - 1] + rng.normal(0, 20)
    for k, expiry in enumerate(pd.date_range(dates[0] + pd.Timedelta(days=45), dates[-1] + pd.Timedelta(days=90), freq="30D")):
        for i, d in enumerate(dates):
            dte = (expiry - d).days
            if 0 <= dte <= 90:
                pb = base[i]
                pa = base[i] * (1 + (dev[i] + 50) / 1e4)
                rows.append((d, expiry, dte, pa, pb, 5e5, 5e5, 1e6, True, False))
    sp = pd.DataFrame(rows, columns=["date", "expiry", "dte", "px_a", "px_b", "vol_a_g", "vol_b_g",
                                     "oi_a_g", "traded_a", "interpolated"])
    sp.insert(0, "pair", "GOLDTEN/GOLDPETAL")
    sp["spread_bps"] = 1e4 * (sp.px_a / sp.px_b - 1)
    return sp


def test_zscore_uses_only_past_data():
    sp = _synthetic()
    cut = sp["date"].sort_values().unique()[300]
    full = add_zscores(sp, Params())
    trunc = add_zscores(sp[sp.date <= cut], Params())
    a = full[full.date <= cut].sort_values(["date", "expiry"])["z"].to_numpy()
    b = trunc.sort_values(["date", "expiry"])["z"].to_numpy()
    assert np.allclose(a, b, equal_nan=True)                             # future rows cannot change past z
    # today's own value must not leak into today's z: perturb one day's spread, z that day is unchanged
    d = full["date"].sort_values().unique()[200]
    pert = sp.copy()
    pert.loc[pert.date == d, "spread_bps"] += 1000
    z1 = full[full.date == d].sort_values("expiry")["z"].to_numpy()
    z2 = add_zscores(pert, Params())
    z2 = z2[z2.date == d].sort_values("expiry")["mu"].to_numpy()
    assert np.allclose(full[full.date == d].sort_values("expiry")["mu"].to_numpy(), z2, equal_nan=True)


def test_simulation_is_prefix_invariant():
    sp = _synthetic()
    p, c = Params(entry_z=1.5, min_obs=100), CostModel()
    full = simulate(sp, "GOLDTEN", "GOLDPETAL", p, c)
    cut = sp["date"].sort_values().unique()[320]
    part = simulate(sp[sp.date <= cut], "GOLDTEN", "GOLDPETAL", p, c)
    assert len(full) > 5
    f = full[full["exit"] < cut - pd.Timedelta(days=10)].reset_index(drop=True)
    q = part[part["exit"] < cut - pd.Timedelta(days=10)].reset_index(drop=True)
    assert len(f) == len(q) and np.allclose(f["net"], q["net"])          # decisions never see the future


def test_trades_enter_after_the_signal_day():
    sp = _synthetic()
    tr = simulate(sp, "GOLDTEN", "GOLDPETAL", Params(entry_z=1.5, min_obs=100), CostModel())
    z = add_zscores(sp, Params(entry_z=1.5, min_obs=100))
    for r in tr.head(20).itertuples():
        g = z[z.expiry == r.expiry].sort_values("date").reset_index(drop=True)
        i = g.index[g.date == r.entry][0]
        assert abs(g.loc[i - 1, "z"]) > 1.5                               # signal on the previous day


def test_costs_only_reduce_pnl_and_paths_reconcile():
    sp = _synthetic()
    p = Params(entry_z=1.5, min_obs=100)
    free = simulate(sp, "GOLDTEN", "GOLDPETAL", p, CostModel(scale=0.0))
    paid = simulate(sp, "GOLDTEN", "GOLDPETAL", p, CostModel(scale=1.0))
    assert free["cost"].sum() == 0 and paid["cost"].sum() > 0
    assert np.allclose(free["gross"], paid["gross"])                     # costs never change the trades
    idx = pd.Index(sorted(sp.date.unique()))
    d = paths_to_daily(paid, idx)
    assert d["net"].sum() == pytest.approx(paid["net"].sum())            # daily series == sum of trades
    assert d["cost"].sum() == pytest.approx(paid["cost"].sum())


def test_mean_reverting_spread_earns_gross_edge_on_synthetic_data():
    sp = _synthetic(n_days=600, seed=3)
    tr = simulate(sp, "GOLDTEN", "GOLDPETAL", Params(entry_z=1.5, min_obs=100), CostModel(scale=0.0))
    assert len(tr) > 10 and tr["gross"].sum() > 0                        # engine finds a planted edge
