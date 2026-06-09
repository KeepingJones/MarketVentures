import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import SHARED_DB_PATH


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SHARED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    schema = Path(__file__).parent / "schema.sql"
    with _conn() as c:
        c.executescript(schema.read_text())


# ── Vendor pipeline ───────────────────────────────────────────────────────────

def create_vendor(vendor_name: str, vendor_id: str, contact_email: str,
                  api_endpoint: str, asset_classes: list[str]) -> int:
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO vendor_pipeline
               (vendor_name, vendor_id, contact_email, api_endpoint,
                claimed_asset_classes, current_stage, stage_status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (vendor_name, vendor_id, contact_email, api_endpoint,
             json.dumps(asset_classes), "intake", "in_progress", now, now)
        )
        row = c.execute("SELECT id FROM vendor_pipeline WHERE vendor_id = ?", (vendor_id,)).fetchone()
    return row["id"] if row else 0


def get_vendor(vendor_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM vendor_pipeline WHERE vendor_id = ?", (vendor_id,)).fetchone()
    return dict(row) if row else None


def get_all_vendors() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM vendor_pipeline ORDER BY updated_at DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["claimed_asset_classes"] = json.loads(d.get("claimed_asset_classes", "[]"))
        result.append(d)
    return result


def advance_stage(vendor_id: str, new_stage: str, status: str = "pass", notes: str = "") -> bool:
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE vendor_pipeline SET current_stage=?, stage_status=?, updated_at=? WHERE vendor_id=?",
            (new_stage, status, now, vendor_id)
        )
        c.execute(
            """INSERT INTO pipeline_stage_log (vendor_id, stage, status, notes, timestamp)
               VALUES (?,?,?,?,?)""",
            (vendor_id, new_stage, status, notes, now)
        )
    return True


def get_stage_log(vendor_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM pipeline_stage_log WHERE vendor_id = ? ORDER BY timestamp",
            (vendor_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── QA assessments ────────────────────────────────────────────────────────────

def save_qa_assessment(vendor_id: str, completeness: float,
                       latency_minutes: float, accuracy: float,
                       notes: str = "") -> bool:
    from config import QA_MIN_COMPLETENESS_PCT, QA_MAX_LATENCY_MINUTES, QA_MIN_ACCURACY_PCT
    passed = (completeness >= QA_MIN_COMPLETENESS_PCT and
              latency_minutes <= QA_MAX_LATENCY_MINUTES and
              accuracy >= QA_MIN_ACCURACY_PCT)
    with _conn() as c:
        c.execute(
            """INSERT INTO qa_assessments
               (vendor_id, completeness_pct, latency_minutes, accuracy_pct, overall_pass, notes, assessed_at)
               VALUES (?,?,?,?,?,?,?)""",
            (vendor_id, completeness, latency_minutes, accuracy,
             int(passed), notes, datetime.utcnow().isoformat())
        )
    return passed


def get_qa_assessments(vendor_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM qa_assessments WHERE vendor_id = ? ORDER BY assessed_at DESC",
            (vendor_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── FIGI mappings ─────────────────────────────────────────────────────────────

def save_figi_mapping(vendor_id: str, vendor_ticker: str, figi: Optional[str],
                      security_type: str, market_sector: str, match_status: str):
    with _conn() as c:
        c.execute(
            """INSERT INTO figi_mappings
               (vendor_id, vendor_ticker, figi, security_type, market_sector, match_status, mapped_at)
               VALUES (?,?,?,?,?,?,?)""",
            (vendor_id, vendor_ticker, figi, security_type, market_sector,
             match_status, datetime.utcnow().isoformat())
        )


def get_figi_mappings(vendor_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM figi_mappings WHERE vendor_id = ?", (vendor_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Coverage gaps ─────────────────────────────────────────────────────────────

def save_coverage_gap(vendor_id: str, asset_class: str, gap_type: str, notes: str = ""):
    with _conn() as c:
        c.execute(
            """INSERT INTO coverage_gaps
               (vendor_id, asset_class, gap_type, notes, analysed_at)
               VALUES (?,?,?,?,?)""",
            (vendor_id, asset_class, gap_type, notes, datetime.utcnow().isoformat())
        )


def get_coverage_gaps(vendor_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM coverage_gaps WHERE vendor_id = ?", (vendor_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Alt data signals ──────────────────────────────────────────────────────────

def save_alt_signal(source_file: str, ticker: Optional[str], sentiment: str,
                    revenue_guidance: str, earnings_surprise: str,
                    key_risks: list[str], source_type: str, confidence: float):
    with _conn() as c:
        c.execute(
            """INSERT INTO alt_data_signals
               (source_file, ticker, sentiment, revenue_guidance, earnings_surprise,
                key_risks, source_type, confidence, extracted_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (source_file, ticker, sentiment, revenue_guidance, earnings_surprise,
             json.dumps(key_risks), source_type, confidence,
             datetime.utcnow().isoformat())
        )


def get_alt_signals(limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM alt_data_signals ORDER BY extracted_at DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["key_risks"] = json.loads(d.get("key_risks", "[]"))
        result.append(d)
    return result
