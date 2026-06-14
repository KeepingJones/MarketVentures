"""
Unit tests for risk/performance.py — Sharpe, Sortino, CAGR, performance_summary.

All tests use deterministic synthetic NAV series so they're reproducible.
"""
import pytest

from risk.performance import sharpe_ratio, sortino_ratio, cagr, performance_summary


def _flat_nav(n: int = 10, start: float = 100_000.0) -> list[float]:
    """Constant NAV — zero returns — edge-case input."""
    return [start] * n


def _growing_nav(n: int = 252, start: float = 100_000.0, daily_return: float = 0.001) -> list[float]:
    """Geometrically compounding NAV with fixed daily return."""
    nav = [start]
    for _ in range(n - 1):
        nav.append(nav[-1] * (1 + daily_return))
    return nav


def _volatile_nav(n: int = 30) -> list[float]:
    """Alternating up/down: +2%, -1.5% every other day — creates downside vol."""
    nav = [100_000.0]
    for i in range(n - 1):
        r = 0.02 if i % 2 == 0 else -0.015
        nav.append(nav[-1] * (1 + r))
    return nav


class TestSharpeRatio:
    def test_too_short_returns_none(self):
        assert sharpe_ratio([100_000.0]) is None

    def test_flat_nav_returns_none(self):
        # All returns zero → std=0 → undefined
        assert sharpe_ratio(_flat_nav()) is None

    def test_positive_trend_gives_positive_sharpe(self):
        nav = _growing_nav(daily_return=0.001)
        result = sharpe_ratio(nav)
        assert result is not None
        assert result > 0

    def test_negative_trend_gives_negative_sharpe(self):
        nav = _growing_nav(daily_return=-0.002)
        result = sharpe_ratio(nav)
        assert result is not None
        assert result < 0

    def test_higher_return_higher_sharpe(self):
        low = sharpe_ratio(_growing_nav(daily_return=0.0005))
        high = sharpe_ratio(_growing_nav(daily_return=0.002))
        assert low is not None and high is not None
        assert high > low

    def test_result_is_float(self):
        result = sharpe_ratio(_growing_nav())
        assert isinstance(result, float)


class TestSortinoRatio:
    def test_too_short_returns_none(self):
        assert sortino_ratio([100_000.0]) is None

    def test_all_up_days_returns_none(self):
        # No down days → downside std = 0 → undefined (not infinite)
        nav = _growing_nav(n=20, daily_return=0.001)
        assert sortino_ratio(nav) is None

    def test_volatile_nav_gives_positive_sortino(self):
        result = sortino_ratio(_volatile_nav())
        assert result is not None
        assert result > 0

    def test_sortino_higher_than_sharpe_for_positive_skew(self):
        # Volatile but net positive series: Sortino should exceed Sharpe
        # because upside vol is excluded from denominator
        nav = _volatile_nav(n=30)
        sharpe = sharpe_ratio(nav)
        sortino = sortino_ratio(nav)
        assert sharpe is not None and sortino is not None
        assert sortino > sharpe


class TestCagr:
    def test_too_short_returns_none(self):
        assert cagr([100_000.0]) is None

    def test_flat_returns_zero(self):
        result = cagr([100_000.0, 100_000.0])
        assert result == pytest.approx(0.0, abs=0.01)

    def test_doubling_over_252_days_is_100_pct(self):
        nav = [100_000.0, 200_000.0]
        result = cagr(nav, trading_days=252)
        assert result == pytest.approx(100.0, abs=0.01)

    def test_zero_start_returns_none(self):
        assert cagr([0.0, 100_000.0]) is None

    def test_positive_trend(self):
        nav = _growing_nav(n=252, daily_return=0.001)
        result = cagr(nav)
        assert result is not None
        assert result > 0


class TestPerformanceSummary:
    def test_empty_history_returns_none_values(self):
        result = performance_summary([])
        assert result["sharpe"] is None
        assert result["sortino"] is None
        assert result["n_days"] == 0

    def test_keys_present(self):
        history = [{"nav_gbp": float(v), "drawdown_pct": 0.0}
                   for v in _growing_nav(n=10)]
        result = performance_summary(history)
        assert set(result.keys()) == {
            "sharpe", "sortino", "cagr_pct",
            "max_drawdown_pct", "total_return_pct", "n_days"
        }

    def test_n_days_matches_history_length(self):
        n = 15
        history = [{"nav_gbp": float(v), "drawdown_pct": 0.0}
                   for v in _growing_nav(n=n)]
        result = performance_summary(history)
        assert result["n_days"] == n

    def test_positive_trend_positive_total_return(self):
        # DB returns newest-first — reverse the chronological series
        nav_oldest_first = _growing_nav(n=30, daily_return=0.002)
        history = [{"nav_gbp": float(v), "drawdown_pct": 0.0}
                   for v in reversed(nav_oldest_first)]
        result = performance_summary(history)
        assert result["total_return_pct"] > 0

    def test_max_drawdown_taken_from_snapshots(self):
        history = [
            {"nav_gbp": 100_000.0, "drawdown_pct": 0.0},
            {"nav_gbp": 95_000.0, "drawdown_pct": 5.0},
            {"nav_gbp": 97_000.0, "drawdown_pct": 3.0},
        ]
        result = performance_summary(history)
        assert result["max_drawdown_pct"] == pytest.approx(5.0, abs=0.01)

    def test_reversal_order_handled(self):
        # performance_summary reverses history (DB returns newest-first)
        nav_values = [100_000, 101_000, 102_000, 103_000]
        # Newest-first (as DB returns)
        history = [{"nav_gbp": float(v), "drawdown_pct": 0.0}
                   for v in reversed(nav_values)]
        result = performance_summary(history)
        # total_return should be positive (103k vs 100k after reversal)
        assert result["total_return_pct"] > 0
