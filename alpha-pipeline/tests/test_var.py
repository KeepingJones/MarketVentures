"""
Unit tests for parametric VaR and stress testing.

All tests use injected data — no Yahoo Finance calls.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch
import pandas as pd
import numpy as np
import pytest

from risk.var import position_var, portfolio_var, stress_test


def _mock_returns(vol: float = 0.01, n: int = 252) -> pd.Series:
    """Deterministic return series with known volatility."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0, vol, n)
    return pd.Series(returns)


class TestPositionVar:
    def test_var_95_less_than_var_99(self):
        with patch("risk.var.get_historical_returns", return_value=_mock_returns(0.02)):
            result = position_var("AAPL", market_value_gbp=100_000)
        assert result["var_95_gbp"] < result["var_99_gbp"]

    def test_var_scales_with_market_value(self):
        with patch("risk.var.get_historical_returns", return_value=_mock_returns(0.02)):
            r1 = position_var("AAPL", market_value_gbp=100_000)
            r2 = position_var("AAPL", market_value_gbp=200_000)
        assert abs(r2["var_95_gbp"] / r1["var_95_gbp"] - 2.0) < 0.01

    def test_fallback_vol_when_no_history(self):
        with patch("risk.var.get_historical_returns", return_value=None):
            result = position_var("UNKNOWN", market_value_gbp=100_000)
        # Fallback vol = 2%, Z95 ≈ 1.645 → VaR95 ≈ £3290
        expected = round(100_000 * 0.02 * 1.645, 2)
        assert abs(result["var_95_gbp"] - expected) < 5

    def test_zero_market_value_gives_zero_var(self):
        with patch("risk.var.get_historical_returns", return_value=_mock_returns(0.02)):
            result = position_var("AAPL", market_value_gbp=0)
        assert result["var_95_gbp"] == 0.0
        assert result["var_99_gbp"] == 0.0


class TestPortfolioVar:
    def test_empty_portfolio_returns_zeros(self):
        result = portfolio_var([])
        assert result["var_95_gbp"] == 0.0
        assert result["var_99_gbp"] == 0.0

    def test_portfolio_var_less_than_sum_of_parts(self):
        """Diversification benefit: portfolio VaR < sum of individual VaRs."""
        positions = [
            {"ticker": "AAPL", "market_value_gbp": 100_000, "asset_class": "equity"},
            {"ticker": "MSFT", "market_value_gbp": 100_000, "asset_class": "equity"},
        ]
        with patch("risk.var.get_historical_returns", return_value=_mock_returns(0.02)):
            result = portfolio_var(positions)
        # Individual VaRs ≈ £3290 each; sum ≈ £6580. Portfolio with rho=0.5 < £6580.
        assert result["var_95_gbp"] < 6_600
        assert result["var_95_gbp"] > 0

    def test_single_position_portfolio_var_equals_position_var(self):
        positions = [{"ticker": "AAPL", "market_value_gbp": 100_000, "asset_class": "equity"}]
        returns = _mock_returns(0.02)
        with patch("risk.var.get_historical_returns", return_value=returns):
            port_result = portfolio_var(positions)
        with patch("risk.var.get_historical_returns", return_value=returns):
            pos_result = position_var("AAPL", 100_000)
        assert abs(port_result["var_95_gbp"] - pos_result["var_95_gbp"]) < 1


class TestStressTest:
    def test_gfc_scenario_reduces_equity_positions(self):
        positions = [{"ticker": "AAPL", "market_value_gbp": 100_000, "asset_class": "equity"}]
        result = stress_test(positions)
        # GFC_2008: equity shock = -40% → P&L = -£40,000
        assert result["stress_results"]["GFC_2008"] == pytest.approx(-40_000, abs=1)

    def test_empty_portfolio_stress_is_zero(self):
        result = stress_test([])
        for pnl in result["stress_results"].values():
            assert pnl == 0.0

    def test_worst_case_is_most_negative(self):
        positions = [{"ticker": "AAPL", "market_value_gbp": 200_000, "asset_class": "equity"}]
        result = stress_test(positions)
        worst = result["worst_case_gbp"]
        for pnl in result["stress_results"].values():
            assert worst <= pnl

    def test_govt_bond_shock_applied(self):
        positions = [{"ticker": "GB10Y", "market_value_gbp": 100_000, "asset_class": "govt_bond"}]
        result = stress_test(positions)
        # RATE_SHOCK_2022: govt_bond = -15% → P&L = -£15,000
        assert result["stress_results"]["RATE_SHOCK_2022"] == pytest.approx(-15_000, abs=1)
