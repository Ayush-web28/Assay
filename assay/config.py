from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
FETCH_LOG = ROOT / "data" / "fetch_log.csv"

BASE = "https://www.mcxindia.com/market-data/bhavcopy"
ENDPOINT = BASE + "/GetDateWiseBhavCopy"

# Contract mechanics (from the MCX gold contract specifications in the problem statement).
#   unit_g   : trading unit (grams per lot)
#   quote_g  : grams the quoted price refers to
#   purity   : fineness (995 / 999)
SPECS = {
    "GOLDM":      dict(unit_g=100, quote_g=10, purity=995),
    "GOLDTEN":    dict(unit_g=10,  quote_g=10, purity=999),
    "GOLDGUINEA": dict(unit_g=8,   quote_g=8,  purity=999),
    "GOLDPETAL":  dict(unit_g=1,   quote_g=1,  purity=999),
}
SYMBOLS = list(SPECS)
REF_PURITY = 999
