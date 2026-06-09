"""
Signal generation per asset class.

Each generator returns: {"ticker", "signal_type", "direction", "confidence", "price"}

Signals are simple, explainable — the kind a PM can interrogate:
- Equities: momentum (20d vs 60d MA) + mean-reversion (Z-score)
- FX: carry (interest rate differential)
- Rates: yield curve slope
- Credit: spread compression/widening vs 30d avg
- Commodities: trend (50d EMA direction)
- Volatility: VIX regime (high vol = risk-off, reduce equity exposure)
"""
import logging
from typing import Optional


from data.sources.yahoo import get_historical_returns, INSTRUMENTS
from data.sources.fred import get_risk_free_rates, get_credit_spreads

logger = logging.getLogger(__name__)


def _direction_confidence(value: float, threshold: float = 0.0) -> tuple[str, float]:
    if value > threshold:
        return "long", min(1.0, abs(value) / (abs(threshold) + 0.01))
    elif value < -threshold:
        return "short", min(1.0, abs(value) / (abs(threshold) + 0.01))
    return "flat", 0.0


def equity_momentum(ticker: str, prices_map: dict[str, float]) -> Optional[dict]:
    returns = get_historical_returns(ticker, days=63)
    if returns is None or len(returns) < 20:
        return None
    try:
        ma20 = float(returns.iloc[-20:].mean())
        ma60 = float(returns.mean())
        z_score = (ma20 - ma60) / (returns.std() + 1e-9)

        direction, confidence = _direction_confidence(float(z_score), threshold=0.3)
        if direction == "flat":
            return None

        price = prices_map.get(ticker)
        if not price:
            return None

        return {
            "ticker": ticker,
            "asset_class": "equity",
            "signal_type": "momentum",
            "direction": direction,
            "confidence": round(min(confidence, 0.95), 3),
            "price": price,
            "metadata": {"z_score": round(float(z_score), 3), "ma20": round(ma20, 5), "ma60": round(ma60, 5)},
        }
    except Exception as e:
        logger.warning(f"Equity momentum failed for {ticker}: {e}")
        return None


def fx_carry(pair: str, prices_map: dict[str, float]) -> Optional[dict]:
    rates = get_risk_free_rates()
    try:
        # pair format "GBPUSD=X" → base=GBP, quote=USD
        base = pair[:3]
        quote = pair[3:6]
        r_base = rates.get(base, 0.0)
        r_quote = rates.get(quote, 0.0)
        carry = r_base - r_quote  # positive = long base is advantageous

        direction, confidence = _direction_confidence(carry, threshold=0.005)
        if direction == "flat":
            return None

        price = prices_map.get(pair)
        if not price:
            return None

        return {
            "ticker": pair,
            "asset_class": "fx",
            "signal_type": "carry",
            "direction": direction,
            "confidence": round(min(confidence * 10, 0.9), 3),
            "price": price,
            "metadata": {"carry_differential": round(carry, 5), "base_rate": r_base, "quote_rate": r_quote},
        }
    except Exception as e:
        logger.warning(f"FX carry failed for {pair}: {e}")
        return None


def rates_slope(prices_map: dict[str, float]) -> Optional[dict]:
    from data.sources.fred import get_series_latest
    try:
        y2 = get_series_latest("DGS2")
        y10 = get_series_latest("DGS10")
        if y2 is None or y10 is None:
            return None

        slope = (y10 - y2) * 100  # bps, already divided by 100 in fred.py

        direction = "long" if slope > 0.20 else ("short" if slope < -0.10 else "flat")
        if direction == "flat":
            return None

        price = prices_map.get("TLT", 0.0)
        return {
            "ticker": "TLT",
            "asset_class": "govt_bond",
            "signal_type": "yield_curve_slope",
            "direction": direction,
            "confidence": round(min(abs(slope) / 2.0, 0.85), 3),
            "price": price,
            "metadata": {"2y_yield": y2, "10y_yield": y10, "slope_bps": round(slope * 100, 1)},
        }
    except Exception as e:
        logger.warning(f"Rates slope signal failed: {e}")
        return None


