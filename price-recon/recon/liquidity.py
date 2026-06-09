"""
Liquidity tiering: L1 / L2 / L3 by 30-day Average Daily Volume (ADV).

Used to set appropriate price tolerance thresholds — illiquid instruments
have wider bid-ask spreads and legitimately larger source discrepancies.
Also used for position sizing limits in alpha-pipeline.
"""
import logging
from typing import Optional

import yfinance as yf

from config import LIQUIDITY_TIERS

logger = logging.getLogger(__name__)


def get_adv_usd(ticker: str) -> Optional[float]:
    """Fetch 30-day ADV in USD. Returns None if data unavailable."""
    try:
        hist = yf.Ticker(ticker).history(period="30d")
        if hist.empty or "Volume" not in hist.columns:
            return None
        # ADV = mean(close * volume) over 30 days
        adv = float((hist["Close"] * hist["Volume"]).mean())
        return adv if adv > 0 else None
    except Exception as e:
        logger.warning(f"ADV fetch failed for {ticker}: {e}")
        return None


def get_liquidity_tier(ticker: str, asset_class: str, adv_usd: Optional[float] = None) -> str:
    """
    Classify instrument into L1/L2/L3.

    L1 — highly liquid (large cap equities, major FX, benchmark govt bonds)
         ADV > $100M, max 10% of ADV per position, liquidate in 1 day
    L2 — semi-liquid (mid cap equities, IG corps, commodity ETFs)
         ADV $10M–$100M, max 5% of ADV, liquidate in 5 days
    L3 — illiquid (small cap, HY credit, exotic FX, options)
         ADV < $10M, max 2% of ADV, liquidate in 20+ days
    """
    # Hard-code tier for derivatives / vol indices (price-only, no meaningful ADV)
    if asset_class in ("volatility", "option"):
        return "L2"

    if adv_usd is None:
        adv_usd = get_adv_usd(ticker)

    if adv_usd is None:
        # Default to L3 (conservative) when data unavailable
        return "L3"

    if adv_usd >= LIQUIDITY_TIERS["L1"]["min_adv_usd"]:
        return "L1"
    elif adv_usd >= LIQUIDITY_TIERS["L2"]["min_adv_usd"]:
        return "L2"
    return "L3"


def get_tolerance_for_tier(base_tolerance_pct: float, tier: str) -> float:
    """
    Scale tolerance by liquidity tier.
    L1: base tolerance. L2: 1.5x. L3: 3x.
    """
    multipliers = {"L1": 1.0, "L2": 1.5, "L3": 3.0}
    return base_tolerance_pct * multipliers.get(tier, 1.0)


def max_position_adv_pct(tier: str) -> float:
    return LIQUIDITY_TIERS.get(tier, LIQUIDITY_TIERS["L3"])["max_position_adv_pct"]


def days_to_liquidate(position_value_usd: float, adv_usd: float, tier: str) -> float:
    """Estimated days to fully liquidate a position at max_position_adv_pct of ADV."""
    if adv_usd <= 0:
        return 999.0
    max_daily_liquidation = adv_usd * max_position_adv_pct(tier)
    if max_daily_liquidation <= 0:
        return 999.0
    return round(position_value_usd / max_daily_liquidation, 1)
