"""MCX Bhavcopy ingest with the date-validation traps from the problem statement.

- Requests use DD/MM/YYYY; responses carry Date as MM/DD/YYYY.
- MCX returns the latest trading day for malformed / future dates, so the returned
  Date is always checked against the requested date and mismatches are discarded.
- Holidays / weekends return no data.
- www.mcxindia.com sits behind bot protection that rejects plain `requests`;
  curl_cffi (Chrome TLS impersonation) is required.
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta

import pandas as pd
from curl_cffi import requests as cr

from .config import BASE, ENDPOINT, FETCH_LOG, RAW_DIR, SYMBOLS

HEADERS = {"Referer": BASE, "Accept": "application/json"}
KEEP = ["Date", "Symbol", "ExpiryDate", "Open", "High", "Low", "Close",
        "PreviousClose", "Volume", "OpenInterest", "Value"]


def _session() -> cr.Session:
    s = cr.Session(impersonate="chrome")
    s.get(BASE, timeout=30)  # pick up cookies
    return s


def parse_response(rows: list[dict], requested: date) -> pd.DataFrame | None:
    """Filter to gold futures and validate the returned date. None if the day is unusable."""
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["Symbol"] = df["Symbol"].str.strip()
    df = df[df["Symbol"].isin(SYMBOLS)]
    if df.empty:
        return None
    got = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.date
    if (got != requested).any():
        return None  # fallback day served for a bad / holiday / future request
    out = df[KEEP].rename(columns=str.lower).rename(
        columns={"expirydate": "expiry", "previousclose": "prev_close", "openinterest": "oi"})
    out["date"] = pd.to_datetime(out["date"], format="%m/%d/%Y")
    out["expiry"] = pd.to_datetime(out["expiry"].str.strip(), format="%d%b%Y")
    return out.reset_index(drop=True)


def fetch_day(s: cr.Session, d: date) -> tuple[str, pd.DataFrame | None]:
    r = s.get(ENDPOINT, params={"InstrumentName": "FUTCOM", "fromDate": d.strftime("%d/%m/%Y")},
              headers=HEADERS, timeout=60)
    r.raise_for_status()
    rows = r.json().get("Data") or []
    if not rows:
        return "no_data", None
    df = parse_response(rows, d)
    return ("ok", df) if df is not None else ("mismatch", None)


def _done() -> set[str]:
    if not FETCH_LOG.exists():
        return set()
    return set(pd.read_csv(FETCH_LOG)["date"].astype(str))


def backfill(start: date, end: date, pause: float = 0.15) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    done = _done()
    s = _session()
    n = 0
    with open(FETCH_LOG, "a", encoding="utf8") as log:
        if not done:
            log.write("date,status\n")
        d = start
        while d <= end:
            key = d.isoformat()
            if d.weekday() < 5 and key not in done:
                for attempt in range(3):
                    try:
                        status, df = fetch_day(s, d)
                        break
                    except Exception:
                        time.sleep(1 + attempt)
                        s = _session()
                else:
                    d += timedelta(days=1)
                    continue
                if df is not None:
                    df.to_parquet(RAW_DIR / f"gold_{key}.parquet", index=False)
                log.write(f"{key},{status}\n")
                log.flush()
                n += 1
                if n % 50 == 0:
                    print(f"  {key}: {n} days fetched")
                time.sleep(pause)
            d += timedelta(days=1)


def load_raw() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("gold_*.parquet"))
    if not files:
        raise FileNotFoundError("no raw data; run `python -m assay.ingest`")
    df = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    return df.drop_duplicates(["date", "symbol", "expiry"]).sort_values(["date", "symbol", "expiry"]).reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    a = ap.parse_args()
    backfill(datetime.fromisoformat(a.start).date(), datetime.fromisoformat(a.end).date())
    print("done")
