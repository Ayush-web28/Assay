"""Normalize every contract to a common basis: rupees per gram of 999 gold."""
from __future__ import annotations

import pandas as pd

from .config import REF_PURITY, SPECS


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[raw["symbol"].isin(SPECS)].copy()
    spec = pd.DataFrame(SPECS).T
    df = df.join(spec, on="symbol")
    df["px_g"] = df["close"] / df["quote_g"] * REF_PURITY / df["purity"]   # settlement, Rs/g @ 999
    df["prev_px_g"] = df["prev_close"] / df["quote_g"] * REF_PURITY / df["purity"]
    df["lot_value"] = df["close"] / df["quote_g"] * df["unit_g"]           # Rs per lot
    df["dte"] = (df["expiry"] - df["date"]).dt.days
    df["traded"] = df["volume"] > 0
    df["volume_g"] = df["volume"] * df["unit_g"]                          # grams traded
    df["oi_g"] = df["oi"] * df["unit_g"]
    return df.drop(columns=["unit_g", "quote_g", "purity"]).reset_index(drop=True)
