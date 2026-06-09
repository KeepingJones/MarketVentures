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


# ── Positions ─────────────────────────────────────────────────────────────────

def upsert_position(ticker: str, asset_class: str, currency: str,
                    quantity: float, avg_entry_price: float,
                    current_price: float, market_value_gbp: float,
                    unrealised_pnl_gbp: float, liquidity_tier: str,
                    fx_hedge_ratio: float = 1.0):
    now = datetime.utcnow().isoformat()
    with _conn() as c:
        existing = c.execute("SELECT id FROM positions WHERE ticker = ?", (ticker,)).fetchone()
        if existing:
            c.execute(
                """UPDATE positions SET quantity=?, avg_entry_price=?, current_price=?,
                   market_value_gbp=?, unrealised_pnl_gbp=?, liquidity_tier=?,
                   fx_hedge_ratio=?, updated_at=? WHERE ticker=?""",
                (quantity, avg_entry_price, current_price, market_value_gbp,
                 unrealised_pnl_gbp, liquidity_tier, fx_hedge_ratio, now, ticker)
            )
        else:
            c.execute(
                """INSERT INTO positions
                   (ticker, asset_class, currency, quantity, avg_entry_price, current_price,
                    market_value_gbp, unrealised_pnl_gbp, liquidity_tier, fx_hedge_ratio, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ticker, asset_class, currency, quantity, avg_entry_price, current_price,
                 market_value_gbp, unrealised_pnl_gbp, liquidity_tier, fx_hedge_ratio, now)
            )


def get_positions() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM positions ORDER BY market_value_gbp DESC").fetchall()
    return [dict(r) for r in rows]


def get_nav_gbp() -> float:
    with _conn() as c:
        row = c.execute("SELECT SUM(market_value_gbp) as nav FROM positions").fetchone()
    return float(row["nav"] or 0.0)


# ── Trades ────────────────────────────────────────────────────────────────────

def save_trade(ticker: str, asset_class: str, direction: str,
               quantity: float, price: float, currency: str,
               price_gbp: float, signal_source: str, broker: str,
               alpaca_order_id: Optional[str] = None):
    value_gbp = quantity * price_gbp
    with _conn() as c:
        c.execute(
            """INSERT INTO trades
               (ticker, asset_class, direction, quantity, price, currency,
                price_gbp, value_gbp, signal_source, broker, alpaca_order_id, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ticker, asset_class, direction, quantity, price, currency,
             price_gbp, value_gbp, signal_source, broker,
             alpaca_order_id, datetime.utcnow().isoformat())
        )


def get_trades(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── Portfolio snapshots ───────────────────────────────────────────────────────

def save_snapshot(nav_gbp: float, peak_nav_gbp: float, drawdown_pct: float,
                  var_95: float, var_99: float,
                  stress: dict, open_breaks: int, critical_breaks: int):
    with _conn() as c:
        c.execute(
            """INSERT INTO portfolio_snapshots
               (nav_gbp, peak_nav_gbp, drawdown_pct, var_95_gbp, var_99_gbp,
                stress_gfc_gbp, stress_covid_gbp, stress_rate_shock_gbp,
                open_breaks, critical_breaks, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (nav_gbp, peak_nav_gbp, drawdown_pct, var_95, var_99,
             stress.get("GFC_2008", 0), stress.get("COVID_2020", 0),
             stress.get("RATE_SHOCK_2022", 0),
             open_breaks, critical_breaks, datetime.utcnow().isoformat())
        )


def get_latest_snapshot() -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_snapshot_history(limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Signals ───────────────────────────────────────────────────────────────────

def save_signal(ticker: str, asset_class: str, signal_type: str,
                direction: str, confidence: float, price: float,
                var_impact_gbp: float, liquidity_tier: str,
                quality_gate_passed: bool = True):
    with _conn() as c:
        c.execute(
            """INSERT INTO signals
               (ticker, asset_class, signal_type, direction, confidence, price,
                var_impact_gbp, liquidity_tier, quality_gate_passed, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ticker, asset_class, signal_type, direction, confidence, price,
             var_impact_gbp, liquidity_tier, int(quality_gate_passed),
             datetime.utcnow().isoformat())
        )


def get_signals(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── FX forwards ───────────────────────────────────────────────────────────────

def save_fx_forward(pair: str, notional_gbp: float, spot_rate: float,
                    forward_rate: float, tenor_days: int,
                    domestic_rate: float, foreign_rate: float):
    from datetime import timedelta
    now = datetime.utcnow()
    with _conn() as c:
        c.execute(
            """INSERT INTO fx_forwards
               (pair, notional_gbp, spot_rate, forward_rate, tenor_days,
                domestic_rate, foreign_rate, created_at, expires_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (pair, notional_gbp, spot_rate, forward_rate, tenor_days,
             domestic_rate, foreign_rate,
             now.isoformat(), (now + timedelta(days=tenor_days)).isoformat())
        )


def get_active_forwards() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM fx_forwards WHERE expires_at > ? ORDER BY created_at DESC",
            (datetime.utcnow().isoformat(),)
        ).fetchall()
    return [dict(r) for r in rows]
