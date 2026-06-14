"""
Bloomberg B-PIPE mock data source.

Real production market data infrastructure uses Bloomberg Professional
(B-PIPE / BLPAPI). This module simulates that feed so the reconciliation
engine can demonstrate three-way price validation:

    Yahoo Finance  ─┐
    FRED           ─┼──► recon/engine.py ──► classify_break()
    Bloomberg mock ─┘

The mock reproduces realistic Bloomberg field names (PX_LAST, BID, ASK,
VOLUME, SECURITY_TYP) and applies a small, configurable random spread so
discrepancies are detectable but not always critical.

To swap in a real Bloomberg connection:
    1. Install blpapi: pip install blpapi
    2. Replace _bloomberg_field_request() with a real BDP/BDH call
    3. Map Bloomberg field names to PriceQuote as below
    4. Ensure the Bloomberg terminal or B-PIPE server is running locally

Bloomberg field reference (relevant subset):
    PX_LAST   — last trade price
    BID       — best bid
    ASK       — best ask
    VOLUME    — daily volume
    CRNCY     — ISO currency of the security
    SECURITY_TYP — security type string (e.g. "Common Stock", "Corp")
"""
import logging
import random
from datetime import datetime
from typing import Optional

from config import INSTRUMENTS
from data.models import PriceQuote

logger = logging.getLogger(__name__)

# Simulates Bloomberg's typical spread vs Yahoo Finance: ±0.03% random noise
# Real Bloomberg often differs from Yahoo on stale after-hours ticks
_BLOOMBERG_SPREAD_PCT = 0.0003

# Tickers Bloomberg typically covers better (adds value over Yahoo)
_BLOOMBERG_PREFERRED = {
    "govt_bond", "corp_bond", "fx",
}


def _bloomberg_field_request(ticker: str, fields: list[str]) -> Optional[dict]:
    """
    Simulate a Bloomberg BDP (reference data) request.

    In production this would be:
        import blpapi
        session = blpapi.Session()
        session.start()
        refDataService = session.getService("//blp/refdata")
        request = refDataService.createRequest("ReferenceDataRequest")
        request.append("securities", ticker)
        for f in fields:
            request.append("fields", f)
        session.sendRequest(request)
        # ... parse events ...

    We return a dict matching the Bloomberg response schema.
    """
    # Bloomberg uses its own ticker format: "AAPL US Equity", "GBPUSD Curncy"
    # We accept Yahoo-format tickers and map back for display only
    return {
        "ticker": ticker,
        "PX_LAST": None,       # filled in by caller
        "BID": None,
        "ASK": None,
        "VOLUME": None,
        "CRNCY": None,
        "SECURITY_TYP": None,
        "ERROR_CODE": 0,       # 0 = success in BLPAPI
    }


def get_bloomberg_quotes(
    instruments: Optional[list[dict]] = None,
    seed: Optional[int] = None,
) -> list[PriceQuote]:
    """
    Return simulated Bloomberg prices for all instruments.

    Applies a small random spread vs expected fair value so the
    reconciliation engine sees realistic discrepancies.

    Args:
        instruments: list of instrument dicts from config.INSTRUMENTS.
                     Defaults to all instruments.
        seed: random seed for reproducibility in tests.
    """
    if instruments is None:
        instruments = INSTRUMENTS

    if seed is not None:
        random.seed(seed)

    quotes: list[PriceQuote] = []

    # Import Yahoo prices as a base — Bloomberg would have its own feed
    # In production, replace with actual B-PIPE subscription prices
    try:
        from data.sources.yahoo import get_bulk_quotes
        yahoo_quotes = get_bulk_quotes(instruments)
        yahoo_prices = {q.ticker: q.price for q in yahoo_quotes if q.price > 0}
    except Exception as e:
        logger.warning(f"Bloomberg mock: could not fetch Yahoo base prices: {e}")
        yahoo_prices = {}

    for inst in instruments:
        ticker = inst["ticker"]
        asset_class = inst["asset_class"]
        currency = inst["currency"]

        base_price = yahoo_prices.get(ticker)
        if base_price is None or base_price <= 0:
            logger.debug(f"Bloomberg mock: no base price for {ticker}, skipping")
            continue

        # Simulate Bloomberg's tick — small spread from Yahoo
        # Bloomberg is more authoritative on bonds/FX; noisier on equity after-hours
        spread = _BLOOMBERG_SPREAD_PCT
        if asset_class in _BLOOMBERG_PREFERRED:
            spread *= 0.5  # Bloomberg tighter on fixed income / FX

        noise = random.uniform(-spread, spread)
        bloomberg_price = round(base_price * (1 + noise), 6)

        # Simulate realistic bid/ask around the last price
        half_spread = base_price * 0.0001  # 1bp half-spread
        bid = round(bloomberg_price - half_spread, 6)
        ask = round(bloomberg_price + half_spread, 6)

        # Simulate an occasional stale tick (1% chance — Bloomberg has TTL)
        is_stale = random.random() < 0.01

        blp_response = _bloomberg_field_request(ticker, ["PX_LAST", "BID", "ASK"])
        blp_response["PX_LAST"] = bloomberg_price
        blp_response["BID"] = bid
        blp_response["ASK"] = ask
        blp_response["CRNCY"] = currency

        quotes.append(PriceQuote(
            ticker=ticker,
            source="bloomberg",
            asset_class=asset_class,
            currency=currency,
            price=bloomberg_price,
            bid=bid,
            ask=ask,
            timestamp=datetime.utcnow(),
            is_stale=is_stale,
        ))

    logger.info(f"Bloomberg mock: returned {len(quotes)} quotes for {len(instruments)} instruments")
    return quotes
