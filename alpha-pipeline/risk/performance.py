"""
Portfolio performance attribution: Sharpe ratio, Sortino ratio, CAGR.

All metrics computed from the portfolio_snapshots table — no external
data needed beyond what the agent already records.

Sharpe  = (mean_daily_return - rf_daily) / std_daily_return  * sqrt(252)
Sortino = (mean_daily_return - rf_daily) / downside_std      * sqrt(252)

Downside std uses only negative daily returns (semi-deviation), which
penalises volatility below the risk-free rate more than upside swings.
We use 0.0 as the Minimum Acceptable Return (MAR) for simplicity —
suitable for a paper portfolio where we're measuring absolute loss risk.
"""
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_ANNUALISE = math.sqrt(252)
_RF_ANNUAL = 0.052   # SONIA approx — update from FRED if needed
_RF_DAILY = (1 + _RF_ANNUAL) ** (1 / 252) - 1


def _nav_to_daily_returns(nav_series: list[float]) -> list[float]:
    """Convert a list of daily NAV values to daily % returns."""
    if len(nav_series) < 2:
        return []
    return [(nav_series[i] - nav_series[i - 1]) / nav_series[i - 1]
            for i in range(1, len(nav_series))]


def sharpe_ratio(nav_series: list[float]) -> Optional[float]:
    """
    Annualised Sharpe ratio from a NAV time series.

    Returns None when there are fewer than 2 observations or zero volatility.
    """
    returns = _nav_to_daily_returns(nav_series)
    if len(returns) < 2:
        return None

    n = len(returns)
    mean_r = sum(returns) / n
    excess = mean_r - _RF_DAILY
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)

    if std == 0:
        return None
    return round((excess / std) * _ANNUALISE, 3)


def sortino_ratio(nav_series: list[float]) -> Optional[float]:
    """
    Annualised Sortino ratio from a NAV time series.

    Uses 0% MAR (Minimum Acceptable Return) so any day with negative
    return contributes to downside deviation.
    """
    returns = _nav_to_daily_returns(nav_series)
    if len(returns) < 2:
        return None

    n = len(returns)
    mean_r = sum(returns) / n
    excess = mean_r - _RF_DAILY

    # Downside deviation: only negative returns vs MAR (0)
    downside_sq = [r ** 2 for r in returns if r < 0]
    if not downside_sq:
        return None  # no down days — undefined (infinite is misleading)

    downside_std = math.sqrt(sum(downside_sq) / n)
    if downside_std == 0:
        return None
    return round((excess / downside_std) * _ANNUALISE, 3)


def cagr(nav_series: list[float], trading_days: Optional[int] = None) -> Optional[float]:
    """
    Compound Annual Growth Rate.

    trading_days defaults to len(nav_series) - 1, i.e. one snapshot per day.
    """
    if len(nav_series) < 2 or nav_series[0] <= 0:
        return None
    n = trading_days if trading_days is not None else len(nav_series) - 1
    if n <= 0:
        return None
    total_return = nav_series[-1] / nav_series[0]
    return round((total_return ** (252 / n) - 1) * 100, 2)


def performance_summary(snapshot_history: list[dict]) -> dict:
    """
    Compute all performance metrics from the snapshot history list returned
    by db.database.get_snapshot_history().

    Returns a dict with keys: sharpe, sortino, cagr_pct, max_drawdown_pct,
    total_return_pct, n_days.
    """
    if not snapshot_history:
        return {"sharpe": None, "sortino": None, "cagr_pct": None,
                "max_drawdown_pct": None, "total_return_pct": None, "n_days": 0}

    # History comes newest-first from the DB — reverse for chronological order
    ordered = list(reversed(snapshot_history))
    nav_series = [s["nav_gbp"] for s in ordered]
    initial = nav_series[0]

    sharpe = sharpe_ratio(nav_series)
    sortino = sortino_ratio(nav_series)
    cagr_pct = cagr(nav_series)

    max_dd = max((s.get("drawdown_pct", 0) for s in ordered), default=0.0)
    total_return = (nav_series[-1] / initial - 1) * 100 if initial > 0 else 0.0

    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "cagr_pct": cagr_pct,
        "max_drawdown_pct": round(max_dd, 3),
        "total_return_pct": round(total_return, 3),
        "n_days": len(nav_series),
    }
