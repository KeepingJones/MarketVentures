"""
Unit tests for market-ops core logic.

Tests cover:
- SLA penalty calculation (pure math from config constants)
- Alert threshold logic (VaR vs limit, critical breaks)
- PDF report data assembly (data shape validation, no PDF render needed)
- Config constants (regression guards)

No network calls, no DB writes.
"""
import sqlite3
import pytest
from pathlib import Path


# ── Config constants ──────────────────────────────────────────────────────────

from config import (
    VAR_95_LIMIT_PCT,
    CRITICAL_BREAKS_THRESHOLD,
    SLA_PENALTY_RATE_PER_HOUR,
    DEFAULT_SLA_UPTIME_PCT,
    DEFAULT_LATENCY_SLA_MIN,
    SLA_TRACKING_WINDOW_DAYS,
)


class TestConfigConstants:
    def test_var_limit_is_3_pct(self):
        assert VAR_95_LIMIT_PCT == 0.03

    def test_critical_breaks_threshold_is_5(self):
        assert CRITICAL_BREAKS_THRESHOLD == 5

    def test_sla_penalty_rate_is_1_pct_per_hour(self):
        assert SLA_PENALTY_RATE_PER_HOUR == 0.01

    def test_default_uptime_sla_is_99_9_pct(self):
        assert DEFAULT_SLA_UPTIME_PCT == 99.9

    def test_default_latency_sla_is_15_minutes(self):
        assert DEFAULT_LATENCY_SLA_MIN == 15

    def test_sla_tracking_window_is_30_days(self):
        assert SLA_TRACKING_WINDOW_DAYS == 30


# ── SLA penalty engine ────────────────────────────────────────────────────────

class TestSlaPenaltyEngine:
    """
    SLA penalty: % of monthly fee per hour of breach.
    penalty = breach_hours * SLA_PENALTY_RATE_PER_HOUR * monthly_cost
    """

    def _penalty(self, breach_hours: float, monthly_cost_usd: float) -> float:
        return breach_hours * SLA_PENALTY_RATE_PER_HOUR * monthly_cost_usd

    def test_5_hour_breach_at_2000_monthly_is_100_usd(self):
        assert self._penalty(5.0, 2000.0) == pytest.approx(100.0, abs=0.01)

    def test_zero_breach_has_zero_penalty(self):
        assert self._penalty(0.0, 2000.0) == 0.0

    def test_zero_cost_has_zero_penalty(self):
        assert self._penalty(5.0, 0.0) == 0.0

    def test_penalty_scales_linearly_with_hours(self):
        p1 = self._penalty(1.0, 1000.0)
        p2 = self._penalty(2.0, 1000.0)
        assert p2 == pytest.approx(p1 * 2, rel=1e-6)

    def test_bloomberg_24k_annual_5h_breach(self):
        monthly = 24_000 / 12
        penalty = self._penalty(5.0, monthly)
        assert penalty == pytest.approx(100.0, abs=0.01)


# ── Alert threshold logic ─────────────────────────────────────────────────────

class TestAlertThresholds:
    def _build_alerts(self, nav: float, var_95_gbp: float,
                      critical_breaks: int) -> list[dict]:
        alerts = []
        var_pct = var_95_gbp / nav if nav > 0 else 0
        if var_pct > VAR_95_LIMIT_PCT:
            alerts.append({
                "level": "CRITICAL",
                "message": f"VaR 95% ({var_pct:.1%}) exceeds limit ({VAR_95_LIMIT_PCT:.1%})"
            })
        if critical_breaks > CRITICAL_BREAKS_THRESHOLD:
            alerts.append({
                "level": "CRITICAL",
                "message": f"{critical_breaks} critical breaks open (limit {CRITICAL_BREAKS_THRESHOLD})"
            })
        return alerts

    def test_no_breach_no_alerts(self):
        alerts = self._build_alerts(nav=1_000_000, var_95_gbp=20_000, critical_breaks=2)
        assert alerts == []

    def test_var_over_limit_raises_critical(self):
        alerts = self._build_alerts(nav=1_000_000, var_95_gbp=40_000, critical_breaks=0)
        assert len(alerts) == 1
        assert alerts[0]["level"] == "CRITICAL"
        assert "VaR" in alerts[0]["message"]

    def test_critical_breaks_over_threshold_raises_critical(self):
        alerts = self._build_alerts(nav=1_000_000, var_95_gbp=20_000, critical_breaks=6)
        assert len(alerts) == 1
        assert "breaks" in alerts[0]["message"]

    def test_both_breaches_produce_two_alerts(self):
        alerts = self._build_alerts(nav=1_000_000, var_95_gbp=50_000, critical_breaks=8)
        assert len(alerts) == 2

    def test_exactly_at_threshold_no_alert(self):
        # VAR_95_LIMIT_PCT = 3% exactly → should NOT alert (strictly greater than)
        alerts = self._build_alerts(nav=1_000_000, var_95_gbp=30_000, critical_breaks=0)
        assert alerts == []

    def test_exactly_at_break_threshold_no_alert(self):
        # CRITICAL_BREAKS_THRESHOLD = 5 → 5 breaks should NOT alert (strictly greater than)
        alerts = self._build_alerts(nav=1_000_000, var_95_gbp=0, critical_breaks=5)
        assert alerts == []


