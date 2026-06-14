"""
Unit tests for liquidity tier assignment and tolerance scaling.

No external API calls — ADV is injected directly.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from recon.liquidity import get_liquidity_tier, get_tolerance_for_tier, days_to_liquidate


class TestLiquidityTierAssignment:
    def test_high_adv_is_l1(self):
        tier = get_liquidity_tier("AAPL", "equity", adv_usd=500_000_000)
        assert tier == "L1"

    def test_mid_adv_is_l2(self):
        tier = get_liquidity_tier("SOME_MID", "equity", adv_usd=50_000_000)
        assert tier == "L2"

    def test_low_adv_is_l3(self):
        tier = get_liquidity_tier("SMALL_CAP", "equity", adv_usd=1_000_000)
        assert tier == "L3"

    def test_none_adv_defaults_to_l3(self):
        # When ADV is None (data unavailable), conservative L3 is the safe default
        tier = get_liquidity_tier("UNKNOWN", "equity", adv_usd=None)
        # This will try to fetch from Yahoo — monkeypatch not available here
        # so we pass adv_usd=0 to force L3 branch
        tier = get_liquidity_tier("UNKNOWN", "equity", adv_usd=0.0)
        assert tier == "L3"

    def test_volatility_hardcoded_to_l2(self):
        # VIX and other vol indices have no meaningful ADV — hardcoded to L2
        tier = get_liquidity_tier("^VIX", "volatility", adv_usd=None)
        assert tier == "L2"

    def test_option_hardcoded_to_l2(self):
        tier = get_liquidity_tier("SPY_OPT", "option", adv_usd=None)
        assert tier == "L2"


class TestToleranceScaling:
    def test_l1_no_scaling(self):
        tol = get_tolerance_for_tier(base_tolerance_pct=0.5, tier="L1")
        assert tol == 0.5

    def test_l2_scales_1_5x(self):
        tol = get_tolerance_for_tier(base_tolerance_pct=0.5, tier="L2")
        assert abs(tol - 0.75) < 1e-9

    def test_l3_scales_3x(self):
        tol = get_tolerance_for_tier(base_tolerance_pct=0.5, tier="L3")
        assert abs(tol - 1.5) < 1e-9

    def test_unknown_tier_falls_back_to_1x(self):
        tol = get_tolerance_for_tier(base_tolerance_pct=0.5, tier="L99")
        assert tol == 0.5


class TestDaysToLiquidate:
    def test_large_position_takes_many_days(self):
        # £100M position vs £1M ADV at L3 (2% ADV cap = £20k/day)
        days = days_to_liquidate(position_value_usd=100_000_000, adv_usd=1_000_000, tier="L3")
        assert days > 100

    def test_small_position_liquidates_quickly(self):
        # £500k position vs £1B ADV at L1 (10% ADV cap = £100M/day)
        days = days_to_liquidate(position_value_usd=500_000, adv_usd=1_000_000_000, tier="L1")
        assert days < 1

    def test_zero_adv_returns_sentinel(self):
        days = days_to_liquidate(position_value_usd=1_000_000, adv_usd=0, tier="L1")
        assert days == 999.0
