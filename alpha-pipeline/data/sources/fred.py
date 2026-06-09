"""FRED data source — rates, macro, credit spreads. Reused pattern from price-recon."""
import logging
from datetime import datetime, timedelta
from typing import Optional


from config import FRED_API_KEY, FRED_RATE_SERIES

logger = logging.getLogger(__name__)

FRED_SERIES_MAP = {
    "DGS2":            {"name": "US 2Y Treasury Yield",        "asset_class": "govt_bond",    "currency": "USD"},
    "DGS10":           {"name": "US 10Y Treasury Yield",       "asset_class": "govt_bond",    "currency": "USD"},
    "DGS30":           {"name": "US 30Y Treasury Yield",       "asset_class": "govt_bond",    "currency": "USD"},
    "BAMLC0A0CM":      {"name": "US IG OAS Spread",            "asset_class": "corp_bond",    "currency": "USD"},
    "BAMLH0A0HYM2":    {"name": "US HY OAS Spread",            "asset_class": "corp_bond",    "currency": "USD"},
    "DFF":             {"name": "Fed Funds Rate (SOFR proxy)", "asset_class": "rate",         "currency": "USD"},
    "IUDSOIA":         {"name": "SONIA",                       "asset_class": "rate",         "currency": "GBP"},
    "ECBESTRVOLWGTTRMD": {"name": "ESTR",                      "asset_class": "rate",         "currency": "EUR"},
    "IRSTCI01JPM156N": {"name": "JP Overnight Rate",           "asset_class": "rate",         "currency": "JPY"},
    "CPIAUCSL":        {"name": "US CPI",                      "asset_class": "macro",        "currency": "USD"},
    "UNRATE":          {"name": "US Unemployment Rate",        "asset_class": "macro",        "currency": "USD"},
}


def _get_fred():
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set")
        return None
    import fredapi
    return fredapi.Fred(api_key=FRED_API_KEY)


def get_rate(series_id: str) -> Optional[float]:
    fred = _get_fred()
    if not fred:
        return None
    try:
        end = datetime.today()
        start = end - timedelta(days=10)
        data = fred.get_series(series_id, observation_start=start.strftime("%Y-%m-%d"))
        data = data.dropna()
        return float(data.iloc[-1]) / 100.0 if not data.empty else None
    except Exception as e:
        logger.error(f"FRED rate fetch failed for {series_id}: {e}")
        return None


def get_risk_free_rates() -> dict[str, float]:
    rates = {}
    for currency, series_id in FRED_RATE_SERIES.items():
        r = get_rate(series_id)
        if r is not None:
            rates[currency] = r
    # Fallback to approximate rates if FRED unavailable
    defaults = {"USD": 0.053, "GBP": 0.052, "EUR": 0.040, "JPY": 0.001}
    for currency, default in defaults.items():
        rates.setdefault(currency, default)
    return rates


def get_credit_spreads() -> dict[str, float]:
    spreads = {}
    for series_id in ("BAMLC0A0CM", "BAMLH0A0HYM2"):
        val = get_rate(series_id)
        if val is not None:
            spreads[series_id] = val * 100  # convert back to bps display
    return spreads


def get_series_latest(series_id: str) -> Optional[float]:
    return get_rate(series_id)
