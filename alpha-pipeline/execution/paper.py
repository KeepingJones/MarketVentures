"""
Paper execution layer.

Equities: Alpaca Paper API (real paper account, no live capital).
FX / Bonds / Commodities: Internal ledger (no paper API for these).

PAPER_TRADE_MODE = True hardcoded — this file should never touch live endpoints.
"""
import logging
from typing import Optional

from config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY, PAPER_TRADE_MODE, MAX_POSITION_PCT, FUND_INITIAL_NAV,
)
from db.database import save_trade, upsert_position, get_nav_gbp

logger = logging.getLogger(__name__)

assert PAPER_TRADE_MODE, "PAPER_TRADE_MODE must be True — never execute on live capital"


def _get_alpaca_client():
    try:
        from alpaca.trading.client import TradingClient
        return TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
    except ImportError:
        logger.warning("alpaca-py not installed — falling back to internal ledger for equities")
        return None


def _position_size_gbp(signal_confidence: float, nav_gbp: float) -> float:
    base_size = nav_gbp * MAX_POSITION_PCT
    return round(base_size * min(signal_confidence, 1.0), 2)


def execute_equity(signal: dict, fx_rate_to_gbp: float = 1.0) -> Optional[dict]:
    client = _get_alpaca_client()
    ticker = signal["ticker"]
    direction = signal["direction"]
    price = signal["price"]
    nav = get_nav_gbp() or FUND_INITIAL_NAV

    size_gbp = _position_size_gbp(signal["confidence"], nav)
    quantity = round(size_gbp / (price * fx_rate_to_gbp), 4)
    if quantity < 0.001:
        logger.info(f"Skipping {ticker} — position size too small")
        return None

    side = "buy" if direction == "long" else "sell"

    alpaca_order_id = None
    if client:
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
            req = MarketOrderRequest(
                symbol=ticker,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(req)
            alpaca_order_id = str(order.id)
            logger.info(f"Alpaca paper order: {side} {quantity} {ticker} @ ~{price} | id={alpaca_order_id}")
        except Exception as e:
            logger.warning(f"Alpaca order failed for {ticker}: {e} — recording in internal ledger only")

    price_gbp = price * fx_rate_to_gbp
    save_trade(
        ticker=ticker, asset_class=signal["asset_class"],
        direction=side, quantity=quantity, price=price,
        currency=signal.get("currency", "USD"),
        price_gbp=price_gbp, signal_source=signal["signal_type"],
        broker="alpaca" if alpaca_order_id else "internal_ledger",
        alpaca_order_id=alpaca_order_id,
    )

    upsert_position(
        ticker=ticker, asset_class=signal["asset_class"],
        currency=signal.get("currency", "USD"),
        quantity=quantity if side == "buy" else -quantity,
        avg_entry_price=price,
        current_price=price, market_value_gbp=size_gbp,
        unrealised_pnl_gbp=0.0, liquidity_tier=signal.get("liquidity_tier", "L2"),
    )

    return {
        "status": "executed",
        "ticker": ticker, "direction": side,
        "quantity": quantity, "price": price,
        "value_gbp": size_gbp, "alpaca_order_id": alpaca_order_id,
        "broker": "alpaca" if alpaca_order_id else "internal_ledger",
    }


def execute_internal_ledger(signal: dict, fx_rate_to_gbp: float = 1.0) -> dict:
    ticker = signal["ticker"]
    direction = signal["direction"]
    price = signal["price"]
    nav = get_nav_gbp() or FUND_INITIAL_NAV

    size_gbp = _position_size_gbp(signal["confidence"], nav)
    quantity = round(size_gbp / max(price * fx_rate_to_gbp, 0.0001), 4)
    side = "buy" if direction == "long" else "sell"
    price_gbp = price * fx_rate_to_gbp

    save_trade(
        ticker=ticker, asset_class=signal["asset_class"],
        direction=side, quantity=quantity, price=price,
        currency=signal.get("currency", "USD"),
        price_gbp=price_gbp, signal_source=signal["signal_type"],
        broker="internal_ledger",
    )
    upsert_position(
        ticker=ticker, asset_class=signal["asset_class"],
        currency=signal.get("currency", "USD"),
        quantity=quantity if side == "buy" else -quantity,
        avg_entry_price=price, current_price=price,
        market_value_gbp=size_gbp, unrealised_pnl_gbp=0.0,
        liquidity_tier=signal.get("liquidity_tier", "L2"),
    )
    logger.info(f"Internal ledger: {side} {quantity} {ticker} @ {price} (£{size_gbp:.0f})")
    return {
        "status": "executed",
        "ticker": ticker, "direction": side,
        "quantity": quantity, "price": price,
        "value_gbp": size_gbp, "broker": "internal_ledger",
    }


def route_signal(signal: dict, fx_rates: dict[str, float]) -> Optional[dict]:
    ac = signal.get("asset_class", "")
    currency = signal.get("currency", "USD")
    from risk.fx_hedge import spot_to_gbp
    fx_rate = spot_to_gbp(1.0, currency, fx_rates) if currency != "GBP" else 1.0

    if ac == "equity":
        return execute_equity(signal, fx_rate_to_gbp=fx_rate)
    else:
        return execute_internal_ledger(signal, fx_rate_to_gbp=fx_rate)