def credit_spread_signal(prices_map: dict[str, float]) -> Optional[dict]:
    spreads = get_credit_spreads()
    ig_spread = spreads.get("BAMLC0A0CM")
    if ig_spread is None:
        return None

    # Simple mean-reversion: if spread is wide vs 12m avg → compress → long credit
    # We don't have 12m history so use threshold heuristic
    # IG spreads typically range 50–200bps; >150bps = wide = opportunity
    if ig_spread > 1.50:
        direction, confidence = "long", 0.70
    elif ig_spread < 0.80:
        direction, confidence = "short", 0.60
    else:
        return None

    price = prices_map.get("LQD", 0.0)
    return {
        "ticker": "LQD",
        "asset_class": "corp_bond",
        "signal_type": "spread_compression",
        "direction": direction,
        "confidence": confidence,
        "price": price,
        "metadata": {"ig_oas_bps": round(ig_spread, 2)},
    }


def commodity_trend(ticker: str, prices_map: dict[str, float]) -> Optional[dict]:
    returns = get_historical_returns(ticker, days=60)
    if returns is None or len(returns) < 10:
        return None
    try:
        ema50 = float(returns.ewm(span=50).mean().iloc[-1])
        direction, confidence = _direction_confidence(ema50, threshold=0.0005)
        if direction == "flat":
            return None
        price = prices_map.get(ticker)
        if not price:
            return None
        return {
            "ticker": ticker,
            "asset_class": "commodity",
            "signal_type": "trend",
            "direction": direction,
            "confidence": round(min(confidence * 20, 0.80), 3),
            "price": price,
            "metadata": {"ema50": round(ema50, 6)},
        }
    except Exception as e:
        logger.warning(f"Commodity trend failed for {ticker}: {e}")
        return None


def vix_regime(prices_map: dict[str, float]) -> Optional[dict]:
    vix = prices_map.get("^VIX")
    if not vix:
        return None
    # VIX > 25 = high fear = reduce equity = "short" signal on risk assets
    # VIX < 15 = complacency = increase equity = "long"
    if vix > 25:
        direction, confidence = "short", min((vix - 25) / 20, 0.9)
    elif vix < 15:
        direction, confidence = "long", min((15 - vix) / 10, 0.7)
    else:
        return None
    return {
        "ticker": "^VIX",
        "asset_class": "volatility",
        "signal_type": "vix_regime",
        "direction": direction,
        "confidence": round(confidence, 3),
        "price": vix,
        "metadata": {"vix_level": vix, "regime": "risk_off" if direction == "short" else "risk_on"},
    }


def generate_all_signals(prices_map: dict[str, float]) -> list[dict]:
    signals = []

    # Equities — momentum
    for inst in INSTRUMENTS:
        if inst["asset_class"] == "equity":
            sig = equity_momentum(inst["ticker"], prices_map)
            if sig:
                signals.append(sig)

    # FX — carry
    for inst in INSTRUMENTS:
        if inst["asset_class"] == "fx":
            sig = fx_carry(inst["ticker"], prices_map)
            if sig:
                signals.append(sig)

    # Rates — yield curve
    sig = rates_slope(prices_map)
    if sig:
        signals.append(sig)

    # Credit — spread compression
    sig = credit_spread_signal(prices_map)
    if sig:
        signals.append(sig)

    # Commodities — trend
    for inst in INSTRUMENTS:
        if inst["asset_class"] == "commodity":
            sig = commodity_trend(inst["ticker"], prices_map)
            if sig:
                signals.append(sig)

    # VIX regime
    sig = vix_regime(prices_map)
    if sig:
        signals.append(sig)

    signals.sort(key=lambda s: -s["confidence"])
    logger.info(f"Generated {len(signals)} signals")
    return signals
