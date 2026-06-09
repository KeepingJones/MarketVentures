"""
FX hedging via simulated FX forwards using interest rate parity.

F = S * (1 + r_d)^(T/365) / (1 + r_f)^(T/365)

Where:
  S  = spot rate (foreign per GBP)
  r_d = GBP domestic risk-free rate (SONIA)
  r_f = foreign currency risk-free rate (SOFR / ESTR / JPY overnight)
  T  = tenor in days

All non-GBP positions are hedged at FX_HEDGE_RATIO (default 100%).
"""
import logging

from config import FX_HEDGE_RATIO, FUND_BASE_CURRENCY
from data.sources.fred import get_risk_free_rates
from data.sources.yahoo import get_bulk_prices
from db.database import save_fx_forward

logger = logging.getLogger(__name__)

_FX_PAIRS = {
    "USD": "GBPUSD=X",
    "EUR": "EURUSD=X",
    "JPY": "USDJPY=X",
    "CHF": "USDCHF=X",
}


def spot_to_gbp(price: float, currency: str, fx_rates: dict[str, float]) -> float:
    if currency == "GBP":
        return price
    if currency == "USD":
        gbpusd = fx_rates.get("GBPUSD=X", 1.27)
        return price / gbpusd
    if currency == "EUR":
        eurusd = fx_rates.get("EURUSD=X", 1.08)
        gbpusd = fx_rates.get("GBPUSD=X", 1.27)
        return price * eurusd / gbpusd
    if currency == "JPY":
        usdjpy = fx_rates.get("USDJPY=X", 150.0)
        gbpusd = fx_rates.get("GBPUSD=X", 1.27)
        return price / usdjpy / gbpusd
    return price


def forward_rate(spot: float, r_domestic: float, r_foreign: float,
                 tenor_days: int = 30) -> float:
    t = tenor_days / 365.0
    return spot * ((1 + r_domestic) ** t) / ((1 + r_foreign) ** t)


def compute_hedge(
    positions: list[dict],
    tenor_days: int = 30,
    save_to_db: bool = True,
) -> list[dict]:
    rates = get_risk_free_rates()
    r_gbp = rates.get("GBP", 0.052)

    fx_tickers = list(_FX_PAIRS.values())
    fx_prices = get_bulk_prices(fx_tickers)

    hedges = []
    currency_exposures: dict[str, float] = {}

    for pos in positions:
        currency = pos.get("currency", "GBP")
        if currency == FUND_BASE_CURRENCY:
            continue
        mv_gbp = pos.get("market_value_gbp", 0.0)
        currency_exposures[currency] = currency_exposures.get(currency, 0.0) + mv_gbp

    for currency, exposure_gbp in currency_exposures.items():
        pair_ticker = _FX_PAIRS.get(currency)
        if not pair_ticker:
            logger.warning(f"No FX pair configured for {currency}")
            continue

        spot = fx_prices.get(pair_ticker)
        if spot is None:
            logger.warning(f"No spot rate for {pair_ticker}")
            continue

        r_foreign = rates.get(currency, 0.05)

        if currency == "JPY":
            # USDJPY is quoted as JPY per USD — invert to get USD/JPY for IRP
            spot_for_irp = 1.0 / spot
            fwd = forward_rate(spot_for_irp, r_domestic=r_gbp, r_foreign=r_foreign,
                               tenor_days=tenor_days)
            fwd = 1.0 / fwd
        else:
            # GBPUSD, EURUSD: express as currency per GBP for IRP
            if currency == "USD":
                spot_for_irp = spot  # GBPUSD already in USD per GBP
            elif currency == "EUR":
                gbpusd = fx_prices.get("GBPUSD=X", 1.27)
                eurusd = spot
                spot_for_irp = gbpusd / eurusd  # GBP/EUR
            else:
                spot_for_irp = spot
            fwd = forward_rate(spot_for_irp, r_domestic=r_gbp, r_foreign=r_foreign,
                               tenor_days=tenor_days)

        notional_gbp = round(exposure_gbp * FX_HEDGE_RATIO, 2)
        hedge_pnl = round((fwd - spot_for_irp) * notional_gbp / spot_for_irp, 2)

        hedge = {
            "currency": currency,
            "pair": pair_ticker,
            "exposure_gbp": round(exposure_gbp, 2),
            "notional_gbp": notional_gbp,
            "spot_rate": round(spot, 6),
            "forward_rate": round(fwd, 6) if currency != "JPY" else round(fwd, 4),
            "tenor_days": tenor_days,
            "r_domestic": r_gbp,
            "r_foreign": r_foreign,
            "hedge_pnl_estimate_gbp": hedge_pnl,
        }
        hedges.append(hedge)

        if save_to_db:
            try:
                save_fx_forward(
                    pair=pair_ticker,
                    notional_gbp=notional_gbp,
                    spot_rate=spot,
                    forward_rate=fwd,
                    tenor_days=tenor_days,
                    domestic_rate=r_gbp,
                    foreign_rate=r_foreign,
                )
            except Exception as e:
                logger.warning(f"Failed to save FX forward for {pair_ticker}: {e}")

    return hedges


def fx_pnl_attribution(positions: list[dict], fx_rates: dict[str, float]) -> list[dict]:
    attribution = []
    for pos in positions:
        currency = pos.get("currency", "GBP")
        if currency == "GBP":
            continue
        mv_local = pos.get("quantity", 0) * pos.get("current_price", 0)
        mv_gbp = spot_to_gbp(mv_local, currency, fx_rates)
        entry_gbp = spot_to_gbp(
            pos.get("quantity", 0) * pos.get("avg_entry_price", 0),
            currency, fx_rates
        )
        fx_contribution = mv_gbp - entry_gbp
        attribution.append({
            "ticker": pos["ticker"],
            "currency": currency,
            "fx_contribution_gbp": round(fx_contribution, 2),
            "mv_gbp": round(mv_gbp, 2),
        })
    return attribution
