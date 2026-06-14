"""
Unit tests for market-data-hub core logic.

Tests cover:
- Quality scoring functions (pure math, no external API calls)
- Entitlement engine (desk × licence_type logic)
- DB layer (in-memory SQLite to avoid touching shared fund.db)

No network calls, no disk writes to the shared DB.
"""
import sqlite3
import pytest
from datetime import datetime, timedelta


# ── Quality scorer pure functions ─────────────────────────────────────────────

from data.quality_scorer import _score_freshness, _score_completeness, _score_accuracy


class TestScoreFreshness:
    def test_within_sla_is_100(self):
        recent = datetime.utcnow() - timedelta(minutes=5)
        assert _score_freshness(recent, sla_latency_minutes=15) == 100.0

    def test_exactly_at_sla_is_100(self):
        at_sla = datetime.utcnow() - timedelta(minutes=15)
        assert _score_freshness(at_sla, sla_latency_minutes=15) == 100.0

    def test_2x_sla_is_70(self):
        stale = datetime.utcnow() - timedelta(minutes=25)
        result = _score_freshness(stale, sla_latency_minutes=15)
        assert result == 70.0

    def test_5x_sla_is_40(self):
        very_stale = datetime.utcnow() - timedelta(minutes=70)
        result = _score_freshness(very_stale, sla_latency_minutes=15)
        assert result == 40.0

    def test_beyond_5x_sla_is_10(self):
        ancient = datetime.utcnow() - timedelta(minutes=200)
        result = _score_freshness(ancient, sla_latency_minutes=15)
        assert result == 10.0

    def test_none_timestamp_is_zero(self):
        assert _score_freshness(None, sla_latency_minutes=15) == 0.0


class TestScoreCompleteness:
    def test_full_fields_is_100(self):
        assert _score_completeness(10, 10) == 100.0

    def test_zero_expected_is_100(self):
        assert _score_completeness(0, 0) == 100.0

    def test_half_fields_is_50(self):
        assert _score_completeness(5, 10) == 50.0

    def test_over_100_capped_at_100(self):
        assert _score_completeness(15, 10) == 100.0

    def test_zero_fields_present(self):
        assert _score_completeness(0, 10) == 0.0


class TestScoreAccuracy:
    def test_zero_deviation_is_100(self):
        assert _score_accuracy(100.0, 100.0) == 100.0

    def test_within_01_pct_is_100(self):
        assert _score_accuracy(100.05, 100.0) == 100.0

    def test_within_05_pct_is_90(self):
        assert _score_accuracy(100.4, 100.0) == 90.0

    def test_within_1_pct_is_75(self):
        assert _score_accuracy(100.8, 100.0) == 75.0

    def test_within_2_pct_is_50(self):
        assert _score_accuracy(101.5, 100.0) == 50.0

    def test_over_2_pct_is_20(self):
        assert _score_accuracy(103.0, 100.0) == 20.0

    def test_zero_benchmark_is_zero(self):
        assert _score_accuracy(100.0, 0.0) == 0.0


# ── Entitlement engine ────────────────────────────────────────────────────────

from config import DESK_ENTITLEMENTS, LICENCE_TYPES


class TestDeskEntitlements:
    def test_quant_desk_can_use_execution_licensed(self):
        assert "execution_licensed" in DESK_ENTITLEMENTS["quant"]

    def test_operations_desk_cannot_use_execution_licensed(self):
        assert "execution_licensed" not in DESK_ENTITLEMENTS["operations"]

    def test_credit_desk_cannot_use_execution_licensed(self):
        assert "execution_licensed" not in DESK_ENTITLEMENTS["credit"]

    def test_all_desks_can_use_display_only(self):
        for desk, licences in DESK_ENTITLEMENTS.items():
            assert "display_only" in licences, f"{desk} should have display_only"

    def test_seven_desks_defined(self):
        from config import DESKS
        assert len(DESKS) == 7

    def test_all_licence_types_are_valid(self):
        valid = set(LICENCE_TYPES)
        for desk, licences in DESK_ENTITLEMENTS.items():
            for lic in licences:
                assert lic in valid, f"{lic} for {desk} not in LICENCE_TYPES"


