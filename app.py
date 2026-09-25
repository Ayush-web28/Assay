"""Assay dashboard.  Run:  streamlit run app.py"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from assay.backtest import CostModel, Params, add_zscores
from assay.config import ROOT, SPECS
from assay.ingest import load_raw
from assay.normalize import normalize
from assay.spreads import PAIRS

GOLD, GOLD_DK, INK, SLATE, WARN, TINT = "#C98A1B", "#8A5A0B", "#1D1D1F", "#5B6573", "#B5482F", "#FBF6EC"
SYM_COLOR = {"GOLDM": INK, "GOLDTEN": GOLD, "GOLDGUINEA": WARN, "GOLDPETAL": SLATE}
TRADABLE = [f"{a}/{b}" for a, b in PAIRS if a != "GOLDM"]

st.set_page_config(page_title="Assay", page_icon="💎", layout="wide")
st.markdown(f"""<style>
h1,h2,h3 {{ letter-spacing:-0.01em; }}
div[data-testid="stMetric"] {{ background:{TINT}; border:1px solid #F0E2C4; border-radius:12px; padding:14px 16px; }}
.verdict {{ background:{INK}; color:#fff; border-radius:14px; padding:18px 22px; font-size:1.05rem; }}
.verdict b {{ color:{GOLD}; }}
.quiet {{ background:{TINT}; border:1px dashed {GOLD}; border-radius:14px; padding:18px 22px; }}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading Bhavcopy data...")
def load():
    df = normalize(load_raw())
    sp = pd.read_parquet(ROOT / "data" / "spreads.parquet")
    summ = json.loads((ROOT / "results" / "summary.json").read_text())
    pf = pd.read_csv(ROOT / "results" / "portfolio_net.csv", index_col=0, parse_dates=True)
    return df, sp, summ, pf


try:
    df, sp, summ, pf = load()
except FileNotFoundError:
    st.error("No data yet. Run `python -m assay.ingest` then `python -m assay.run`.")
    st.stop()

last = df["date"].max()
fmt_rs = lambda x: f"-₹{abs(x):,.0f}" if x < 0 else f"₹{x:,.0f}"


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(color=INK), legend=dict(orientation="h", y=1.08, x=0))
    fig.update_xaxes(showgrid=False, linecolor="#DDD")
    fig.update_yaxes(gridcolor="#EEE", zerolinecolor="#CCC")
    return fig


# ---------------------------------------------------------------- sidebar
st.sidebar.markdown("## 💎 Assay")
st.sidebar.caption("Is the gold spread real, or just noise?")
st.sidebar.markdown(f"**Data:** {summ['data']['first']} → {summ['data']['last']}  \n"
                    f"**Days:** {summ['data']['days']}  ·  **Contracts:** {summ['data']['contracts']}")
entry_z = st.sidebar.slider("Alert threshold |z|", 1.5, 4.0, 3.0, 0.5,
                            help="Alerts also need expected reversion to exceed round-trip cost.")
cost_scale = st.sidebar.select_slider("Cost multiplier", [0.5, 1.0, 1.5, 2.0], value=1.0)

tab_over, tab_alerts, tab_spread, tab_curve, tab_cal, tab_bt = st.tabs(
    ["Overview", "Alerts", "Spreads", "Term structure", "Contract calendar", "Backtest"])

# ---------------------------------------------------------------- overview
with tab_over:
    st.title("Assay")
    st.markdown("""<div class="verdict">MCX lists gold in four contract sizes. Once normalized to <b>₹ per gram at 999
    purity</b> they should track each other. Assay measures the gaps, tests whether they can be traded after
    costs, and <b>says so when they cannot</b>.</div>""", unsafe_allow_html=True)
    st.write("")
    p1 = summ["portfolio"]["1.0"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Walk-forward net P&L (1x costs)", fmt_rs(p1["net"]))
    c2.metric("Gross before costs", fmt_rs(p1["gross"]))
    c3.metric("Costs paid", fmt_rs(p1["cost"]))
    c4.metric("Beta to gold", f"{p1['gold_beta']:.3f}", help="Slope of daily P&L on the daily gold move (per 1,000 g). Equal-gram legs aim for ~0; crash days push it away.")
    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Latest normalized prices (₹/g @ 999)")
        latest = df[df.date == last]
        fig = go.Figure()
        for s in SPECS:
            x = latest[latest.symbol == s].sort_values("expiry")
            fig.add_trace(go.Scatter(x=x["expiry"], y=x["px_g"], mode="lines+markers", name=s,
                                     line=dict(color=SYM_COLOR[s], width=2.5)))
        st.plotly_chart(style(fig, 340), use_container_width=True)
    with right:
        st.subheader("Verdict")
        fx = {k: v["fixed_params"] for k, v in summ["pairs"].items()}
        rows = [dict(Pair=k, Trades=v.get("trades"), **{"Break-even cost": f"{v.get('breakeven_cost_scale')}x"})
                for k, v in fx.items()]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Break-even cost = multiple of the assumed costs at which the strategy earns zero. "
                   "Below 1x means the edge does not survive costs.")
        st.info("No persistent edge survives costs in this sample. A rigorous null result is a valid outcome.")

# ---------------------------------------------------------------- alerts
with tab_alerts:
    st.subheader(f"Signals as of {last.date()}")
    cost = CostModel(scale=cost_scale)
    fired, watch = [], []
    for name in TRADABLE:
        rows = sp[sp.pair == name]
        z = add_zscores(rows, Params())
        z = z[(z.date == last) & np.isfinite(z["z"]) & (z.dte >= 10) & z.traded_a & (z.vol_b_g > 0)]
        diag = {d["z_bucket"]: d for d in summ["pairs"][name]["diagnostic"]}
        a, b = name.split("/")
        for r in z.itertuples():
            rt = 2 * (cost.leg_bps(a, r.vol_a_g) + cost.leg_bps(b, r.vol_b_g))
            bucket = "3.0-inf" if abs(r.z) >= 3 else "2.0-3.0" if abs(r.z) >= 2 else "1.5-2.0"
            exp = diag.get(bucket, {}).get("mean_reversion_bps", 0.0)
            row = dict(Pair=name, Expiry=r.expiry.date(), DTE=r.dte, Spread_bps=round(r.spread_bps, 1),
                       z=round(r.z, 2), Expected_reversion_bps=exp, Round_trip_cost_bps=round(rt, 1),
                       Net_bps=round(exp - rt, 1),
                       Direction=("short " + a + " / long " + b) if r.z > 0 else ("long " + a + " / short " + b))
            (fired if abs(r.z) >= entry_z and exp > rt else watch).append(row)
    if fired:
        st.success(f"{len(fired)} signal(s) clear both the z threshold and the cost hurdle.")
        st.dataframe(pd.DataFrame(fired), hide_index=True, use_container_width=True)
    else:
        st.markdown(f"""<div class="quiet"><b>No meaningful signal.</b><br>Nothing today combines |z| ≥ {entry_z}
        with expected reversion above round-trip cost. Staying quiet is the point.</div>""", unsafe_allow_html=True)
    if watch:
        st.write("")
        st.markdown("**Closest to firing** (does not clear the bar)")
        w = pd.DataFrame(watch)
        w["abs_z"] = w["z"].abs()
        st.dataframe(w.sort_values("abs_z", ascending=False).drop(columns="abs_z").head(8),
                     hide_index=True, use_container_width=True)
    st.caption("Expected reversion comes from the 5-day post-signal study, measured from the next settlement, "
               "the earliest tradable price. Costs are modelled assumptions.")

# ---------------------------------------------------------------- spreads
with tab_spread:
    pair = st.selectbox("Pair", [f"{a}/{b}" for a, b in PAIRS])
    rows = sp[sp.pair == pair]
    dte_min, dte_max = st.slider("Days to expiry", 0, 120, (10, 90))
    r = rows[(rows.dte >= dte_min) & (rows.dte <= dte_max) & rows.traded_a]
    if pair.startswith("GOLDM"):
        st.caption("GOLDM expires on the 5th, the others at month-end, so the reference contract is interpolated "
                   "to GOLDM's expiry. This pair is monitor-only, not traded.")
    daily = r.groupby("date")["spread_bps"].agg(["mean", "min", "max"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily.index, y=daily["max"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=daily.index, y=daily["min"], fill="tonexty", fillcolor="rgba(201,138,27,0.15)",
                             line=dict(width=0), name="range across expiries", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=daily.index, y=daily["mean"], name="mean spread", line=dict(color=GOLD, width=2.5)))
    fig.add_hline(y=float(daily["mean"].mean()), line_dash="dash", line_color=SLATE,
                  annotation_text="long-run level", annotation_position="bottom right")
    fig.update_yaxes(title="spread (bps)")
    st.plotly_chart(style(fig, 400), use_container_width=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Mean", f"{r.spread_bps.mean():.0f} bps")
    m2.metric("Std dev", f"{r.spread_bps.std():.0f} bps")
    m3.metric("Latest (mean)", f"{daily['mean'].iloc[-1]:.0f} bps")
    st.caption("A persistent gap is structural (lot size, retail demand, purity premium), not an arbitrage. "
               "Only deviations from the running level carry signal.")

# ---------------------------------------------------------------- term structure
with tab_curve:
    c1, c2 = st.columns([1, 1])
    sym = c1.selectbox("Contract", list(SPECS), index=3)
    dates = sorted(df[df.symbol == sym]["date"].unique())
    dates = [pd.Timestamp(d) for d in dates]
    when = c2.select_slider("Date", options=dates, value=dates[-1], format_func=lambda d: str(d.date()))
    lag = st.slider("Compare with N trading days earlier", 5, 60, 20)
    before = dates[max(0, dates.index(when) - lag)]
    fig = go.Figure()
    for d, name, col, dash in [(before, f"{before.date()}", SLATE, "dot"), (when, f"{when.date()}", GOLD, "solid")]:
        c = df[(df.symbol == sym) & (df.date == d) & (df.dte > 0)].sort_values("dte")
        fig.add_trace(go.Scatter(x=c["dte"], y=c["px_g"], mode="lines+markers", name=name,
                                 line=dict(color=col, width=2.5, dash=dash)))
    fig.update_xaxes(title="days to expiry")
    fig.update_yaxes(title="₹/g @ 999")
    st.plotly_chart(style(fig, 380), use_container_width=True)

    c = df[(df.symbol == sym) & (df.date == when) & (df.dte > 0)].sort_values("expiry").reset_index(drop=True)
    if len(c) >= 2:
        c["carry_pct_ann"] = (c["px_g"].shift(-1) / c["px_g"] - 1) * 365 / (c["expiry"].shift(-1) - c["expiry"]).dt.days * 100
        c["roll_down_g_30d"] = c["px_g"] - c["px_g"].shift(1)   # price step to the next-nearer expiry
        show = c[["expiry", "dte", "px_g", "carry_pct_ann", "volume_g", "oi_g"]].copy()
        show["expiry"] = show["expiry"].dt.date
        show.columns = ["Expiry", "DTE", "₹/g", "Carry to next (% ann.)", "Volume (g)", "OI (g)"]
        st.dataframe(show.round(2), hide_index=True, use_container_width=True)
        st.caption("Roll-down is mechanical: with an unchanged curve, a contract slides down toward spot as expiry "
                   "nears. Compare the two curves above by days-to-expiry to see what is genuine shape change "
                   "versus time passing.")

# ---------------------------------------------------------------- calendar
with tab_cal:
    st.subheader("Contract lifecycle")
    g = df.groupby(["symbol", "expiry"]).agg(first=("date", "min"), last=("date", "max"), peak=("volume_g", "max")).reset_index()
    liq = df.merge(g[["symbol", "expiry", "peak"]], on=["symbol", "expiry"])
    liq = liq[liq.volume_g >= 0.1 * liq.peak].groupby(["symbol", "expiry"])["date"].min().rename("liquid_from")
    g = g.join(liq, on=["symbol", "expiry"])
    win = g[(g.expiry >= last - pd.Timedelta(days=30)) & (g.expiry <= last + pd.Timedelta(days=200))].sort_values("expiry")
    syms = st.multiselect("Contracts", list(SPECS), default=["GOLDTEN", "GOLDGUINEA", "GOLDPETAL"])
    win = win[win.symbol.isin(syms)]
    fig = go.Figure()
    for i, r in enumerate(win.itertuples()):
        y = f"{r.symbol} {r.expiry:%b %y}"
        fig.add_trace(go.Scatter(x=[r.first, r.liquid_from, r.expiry - pd.Timedelta(days=6), r.expiry],
                                 y=[y] * 4, mode="lines", showlegend=False, hoverinfo="skip",
                                 line=dict(color="#DDD", width=10)))
        fig.add_trace(go.Scatter(x=[r.liquid_from, r.expiry - pd.Timedelta(days=6)], y=[y] * 2, mode="lines",
                                 showlegend=False, line=dict(color=SYM_COLOR[r.symbol], width=10),
                                 hovertemplate=f"{y}<br>liquid → exit guard<extra></extra>"))
        fig.add_trace(go.Scatter(x=[r.expiry - pd.Timedelta(days=6), r.expiry], y=[y] * 2, mode="lines",
                                 showlegend=False, line=dict(color=WARN, width=10),
                                 hovertemplate=f"{y}<br>tender / expiry window<extra></extra>"))
    fig.add_vline(x=last, line_dash="dash", line_color=INK, annotation_text="today")
    st.plotly_chart(style(fig, max(320, 26 * len(win) + 80)), use_container_width=True)
    st.caption("Grey: listed but thin. Coloured: liquid (≥10% of the contract's peak volume) until the exit guard. "
               "Red: last 6 days, where the strategy is always flat. Entries and exits are placed only in the coloured span.")
    exp = win.assign(first=win["first"].dt.date, liquid_from=win["liquid_from"].dt.date, expiry=win["expiry"].dt.date)
    st.dataframe(exp[["symbol", "expiry", "first", "liquid_from"]].rename(
        columns={"first": "first seen", "liquid_from": "liquid from"}), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- backtest
with tab_bt:
    st.subheader("Walk-forward results")
    cum = pf[["gross", "net"]].cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum.index, y=cum["gross"], name="gross", line=dict(color=SLATE, width=2, dash="dot")))
    fig.add_trace(go.Scatter(x=cum.index, y=cum["net"], name="net of costs", line=dict(color=GOLD, width=3)))
    fig.update_yaxes(title="cumulative ₹ (1,000 g per leg)")
    st.plotly_chart(style(fig, 360), use_container_width=True)
    st.caption("Parameters for each quarter are chosen using only trades that had already closed, then applied "
               "out of sample. Quarters without a profitable history stay flat.")

    st.subheader("Cost sensitivity, fixed default parameters (no selection)")
    rows = []
    for k, v in summ["pairs"].items():
        f = v["fixed_params"]
        if f.get("trades"):
            rows.append({"Pair": k, "Trades": f["trades"], "Gross ₹": f["gross"], "Cost @1x ₹": f["cost_at_1x"],
                         **{f"Net @{s}x": n for s, n in f["net_at"].items()}, "Break-even": f["breakeven_cost_scale"]})
    tbl = pd.DataFrame(rows)
    money = [c for c in tbl.columns if c not in ("Pair", "Trades", "Break-even")]
    tbl[money] = tbl[money].round(0)
    tbl["Break-even"] = tbl["Break-even"].round(2)
    st.dataframe(tbl, hide_index=True, use_container_width=True)

    st.subheader("Does a deviation revert, and is it worth the cost?")
    pair = st.selectbox("Pair", TRADABLE, key="bt_pair")
    d = pd.DataFrame(summ["pairs"][pair]["diagnostic"])
    fig = go.Figure()
    fig.add_bar(x=d["z_bucket"], y=d["mean_reversion_bps"], name="mean reversion (bps)", marker_color=GOLD)
    fig.add_bar(x=d["z_bucket"], y=d["roundtrip_cost_bps"], name="round-trip cost (bps)", marker_color=SLATE)
    fig.update_layout(barmode="group")
    st.plotly_chart(style(fig, 320), use_container_width=True)
    st.dataframe(d, hide_index=True, use_container_width=True)
    st.caption("Measured from the next settlement over 5 trading days. t-stats are clustered by date. "
               "Large-deviation cases for the GOLDTEN pairs sit mostly in January 2026, so they are largely one episode.")

    with st.expander("Trades"):
        pick = st.selectbox("Pair", [k.replace("/", "_") for k in TRADABLE], key="tr_pair")
        f = ROOT / "results" / f"trades_{pick}.csv"
        st.dataframe(pd.read_csv(f) if f.exists() else pd.DataFrame({"note": ["No walk-forward trades for this pair."]}),
                     hide_index=True, use_container_width=True)
