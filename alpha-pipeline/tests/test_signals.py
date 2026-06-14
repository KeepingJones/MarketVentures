"""
Unit tests for signal generation logic.

Tests the pure math helpers without hitting Yahoo Finance.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from unittest.mock import patch

from signals.engine import _direction_confidence, equity_momentum, fx_carry


class TestDirectionConfidence:
    def test_positive_value_gives_long(self):
        direction, confidence = _direction_confidence(0.5, threshold=0.3)
        assert direction == "long"
        assert confidence > 0

    def test_negative_value_gives_short(self):
        direction, confidence = _direction_confidence(-0.5, threshold=0.3)
        assert direction == "short"
        assert confidence > 0

    def test_within_threshold_gives_flat(self):
        direction, confidence = _direction_confidence(0.1, threshold=0.3)
        assert direction == "flat"
        assert confidence == 0.0

    def test_confidence_capped_at_1(self):
        _, confidence = _direction_confidence(100.0, threshold=0.01)
        assert confidence <= 1.0

    def test_zero_value_gives_flat(self):
        direction, _ = _direction_confidence(0.0, threshold=0.3)
        assert direction == "flat"


class TestEquityMomentum:
    def _make_trending_returns(self) -> pd.Series:
        """
        Returns series where recent 20-day avg >> 60-day avg → positive z-score → long.
        First 40 days: -0.003/day (down). Last 30 days: +0.010/day (strong up).
        ma20 (last 20 of 70) >> ma60 (all 70) → z > 0.3 threshold.
        """
        down = [-0.003] * 40
        up = [0.010] * 30
        return pd.Series(down + up)

    def test_strong_uptrend_gives_long_signal(self):
        returns = self._make_trending_returns()
        with patch("signals.engine.get_historical_returns", return_value=returns):
            result = equity_momentum("AAPL", prices_map={"AAPL": 180.0})
        assert result is not None
        assert result["direction"] == "long"
        assert result["ticker"] == "AAPL"

    def test_no_price_in_map_returns_none(self):
        returns = self._make_trending_returns()
        with patch("signals.engine.get_historical_returns", return_value=returns):
            result = equity_momentum("AAPL", prices_map={})
        assert result is None

    def test_insufficient_history_returns_none(self):
        short_returns = pd.Series([0.001] * 5)  # only 5 days
        with patch("signals.engine.get_historical_returns", return_value=short_returns):
            result = equity_momentum("AAPL", prices_map={"AAPL": 180.0})
        assert result is None

    def test_confidence_between_0_and_1(self):
        returns = self._make_trending_returns()
        with patch("signals.engine.get_historical_returns", return_value=returns):
            result = equity_momentum("AAPL", prices_map={"AAPL": 180.0})
        if result:
            assert 0 < result["confidence"] <= 1.0

    def test_signal_includes_metadata(self):
        returns = self._make_trending_returns()
        with patch("signals.engine.get_historical_returns", return_value=returns):
            result = equity_momentum("AAPL", prices_map={"AAPL": 180.0})
        if result:
            assert "z_score" in result["metadata"]
            assert "ma20" in result["metadata"]
            assert "ma60" in result["metadata"]


class TestFxCarry:
    def test_positive_carry_gives_long_base(self):
        rates = {"GBP": 0.05, "USD": 0.02}  # GBP rate > USD → long GBP
        with patch("signals.engine.get_risk_free_rates", return_value=rates):
            result = fx_carry("GBPUSD=X", prices_map={"GBPUSD=X": 1.27})
        assert result is not None
        assert result["direction"] == "long"

    def test_negative_carry_gives_short_base(self):
        rates = {"GBP": 0.01, "USD": 0.05}  # USD rate > GBP → short GBP
        with patch("signals.engine.get_risk_free_rates", return_value=rates):
            result = fx_carry("GBPUSD=X", prices_map={"GBPUSD=X": 1.27})
        assert result is not None
        assert result["direction"] == "short"

    def test_equal_rates_returns_none(self):
        rates = {"GBP": 0.05, "USD": 0.05}
        with patch("signals.engine.get_risk_free_rates", return_value=rates):
            result = fx_carry("GBPUSD=X", prices_map={"GBPUSD=X": 1.27})
        assert result is None