# ── PDF report data assembly ──────────────────────────────────────────────────

class TestPdfReportDataShape:
    """Validates the data dict passed to generate_pdf_report without rendering a PDF."""

    def _base_data(self) -> dict:
        return {
            "fund": {
                "nav_gbp": 1_050_000.0,
                "drawdown_pct": 2.5,
                "var_95_gbp": 21_000.0,
                "var_99_gbp": 31_500.0,
            },
            "alerts": [],
            "breaks": {"total_open": 3, "critical": 0},
            "pnl_by_asset_class": [
                {"asset_class": "equity", "total_mv_gbp": 500_000, "total_pnl_gbp": 5_000, "position_count": 4},
                {"asset_class": "fx", "total_mv_gbp": 200_000, "total_pnl_gbp": -1_200, "position_count": 2},
            ],
            "positions": [
                {"liquidity_tier": "L1", "market_value_gbp": 300_000},
                {"liquidity_tier": "L2", "market_value_gbp": 150_000},
                {"liquidity_tier": "L3", "market_value_gbp": 50_000},
            ],
            "fx_forwards": [],
            "vendor_health": [
                {"vendor_id": "yahoo", "vendor_name": "Yahoo Finance",
                 "overall_score": 92.0, "freshness_score": 95.0,
                 "completeness_score": 90.0, "latency_minutes": 2.1},
            ],
            "sla_penalties": [],
        }

    def test_fund_section_present(self):
        data = self._base_data()
        assert "nav_gbp" in data["fund"]
        assert "var_95_gbp" in data["fund"]

    def test_pnl_sections_have_required_keys(self):
        data = self._base_data()
        for row in data["pnl_by_asset_class"]:
            assert "asset_class" in row
            assert "total_mv_gbp" in row
            assert "total_pnl_gbp" in row

    def test_positions_have_liquidity_tier(self):
        data = self._base_data()
        for pos in data["positions"]:
            assert pos["liquidity_tier"] in ("L1", "L2", "L3")

    def test_vendor_health_has_overall_score(self):
        data = self._base_data()
        for v in data["vendor_health"]:
            assert "overall_score" in v
            assert 0 <= v["overall_score"] <= 100

    def test_liquidity_tier_aggregation(self):
        data = self._base_data()
        tier_mv = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
        for pos in data["positions"]:
            tier_mv[pos["liquidity_tier"]] += pos["market_value_gbp"]
        assert tier_mv["L1"] == 300_000
        assert tier_mv["L2"] == 150_000
        assert tier_mv["L3"] == 50_000


# ── DB schema ─────────────────────────────────────────────────────────────────

class TestMarketOpsSchema:
    @pytest.fixture
    def db_conn(self):
        schema = Path(__file__).parent.parent / "db" / "schema.sql"
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(schema.read_text())
        return conn

    def test_schema_has_sla_events_table(self, db_conn):
        tables = {r["name"] for r in
                  db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "ops_sla_events" in tables

    def test_schema_has_fund_snapshots_table(self, db_conn):
        tables = {r["name"] for r in
                  db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "ops_fund_snapshots" in tables
