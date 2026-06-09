"""
FastAPI routes — market-ops unified operations dashboard.

WebSocket at /ws/live pushes aggregated state to dashboard every 30s.
REST endpoints serve the same data for initial page load.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from db.database import (
    get_open_breaks, get_breaks_summary, get_latest_positions,
    get_portfolio_snapshot, get_vendor_quality_scores, get_active_vendors,
    get_active_fx_forwards, get_pnl_by_asset_class, get_nav_history,
    compute_sla_penalties, log_sla_event, save_ops_snapshot,
)
from config import CRITICAL_BREAKS_THRESHOLD, VAR_95_LIMIT_PCT

logger = logging.getLogger(__name__)
app = FastAPI(title="market-ops", version="1.0")

_STATIC = Path(__file__).parent.parent / "dashboard"
if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/")
def index():
    html = _STATIC / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return {"status": "market-ops running", "docs": "/docs"}


# ── Aggregated state ──────────────────────────────────────────────────────────

def _build_state() -> dict:
    snapshot = get_portfolio_snapshot()
    breaks = get_open_breaks()
    positions = get_latest_positions()
    vendors = get_vendor_quality_scores()
    forwards = get_active_fx_forwards()
    pnl_by_ac = get_pnl_by_asset_class()
    penalties = compute_sla_penalties()

    nav = snapshot.get("nav_gbp", 0) if snapshot else 0
    var95 = snapshot.get("var_95_gbp", 0) if snapshot else 0
    critical_breaks = sum(1 for b in breaks if b.get("severity") == "CRITICAL")

    alerts = []
    if critical_breaks > CRITICAL_BREAKS_THRESHOLD:
        alerts.append({"level": "CRITICAL", "message": f"{critical_breaks} critical price breaks open"})
    if nav > 0 and var95 / nav > VAR_95_LIMIT_PCT:
        alerts.append({"level": "WARNING", "message": f"VaR {var95/nav*100:.2f}% exceeds limit {VAR_95_LIMIT_PCT*100:.1f}%"})

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "fund": {
            "nav_gbp": nav,
            "drawdown_pct": snapshot.get("drawdown_pct", 0) if snapshot else 0,
            "var_95_gbp": var95,
            "var_99_gbp": snapshot.get("var_99_gbp", 0) if snapshot else 0,
        },
        "breaks": {
            "total_open": len(breaks),
            "critical": critical_breaks,
            "summary": get_breaks_summary(),
        },
        "positions": positions[:20],
        "pnl_by_asset_class": pnl_by_ac,
        "vendor_health": vendors,
        "fx_forwards": forwards,
        "sla_penalties": penalties,
        "alerts": alerts,
    }


@app.get("/api/state")
def state():
    return _build_state()


@app.get("/api/breaks")
def breaks():
    return get_open_breaks()


@app.get("/api/breaks/summary")
def breaks_summary():
    return get_breaks_summary()


@app.get("/api/positions")
def positions():
    return get_latest_positions()


@app.get("/api/risk")
def risk():
    snapshot = get_portfolio_snapshot()
    return {
        "snapshot": snapshot,
        "pnl_by_asset_class": get_pnl_by_asset_class(),
        "nav_history": get_nav_history(limit=30),
    }


@app.get("/api/vendors")
def vendors():
    return get_vendor_quality_scores()


@app.get("/api/sla")
def sla():
    return compute_sla_penalties()


@app.post("/api/sla/event")
def record_sla_event(vendor_id: str, event_type: str,
                     duration_minutes: Optional[float] = None, notes: str = ""):
    log_sla_event(vendor_id, event_type, duration_minutes, notes=notes)
    return {"status": "logged"}


@app.get("/api/report/data")
def report_data():
    return _build_state()


@app.post("/api/report/generate")
def generate_report():
    from reports.pdf import generate_pdf_report
    data = _build_state()
    path = generate_pdf_report(data)
    return {"status": "generated", "path": str(path)}


# ── WebSocket live push ───────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: str):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await manager.connect(ws)
    logger.info(f"WebSocket connected. Active: {len(manager.connections)}")
    try:
        while True:
            data = _build_state()
            save_ops_snapshot()
            await ws.send_text(json.dumps(data))
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        manager.disconnect(ws)
        logger.info(f"WebSocket disconnected. Active: {len(manager.connections)}")
    except Exception as e:
        manager.disconnect(ws)
        logger.error(f"WebSocket error: {e}")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    snapshot = get_portfolio_snapshot()
    breaks = get_open_breaks()
    vendors = get_active_vendors()
    return {
        "status": "ok",
        "service": "market-ops",
        "upstream_projects": ["price-recon:8000", "market-data-hub:8001",
                               "alpha-pipeline:8002", "data-onboard:8003"],
        "fund_nav_gbp": snapshot.get("nav_gbp", 0) if snapshot else 0,
        "open_breaks": len(breaks),
        "active_vendors": len(vendors),
        "websocket": "/ws/live",
        "endpoints": ["/api/state", "/api/breaks", "/api/positions",
                      "/api/risk", "/api/vendors", "/api/sla",
                      "/api/report/generate"],
    }
