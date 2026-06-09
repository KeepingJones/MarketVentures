"""
Parametric VaR — 1-day 95% and 99% confidence intervals.

Uses normal distribution assumption with 252-day lookback.
Also computes position-level Greeks for SPY options via QuantLib
and runs stress tests under 3 scenarios.

Pattern adapted from trading-bot/risk/portfolio_risk.py.
"""
import logging
import math
from typing import Optional

from scipy import stats

from config import (
    VAR_CONFIDENCE_95, VAR_CONFIDENCE_99, VAR_LOOKBACK_DAYS,
    STRESS_SCENARIOS,
)
from data.sources.yahoo import get_historical_returns

logger = logging.getLogger(__name__)

# Z-scores for confidence levels
_Z95 = stats.norm.ppf(VAR_CONFIDENCE_95)  # 1.645
_Z99 = stats.norm.ppf(VAR_CONFIDENCE_99)  # 2.326


def position_var(ticker: str, market_value_gbp: float,
                 lookback: int = VAR_LOOKBACK_DAYS) -> dict:
    returns = get_historical_returns(ticker, days=lookback)
    if returns is None or len(returns) < 20:
        sigma = 0.02  # fallback: assume 2% daily vol
        logger.warning(f"No return history for {ticker}, using fallback vol")
    else:
        sigma = float(returns.std())

    var_95 = round(market_value_gbp * sigma * _Z95, 2)
    var_99 = round(market_value_gbp * sigma * _Z99, 2)
    return {
        "ticker": ticker,
        "market_value_gbp": round(market_value_gbp, 2),
        "daily_vol": round(sigma, 6),
        "var_95_gbp": var_95,
        "var_99_gbp": var_99,
    }


def portfolio_var(positions: list[dict]) -> dict:
    """
    Diversified portfolio VaR using correlations.
    Simplification: assumes 0.5 average pairwise correlation (conservative).
    """
    if not positions:
        return {"var_95_gbp": 0.0, "var_99_gbp": 0.0, "positions": []}

    pos_vars = []
    for pos in positions:
        v = position_var(pos["ticker"], pos.get("market_value_gbp", 0))
        pos_vars.append(v)

    # Portfolio VaR with correlation: sqrt(sum(w_i * w_j * rho_ij * var_i * var_j))
    # Using rho=0.5 approximation
    n = len(pos_vars)
    total_var_95 = 0.0
    total_var_99 = 0.0
    for i in range(n):
        for j in range(n):
            rho = 1.0 if i == j else 0.5
            total_var_95 += rho * pos_vars[i]["var_95_gbp"] * pos_vars[j]["var_95_gbp"]
            total_var_99 += rho * pos_vars[i]["var_99_gbp"] * pos_vars[j]["var_99_gbp"]

    portfolio_var_95 = round(math.sqrt(max(total_var_95, 0)), 2)
    portfolio_var_99 = round(math.sqrt(max(total_var_99, 0)), 2)

    return {
        "var_95_gbp": portfolio_var_95,
        "var_99_gbp": portfolio_var_99,
        "var_95_pct_nav": round(portfolio_var_95 / max(sum(p.get("market_value_gbp", 0) for p in positions), 1) * 100, 3),
        "var_99_pct_nav": round(portfolio_var_99 / max(sum(p.get("market_value_gbp", 0) for p in positions), 1) * 100, 3),
        "positions": pos_vars,
    }


def stress_test(positions: list[dict]) -> dict:
    results = {}
    nav = sum(p.get("market_value_gbp", 0) for p in positions)

    for scenario_name, shocks in STRESS_SCENARIOS.items():
        scenario_pnl = 0.0
        for pos in positions:
            ac = pos.get("asset_class", "")
            shock = 0.0
            if ac == "equity":
                shock = shocks.get("equity", 0.0)
            elif ac == "govt_bond":
                shock = shocks.get("govt_bond", 0.0)
            elif ac in ("corp_bond",):
                shock = shocks.get("credit", 0.0)
            elif ac == "fx":
                shock = shocks.get("fx_gbp", 0.0)
            mv = pos.get("market_value_gbp", 0.0)
            scenario_pnl += mv * shock
        results[scenario_name] = round(scenario_pnl, 2)

    return {
        "stress_results": results,
        "nav_gbp": round(nav, 2),
        "worst_case_gbp": round(min(results.values()) if results else 0.0, 2),
        "worst_case_pct": round(min(results.values()) / max(nav, 1) * 100 if results else 0.0, 3),
    }


def options_greeks(ticker: str = "SPY", strike: Optional[float] = None,
                   spot: Optional[float] = None, expiry_days: int = 30) -> Optional[dict]:
    try:
        import QuantLib as ql

        if spot is None:
            from data.sources.yahoo import get_price
            spot = get_price(ticker)
        if spot is None:
            return None
        if strike is None:
            strike = round(spot * 1.02, 2)  # 2% OTM call

        r = 0.053  # approximate risk-free rate
        sigma = 0.20  # approximate implied vol

        today = ql.Date.todaysDate()
        expiry = today + expiry_days
        day_count = ql.Actual365Fixed()
        calendar = ql.UnitedStates(ql.UnitedStates.NYSE)

        spot_handle = ql.QuoteHandle(ql.SimpleQuote(float(spot)))
        flat_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(today, r, day_count)
        )
        div_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(today, 0.0, day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(today, calendar, sigma, day_count)
        )
        process = ql.BlackScholesMertonProcess(spot_handle, div_ts, flat_ts, vol_ts)

        payoff = ql.PlainVanillaPayoff(ql.Option.Call, float(strike))
        exercise = ql.EuropeanExercise(expiry)
        option = ql.VanillaOption(payoff, exercise)
        engine = ql.AnalyticEuropeanEngine(process)
        option.setPricingEngine(engine)

        return {
            "ticker": ticker,
            "spot": spot,
            "strike": strike,
            "expiry_days": expiry_days,
            "price": round(option.NPV(), 4),
            "delta": round(option.delta(), 4),
            "gamma": round(option.gamma(), 6),
            "vega": round(option.vega() / 100, 4),
            "theta": round(option.theta() / 365, 4),
        }
    except ImportError:
        logger.warning("QuantLib not installed — skipping Greeks")
        return None
    except Exception as e:
        logger.warning(f"Options Greeks failed for {ticker}: {e}")
        return None
