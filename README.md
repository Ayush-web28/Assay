# Assay: is the gold spread real, or just noise?

Cross-contract relative-value analytics on MCX gold futures (GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL),
built for Hack in Hills '26 (problem 03).

## Run

```bash
pip install -r requirements.txt
python -m assay.ingest --start 2023-01-01    # ~960 trading days, ~5 min, cached in data/raw
python -m assay.run                          # spreads, diagnostics, walk-forward backtest -> results/
python -m pytest -q tests
streamlit run app.py                         # dashboard
```

## Pipeline

| Step | Module | What it does |
|---|---|---|
| Ingest | `ingest.py` | Pulls the MCX Bhavcopy. Requested date is DD/MM/YYYY, response date is MM/DD/YYYY. Rows are rejected unless the returned date equals the requested one (MCX serves the latest day for holiday/malformed/future dates). Symbols are trimmed, expiry parsed from `04SEP2026`. |
| Normalize | `normalize.py` | Every contract to Rs per gram of 999 gold: `close / quote_g * 999 / purity`. |
| Spreads | `spreads.py` | Same-expiry pairs compared directly. GOLDM expires on the 5th, the others at month-end, so GOLDM is compared with the GOLDPETAL curve interpolated to GOLDM's expiry (monitor-only, not traded). |
| Backtest | `backtest.py` | Contracts tracked by `(pair, expiry)`, never a continuous series. z-score from past days only; signal on day t executes at settlement of t+1; flat before the expiry window. Costs charged on the contracts actually held. Quarterly walk-forward parameter selection on closed trades only. |
| Attribution | `backtest.gold_attribution` | Regresses net P&L on the daily gold move. Long/short legs are equal grams, so the beta should be ~0 and is reported. |

MCX blocks plain `requests` (403); `curl_cffi` with Chrome impersonation is required.

## Findings (data 2023-01-02 to 2026-09-24, 174 contracts)

* Normalization works: on 24 Sep 2026 all four contracts sit within ~0.3% of each other in Rs/g.
* **Persistent structural gaps, not arbitrage.** GOLDTEN trades about 96 bps below GOLDPETAL on average
  (GOLDGUINEA about 66 bps above). The pattern is stable, so only *deviations from the running level* are signal.
* **Mild deviations (|z| < 3) have no tradable edge.** After a signal you can only trade the next settlement;
  measured from there, 5-day reversion is 3 to 14 bps against 14 to 47 bps of modelled round-trip cost.
* **Large deviations (|z| > 3) revert, but the evidence is one episode.** About 70% of the TEN-pair events fall in
  January 2026 (the gold crash). Date-clustered t-stats are 1.7 to 4.1 on 25 to 36 distinct days.
* **Walk-forward with parameter selection loses money after costs** (few trades, selection on tiny samples).
* **Fixed default parameters:** GOLDGUINEA/GOLDPETAL breaks even at 0.2x the assumed costs (dead);
  the two GOLDTEN pairs break even at 2.2 to 2.5x, on 20 trades and 9 months, again dominated by January 2026.
* Gold attribution is reported, not assumed: equal-gram legs make the book roughly market-neutral, but the walk-forward P&L still shows a small significant negative gold beta (-0.066, t = -4.1), driven by the January 2026 crash days.

**Verdict:** no persistent edge survives costs in this sample. A dislocation-reversion effect is worth
monitoring but cannot be distinguished from a single crash episode yet.

## Caveats

* Costs (`HALF_SPREAD_BPS`, `FEE_BPS`, impact) are assumptions, not measured. Break-even cost scales are shown for that reason.
* Only settlement prices exist; settlement is not an executable price and Volume is not depth.
* GOLDTEN history starts 2025-03-31, so its pairs have about 9 months of warm-up plus a short test window.
* Lot rounding, margin and financing are ignored. Legs are sized in equal grams.
