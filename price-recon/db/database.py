import json
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH
from data.models import PriceQuote, PriceBreak, FXRate


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    schema = Path(__file__).parent / "schema.sql"
    with _conn() as c:
        c.executescript(schema.read_text())


# ── Price quotes ──────────────────────────────────────────────────────────────

def save_quote(q: PriceQuote):
    with _conn() as c:
        c.execute(
            """INSERT INTO price_quotes
               (ticker, source, asset_class, currency, price, bid, ask, volume, timestamp, is_stale)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (q.ticker, q.source, q.asset_class, q.currency, q.price,
             q.bid, q.ask, q.volume, q.timestamp.isoformat(), int(q.is_stale))
        )


def save_quotes(quotes: list[PriceQuote]):
    with _conn() as c:
        c.executemany(
            """INSERT INTO price_quotes
               (ticker, source, asset_class, currency, price, bid, ask, volume, timestamp, is_stale)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [(q.ticker, q.source, q.asset_class, q.currency, q.price,
              q.bid, q.ask, q.volume, q.timestamp.isoformat(), int(q.is_stale))
             for q in quotes]
        )


def get_latest_quotes(ticker: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT * FROM price_quotes WHERE ticker = ?
               ORDER BY timestamp DESC LIMIT 10""",
            (ticker,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Breaks ────────────────────────────────────────────────────────────────────

def save_break(b: PriceBreak):
    with _conn() as c:
        c.execute(
            """INSERT INTO price_breaks
               (ticker, asset_class, source_a, source_b, price_a, price_b,
                diff_pct, tolerance_pct, break_cause, severity, timestamp, resolved)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (b.ticker, b.asset_class, b.source_a, b.source_b, b.price_a, b.price_b,
             b.diff_pct, b.tolerance_pct, b.break_cause, b.severity,
             b.timestamp.isoformat(), int(b.resolved))
        )


def save_breaks(breaks: list[PriceBreak]):
    with _conn() as c:
        c.executemany(
            """INSERT INTO price_breaks
               (ticker, asset_class, source_a, source_b, price_a, price_b,
                diff_pct, tolerance_pct, break_cause, severity, timestamp, resolved)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(b.ticker, b.asset_class, b.source_a, b.source_b, b.price_a, b.price_b,
              b.diff_pct, b.tolerance_pct, b.break_cause, b.severity,
              b.timestamp.isoformat(), int(b.resolved))
             for b in breaks]
        )


def get_open_breaks() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM price_breaks WHERE resolved = 0 ORDER BY severity, timestamp DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def resolve_break(break_id: int, resolved_by: str = "system"):
    with _conn() as c:
        c.execute(
            "UPDATE price_breaks SET resolved = 1, resolved_at = ?, resolved_by = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), resolved_by, break_id)
        )


def get_breaks_summary() -> dict:
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


# ── FX rates ──────────────────────────────────────────────────────────────────

def save_fx_rate(fx: FXRate):
    with _conn() as c:
        c.execute(
            "INSERT INTO fx_rates (pair, rate, source, timestamp) VALUES (?,?,?,?)",
            (fx.pair, fx.rate, fx.source, fx.timestamp.isoformat())
        )


def get_latest_fx_rate(pair: str) -> float | None:
    with _conn() as c:
        row = c.execute(
            "SELECT rate FROM fx_rates WHERE pair = ? ORDER BY timestamp DESC LIMIT 1",
            (pair,)
        ).fetchone()
    return float(row["rate"]) if row else None


# ── Run summary ───────────────────────────────────────────────────────────────

def save_run_summary(run_date: str, total: int, breaks: list[PriceBreak], sources: list[str]):
    critical = sum(1 for b in breaks if b.severity == "CRITICAL")
    warning = sum(1 for b in breaks if b.severity == "WARNING")
    info = sum(1 for b in breaks if b.severity == "INFO")
    with _conn() as c:
        c.execute(
            """INSERT INTO recon_runs
               (run_date, total_instruments, total_breaks, critical_breaks,
                warning_breaks, info_breaks, sources_used, timestamp)
               VALUES (?,?,?,?,?,?,?,?)""",
            (run_date, total, len(breaks), critical, warning, info,
             json.dumps(sources), datetime.utcnow().isoformat())
        )
