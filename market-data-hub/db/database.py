import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import SHARED_DB_PATH, VENDORS


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SHARED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    schema = Path(__file__).parent / "schema.sql"
    with _conn() as c:
        c.executescript(schema.read_text())


# ── Vendor registry ───────────────────────────────────────────────────────────

def seed_vendors():
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        for v in VENDORS:
            c.execute(
                """INSERT OR IGNORE INTO vendors (id, name, delivery, cost_usd_annual,
                   sla_latency_minutes, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (v["id"], v["name"], v["delivery"], v["cost_usd_annual"],
                 v["sla_latency_minutes"], v["status"], now, now)
            )
            for ac in v.get("coverage", []):
                c.execute(
                    "INSERT OR IGNORE INTO vendor_coverage (vendor_id, asset_class) VALUES (?,?)",
                    (v["id"], ac)
                )


def get_vendors(status: Optional[str] = None) -> list[dict]:
    with _conn() as c:
        if status:
            rows = c.execute("SELECT * FROM vendors WHERE status = ?", (status,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM vendors").fetchall()
    return [dict(r) for r in rows]


def get_vendor(vendor_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
    return dict(row) if row else None


# ── Dataset catalogue ─────────────────────────────────────────────────────────

def seed_datasets():
    now = datetime.utcnow().isoformat()
    datasets = [
        ("yahoo", "Yahoo Finance Equities", "equity", "15min", "Global large/mid cap", "derived_data", 1),
        ("yahoo", "Yahoo Finance FX", "fx", "15min", "Major + minor pairs", "derived_data", 1),
        ("yahoo", "Yahoo Finance Commodities", "commodity", "15min", "Futures front-month", "derived_data", 0),
        ("yahoo", "Yahoo Finance Volatility", "volatility", "15min", "VIX, VVIX", "derived_data", 1),
        ("fred", "FRED Treasury Yields", "govt_bond", "daily", "US 2Y/10Y/30Y", "redistributable", 1),
        ("fred", "FRED Credit Spreads", "corp_bond", "daily", "ICE BofA IG/HY OAS", "redistributable", 1),
        ("fred", "FRED Risk-Free Rates", "rate", "daily", "SOFR, SONIA, ESTR", "redistributable", 1),
        ("fred", "FRED Macro Indicators", "macro", "daily", "CPI, Unemployment", "redistributable", 0),
        ("ecb", "ECB FX Reference Rates", "fx", "daily", "EUR cross rates", "redistributable", 1),
        ("alpha_vantage", "Alpha Vantage Equities", "equity", "15min", "US equities intraday", "derived_data", 0),
        ("bloomberg", "Bloomberg B-Pipe Equities", "equity", "realtime", "Global equities", "execution_licensed", 1),
        ("bloomberg", "Bloomberg B-Pipe FX", "fx", "realtime", "All pairs", "execution_licensed", 1),
        ("bloomberg", "Bloomberg B-Pipe Credit", "corp_bond", "realtime", "IG/HY bonds", "execution_licensed", 1),
    ]
    with _conn() as c:
        for d in datasets:
            c.execute(
                """INSERT OR IGNORE INTO datasets
                   (vendor_id, name, asset_class, frequency, coverage, licence_type, on_risk_path, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (*d, now)
            )


def get_datasets(vendor_id: Optional[str] = None, asset_class: Optional[str] = None) -> list[dict]:
    query = "SELECT * FROM datasets WHERE 1=1"
    params: list = []
    if vendor_id:
        query += " AND vendor_id = ?"
        params.append(vendor_id)
    if asset_class:
        query += " AND asset_class = ?"
        params.append(asset_class)
    with _conn() as c:
        rows = c.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_risk_path_datasets() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM datasets WHERE on_risk_path = 1").fetchall()
    return [dict(r) for r in rows]


# ── Quality scores ────────────────────────────────────────────────────────────

def save_quality_score(
    vendor_id: str,
    freshness: float,
    completeness: float,
    accuracy: float,
    latency_minutes: Optional[float] = None,
):
    overall = round(0.4 * freshness + 0.3 * completeness + 0.3 * accuracy, 2)
    with _conn() as c:
        c.execute(
            """INSERT INTO quality_scores
               (vendor_id, freshness_score, completeness_score, accuracy_score,
                overall_score, latency_minutes, scored_at)
               VALUES (?,?,?,?,?,?,?)""",
            (vendor_id, freshness, completeness, accuracy, overall,
             latency_minutes, datetime.utcnow().isoformat())
        )
        c.execute(
            "UPDATE datasets SET quality_score = ?, last_scored_at = ? WHERE vendor_id = ?",
            (overall, datetime.utcnow().isoformat(), vendor_id)
        )
    return overall


def get_latest_quality_scores() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT qs.*, v.name as vendor_name FROM quality_scores qs
               JOIN vendors v ON v.id = qs.vendor_id
               WHERE qs.id IN (
                   SELECT MAX(id) FROM quality_scores GROUP BY vendor_id
               )
               ORDER BY qs.overall_score DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_vendor_quality_history(vendor_id: str, limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM quality_scores WHERE vendor_id = ? ORDER BY scored_at DESC LIMIT ?",
            (vendor_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Usage tracking ────────────────────────────────────────────────────────────

def log_usage(vendor_id: str, desk: str, event_type: str = "query",
              dataset_id: Optional[int] = None, records: int = 0):
    with _conn() as c:
        c.execute(
            """INSERT INTO usage_events
               (vendor_id, dataset_id, desk, event_type, records_fetched, timestamp)
               VALUES (?,?,?,?,?,?)""",
            (vendor_id, dataset_id, desk, event_type, records, datetime.utcnow().isoformat())
        )


def get_usage_by_desk() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT desk, vendor_id, COUNT(*) as queries, SUM(records_fetched) as total_records
               FROM usage_events GROUP BY desk, vendor_id ORDER BY queries DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_cost_allocation() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT ue.desk,
                      SUM(v.cost_usd_annual * 1.0 / NULLIF((
                          SELECT COUNT(DISTINCT desk) FROM usage_events WHERE vendor_id = v.id
                      ), 0)) as allocated_cost_usd
               FROM usage_events ue
               JOIN vendors v ON v.id = ue.vendor_id
               GROUP BY ue.desk
               ORDER BY allocated_cost_usd DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


# ── Entitlement checks ────────────────────────────────────────────────────────

def check_entitlement(vendor_id: str, desk: str, licence_type: str,
                      dataset_id: Optional[int] = None) -> tuple[bool, str]:
    from config import DESK_ENTITLEMENTS
    allowed_licences = DESK_ENTITLEMENTS.get(desk, [])
    allowed = licence_type in allowed_licences
    reason = "permitted" if allowed else f"{desk} desk not entitled to {licence_type} data"

    with _conn() as c:
        c.execute(
            """INSERT INTO entitlement_checks
               (vendor_id, dataset_id, desk, licence_type, allowed, reason, timestamp)
               VALUES (?,?,?,?,?,?,?)""",
            (vendor_id, dataset_id, desk, licence_type, int(allowed),
             reason, datetime.utcnow().isoformat())
        )
    return allowed, reason


# ── SLA events ────────────────────────────────────────────────────────────────

def log_sla_event(vendor_id: str, event_type: str,
                  duration_minutes: Optional[float] = None, notes: str = ""):
    with _conn() as c:
        c.execute(
            """INSERT INTO vendor_sla_events
               (vendor_id, event_type, duration_minutes, notes, timestamp)
               VALUES (?,?,?,?,?)""",
            (vendor_id, event_type, duration_minutes, notes, datetime.utcnow().isoformat())
        )


def get_sla_summary(window_days: int = 30) -> list[dict]:
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    with _conn() as c:
        rows = c.execute(
            """SELECT vendor_id,
                      COUNT(*) as total_events,
                      SUM(CASE WHEN event_type = 'outage_start' THEN 1 ELSE 0 END) as outages,
                      SUM(COALESCE(duration_minutes, 0)) as total_outage_minutes
               FROM vendor_sla_events
               WHERE timestamp >= ?
               GROUP BY vendor_id""",
            (cutoff,)
        ).fetchall()
    return [dict(r) for r in rows]
