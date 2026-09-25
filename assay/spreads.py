"""Cross-contract relative-value spreads on the normalized Rs/g @ 999 basis.

Pairs of contracts that share an expiry date are compared directly. GOLDM expires on
the 5th while GOLDTEN / GOLDGUINEA / GOLDPETAL expire at month-end, so GOLDM is compared
against the reference contract's curve linearly interpolated (in time) to GOLDM's expiry.
That removes the few days of carry that would otherwise masquerade as a spread.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PAIRS = [
    ("GOLDTEN", "GOLDPETAL"),
    ("GOLDGUINEA", "GOLDPETAL"),
    ("GOLDTEN", "GOLDGUINEA"),
    ("GOLDM", "GOLDPETAL"),
]


def _interp(curve: pd.DataFrame, target: pd.Timestamp) -> tuple[float, float, bool]:
    """Interpolate (px, volume_g) of `curve` (columns expiry, px_g, volume_g, traded) at `target`."""
    c = curve.sort_values("expiry")
    exact = c[c["expiry"] == target]
    if len(exact):
        r = exact.iloc[0]
        return r.px_g, r.volume_g, False
    lo = c[c["expiry"] < target].tail(1)
    hi = c[c["expiry"] > target].head(1)
    if lo.empty or hi.empty:
        return np.nan, np.nan, True
    lo, hi = lo.iloc[0], hi.iloc[0]
    w = (target - lo.expiry).days / (hi.expiry - lo.expiry).days
    return lo.px_g * (1 - w) + hi.px_g * w, min(lo.volume_g, hi.volume_g), True


def pair_spreads(df: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    A, B = df[df.symbol == a], df[df.symbol == b]
    if A.empty or B.empty:
        return pd.DataFrame()
    Bg = {d: g for d, g in B.groupby("date")}
    rows = []
    for d, ga in A.groupby("date"):
        gb = Bg.get(d)
        if gb is None:
            continue
        for r in ga.itertuples():
            pb, vb, interp = _interp(gb, r.expiry)
            if np.isnan(pb):
                continue
            rows.append((d, r.expiry, r.dte, r.px_g, pb, r.volume_g, vb, r.oi_g,
                         bool(r.traded), interp))
    out = pd.DataFrame(rows, columns=["date", "expiry", "dte", "px_a", "px_b", "vol_a_g", "vol_b_g",
                                      "oi_a_g", "traded_a", "interpolated"])
    out.insert(0, "pair", f"{a}/{b}")
    out["spread_bps"] = 1e4 * (out["px_a"] / out["px_b"] - 1.0)
    return out


def all_spreads(df: pd.DataFrame, pairs=PAIRS) -> pd.DataFrame:
    parts = [pair_spreads(df, a, b) for a, b in pairs]
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
