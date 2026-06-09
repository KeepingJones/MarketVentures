"""
market-ops DB layer.

Reads from all upstream projects' tables via shared fund.db.
DuckDB is used for aggregation queries — significantly faster on large tables.
Writes only to ops_sla_events and ops_fund_snapshots (owned by market-ops).
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import SHARED_DB_PATH, SLA_TRACKING_WINDOW_DAYS, SLA_PENALTY_RATE_PER_HOUR


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SHARED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _duckdb_conn():
    import duckdb
    conn = duckdb.connect()
    conn.execute(f"ATTACH '{SHARED_DB_PATH}' AS fund (TYPE SQLITE)")
    return conn


def init_db():
    schema = Path(__file__).parent / "schema.sql"
    with _conn() as c:
        c.executescript(schema.read_text())


# ── Upstream reads (via SQLite) ───────────────────────────────────────────────

def get_open_breaks() -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM price_breaks WHERE resolved = 0 ORDER BY severity, timestamp DESC LIMIT 50"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_breaks_summary() -> dict:
    try:
        with _conn() as c:
            rows = c.execute(
                """SELECT asset_class, severity, COUNT(*) as count
                   FROM price_breaks WHERE resolved = 0
                   GROUP BY asset_class, severity"""
            ).fetchall()
        summary: dict = {}
        for r in rows:
            ac = r["asset_class"]
            if ac not in summary:
                summary[ac] = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
            summary[ac][r["severity"]] = r["count"]
        return summary
    except Exception:
        return {}


def get_latest_positions() -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM positions ORDER BY market_value_gbp DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_portfolio_snapshot() -> Optional[dict]:
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def get_vendor_quality_scores() -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute(
                """SELECT qs.vendor_id, v.name as vendor_name,
                          qs.overall_score, qs.freshness_score,
                          qs.completeness_score, qs.latency_minutes, qs.scored_at
                   FROM quality_scores qs
                   JOIN vendors v ON v.id = qs.vendor_id
                   WHERE qs.id IN (SELECT MAX(id) FROM quality_scores GROUP BY vendor_id)
                   ORDER BY qs.overall_score DESC"""
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_active_vendors() -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute("SELECT * FROM vendors WHERE status = 'active'").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_active_fx_forwards() -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM fx_forwards WHERE expires_at > ? ORDER BY created_at DESC",
                (datetime.utcnow().isoformat(),)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_recent_trades(limit: int = 20) -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── Analytics (DuckDB) ────────────────────────────────────────────────────────

def get_pnl_by_asset_class() -> list[dict]:
    try:
        conn = _duckdb_conn()
        rows = conn.execute(
            """SELECT asset_class,
                      SUM(market_value_gbp) as total_mv_gbp,
                      SUM(unrealised_pnl_gbp) as total_pnl_gbp,
                      COUNT(*) as position_count
               FROM fund.positions
               GROUP BY asset_class
               ORDER BY total_mv_gbp DESC"""
        ).fetchall()
        conn.close()
        return [{"asset_class": r[0], "total_mv_gbp": r[1],
                 "total_pnl_gbp": r[2], "position_count": r[3]} for r in rows]
    except Exception:
        return []


def get_nav_history(limit: int = 30) -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT timestamp, nav_gbp, var_95_gbp, drawdown_pct FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── SLA penalty engine ────────────────────────────────────────────────────────

def log_sla_event(vendor_id: str, event_type: str,
                  duration_minutes: Optional[float] = None,
                  feed_latency: Optional[float] = None, notes: str = ""):
    with _conn() as c:
        c.execute(
            """INSERT INTO ops_sla_events
               (vendor_id, event_type, duration_minutes, feed_latency_minutes, notes, timestamp)
               VALUES (?,?,?,?,?,?)""",
            (vendor_id, event_type, duration_minutes, feed_latency, notes,
             datetime.utcnow().isoformat())
        )


def compute_sla_penalties() -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(days=SLA_TRACKING_WINDOW_DAYS)).isoformat()
    vendors = get_active_vendors()
    penalties = []

    with _conn() as c:
        for vendor in vendors:
            vid = vendor["id"]
            rows = c.execute(
                """SELECT SUM(COALESCE(duration_minutes, 0)) as total_outage_min,
                          COUNT(*) as outage_count
                   FROM ops_sla_events
                   WHERE vendor_id = ? AND event_type = 'outage_start' AND timestamp >= ?""",
                (vid, cutoff)
            ).fetchone()
            total_outage_min = float(rows["total_outage_min"] or 0)
            total_outage_hours = total_outage_min / 60

            monthly_cost = vendor.get("cost_usd_annual", 0) / 12
            penalty = round(total_outage_hours * SLA_PENALTY_RATE_PER_HOUR * monthly_cost, 2)

            penalties.append({
                "vendor_id": vid,
                "vendor_name": vendor.get("name", vid),
                "total_outage_hours": round(total_outage_hours, 2),
                "outage_count": rows["outage_count"],
                "monthly_cost_usd": round(monthly_cost, 2),
                "penalty_usd": penalty,
            })

    return sorted(penalties, key=lambda p: -p["penalty_usd"])


# ── Ops snapshots ─────────────────────────────────────────────────────────────

def save_ops_snapshot():
    snapshot = get_portfolio_snapshot()
    vendors = get_active_vendors()
    breaks = get_open_breaks()
    critical = sum(1 for b in breaks if b.get("severity") == "CRITICAL")

    with _conn() as c:
        c.execute(
            """INSERT INTO ops_fund_snapshots
               (nav_gbp, peak_nav_gbp, drawdown_pct, var_95_gbp, var_99_gbp,
                open_breaks, critical_breaks, active_vendors, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                snapshot.get("nav_gbp", 0) if snapshot else 0,
                snapshot.get("peak_nav_gbp", 0) if snapshot else 0,
                snapshot.get("drawdown_pct", 0) if snapshot else 0,
                snapshot.get("var_95_gbp", 0) if snapshot else 0,
                snapshot.get("var_99_gbp", 0) if snapshot else 0,
                len(breaks), critical, len(vendors),
                datetime.utcnow().isoformat(),
            )
        )


def get_ops_snapshot_history(limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM ops_fund_snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