# ── Vendor registry completeness ──────────────────────────────────────────────

from config import VENDORS


class TestVendorConfig:
    def test_five_vendors_defined(self):
        assert len(VENDORS) == 5

    def test_bloomberg_is_inactive(self):
        bloomberg = next(v for v in VENDORS if v["id"] == "bloomberg")
        assert bloomberg["status"] == "inactive"

    def test_active_vendors_have_coverage(self):
        for v in VENDORS:
            if v["status"] == "active":
                assert len(v.get("coverage", [])) > 0, f"{v['id']} has no coverage"

    def test_all_vendors_have_required_fields(self):
        required = {"id", "name", "delivery", "cost_usd_annual", "sla_latency_minutes",
                    "coverage", "status"}
        for v in VENDORS:
            assert required <= set(v.keys()), f"{v['id']} missing fields"

    def test_yahoo_covers_equity_and_fx(self):
        yahoo = next(v for v in VENDORS if v["id"] == "yahoo")
        assert "equity" in yahoo["coverage"]
        assert "fx" in yahoo["coverage"]

    def test_bloomberg_is_expensive(self):
        bloomberg = next(v for v in VENDORS if v["id"] == "bloomberg")
        assert bloomberg["cost_usd_annual"] > 0


# ── DB layer (in-memory SQLite) ───────────────────────────────────────────────

class TestDatabaseLayer:
    @pytest.fixture
    def db_conn(self, tmp_path):
        """Isolated in-memory DB with schema applied."""
        from pathlib import Path
        schema = Path(__file__).parent.parent / "db" / "schema.sql"
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(schema.read_text())
        return conn

    def test_schema_creates_vendors_table(self, db_conn):
        tables = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        assert "vendors" in table_names
        assert "datasets" in table_names
        assert "quality_scores" in table_names

    def test_vendor_insert_and_select(self, db_conn):
        db_conn.execute(
            "INSERT INTO vendors (id, name, delivery, status, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            ("test_vendor", "Test Co", "REST API", "active", "2024-01-01", "2024-01-01")
        )
        row = db_conn.execute(
            "SELECT * FROM vendors WHERE id = 'test_vendor'"
        ).fetchone()
        assert row is not None
        assert row["name"] == "Test Co"

    def test_quality_score_insert(self, db_conn):
        db_conn.execute(
            "INSERT INTO vendors (id, name, delivery, status, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            ("v1", "V1", "API", "active", "2024-01-01", "2024-01-01")
        )
        db_conn.execute(
            "INSERT INTO quality_scores"
            " (vendor_id, freshness_score, completeness_score, accuracy_score, overall_score, scored_at)"
            " VALUES (?,?,?,?,?,?)",
            ("v1", 90.0, 85.0, 95.0, 90.0, "2024-01-01T12:00:00")
        )
        row = db_conn.execute(
            "SELECT * FROM quality_scores WHERE vendor_id = 'v1'"
        ).fetchone()
        assert row["overall_score"] == 90.0

    def test_usage_event_insert(self, db_conn):
        db_conn.execute(
            "INSERT INTO vendors (id, name, delivery, status, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            ("v2", "V2", "API", "active", "2024-01-01", "2024-01-01")
        )
        db_conn.execute(
            "INSERT INTO usage_events (vendor_id, desk, event_type, records_fetched, timestamp)"
            " VALUES (?,?,?,?,?)",
            ("v2", "equity", "query", 100, "2024-01-01T12:00:00")
        )
        row = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM usage_events WHERE vendor_id = 'v2'"
        ).fetchone()
        assert row["cnt"] == 1

    def test_entitlement_check_insert(self, db_conn):
        db_conn.execute(
            "INSERT INTO entitlement_checks"
            " (vendor_id, desk, licence_type, allowed, reason, timestamp)"
            " VALUES (?,?,?,?,?,?)",
            ("bloomberg", "operations", "execution_licensed", 0,
             "operations desk not entitled", "2024-01-01T12:00:00")
        )
        row = db_conn.execute(
            "SELECT allowed FROM entitlement_checks WHERE desk = 'operations'"
        ).fetchone()
        assert row["allowed"] == 0
