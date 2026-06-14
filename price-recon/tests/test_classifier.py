"""
Unit tests for the break classifier — all 8 cause paths.

These tests do NOT call any external API. They exercise the pure classification
logic by constructing PriceQuote objects directly.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from data.models import PriceQuote
from recon.classifier import classify_break


def _quote(ticker="AAPL", source="yahoo", price=100.0, asset_class="equity",
           is_stale=False) -> PriceQuote:
    return PriceQuote(
        ticker=ticker, source=source, asset_class=asset_class,
        currency="USD", price=price, is_stale=is_stale,
        timestamp=datetime.utcnow(),
    )


class TestClassifierCauses:
    def test_zero_price_is_data_quality_critical(self):
        q_a = _quote(price=0.0)
        q_b = _quote(source="fred", price=100.0)
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=100.0, tolerance_pct=0.5)
        assert cause == "DATA_QUALITY"
        assert severity == "CRITICAL"

    def test_negative_price_is_data_quality_critical(self):
        q_a = _quote(price=-5.0)
        q_b = _quote(source="fred", price=100.0)
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=100.0, tolerance_pct=0.5)
        assert cause == "DATA_QUALITY"
        assert severity == "CRITICAL"

    def test_stale_price_flagged_as_warning(self):
        q_a = _quote(price=100.0, is_stale=True)
        q_b = _quote(source="fred", price=102.0)
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=2.0, tolerance_pct=0.5)
        assert cause == "STALE_PRICE"
        assert severity == "WARNING"

    def test_tiny_diff_is_spread_within_normal(self):
        q_a = _quote(price=100.0)
        q_b = _quote(source="fred", price=100.04)
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=0.04, tolerance_pct=0.5)
        assert cause == "SPREAD_WITHIN_NORMAL"
        assert severity == "INFO"

    def test_fx_genuine_discrepancy_is_always_critical(self):
        q_a = _quote(ticker="GBPUSD=X", asset_class="fx", price=1.27)
        q_b = _quote(ticker="GBPUSD=X", source="ecb", asset_class="fx", price=1.28)
        cause, severity = classify_break("GBPUSD=X", "fx", q_a, q_b, diff_pct=0.8, tolerance_pct=0.5)
        assert cause == "GENUINE_DISCREPANCY"
        assert severity == "CRITICAL"

    def test_equity_large_diff_is_corporate_action(self):
        q_a = _quote(price=200.0)
        q_b = _quote(source="fred", price=100.0)
        # 50% diff — likely a split
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=50.0, tolerance_pct=0.5)
        assert cause == "CORPORATE_ACTION"
        assert severity == "WARNING"

    def test_within_tolerance_is_spread_within_normal(self):
        q_a = _quote(price=100.0)
        q_b = _quote(source="fred", price=100.3)
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=0.3, tolerance_pct=0.5)
        assert cause == "SPREAD_WITHIN_NORMAL"
        assert severity == "INFO"

    def test_bond_small_diff_fx_conversion(self):
        q_a = _quote(ticker="GB10Y", asset_class="govt_bond", price=98.5)
        q_b = _quote(ticker="GB10Y", source="fred", asset_class="govt_bond", price=99.5)
        cause, severity = classify_break("GB10Y", "govt_bond", q_a, q_b, diff_pct=1.0, tolerance_pct=0.5)
        assert cause == "FX_CONVERSION"
        assert severity == "WARNING"

    def test_large_genuine_break_is_critical(self):
        q_a = _quote(price=100.0)
        q_b = _quote(source="fred", price=93.0)
        # diff = 7%, tolerance = 0.5% → diff > 3x tolerance → CRITICAL
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=7.0, tolerance_pct=0.5)
        assert cause == "GENUINE_DISCREPANCY"
        assert severity == "CRITICAL"

    def test_moderate_genuine_break_is_warning(self):
        q_a = _quote(price=100.0)
        q_b = _quote(source="fred", price=98.5)
        # diff = 1.5%, tolerance = 0.5% → diff < 3x tolerance → WARNING
        cause, severity = classify_break("AAPL", "equity", q_a, q_b, diff_pct=1.5, tolerance_pct=0.5)
        assert cause == "GENUINE_DISCREPANCY"
        assert severity == "WARNING"
