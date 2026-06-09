"""FastAPI routes — serves the dashboard and exposes break data to market-ops."""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from db.database import get_open_breaks, get_breaks_summary, resolve_break, get_latest_quotes
from recon.engine import ReconEngine

logger = logging.getLogger(__name__)
app = FastAPI(title="price-recon", version="1.0")

# Serve dashboard
_STATIC = Path(__file__).parent.parent / "dashboard"
if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC / "static")), name="static")


@app.get("/")
def index():
    html = _STATIC / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return {"status": "price-recon running", "docs": "/docs"}


@app.get("/api/breaks")
def breaks():
    """All open (unresolved) price breaks — consumed by market-ops dashboard."""
    return get_open_breaks()


@app.get("/api/breaks/summary")
def breaks_summary():
    """Break counts by asset class and severity."""
    return get_breaks_summary()


@app.get("/api/quotes/{ticker}")
def quotes(ticker: str):
    """Latest price quotes for a ticker across all sources."""
    rows = get_latest_quotes(ticker.upper())
    if not rows:
        raise HTTPException(status_code=404, detail=f"No quotes found for {ticker}")
    return rows


@app.post("/api/breaks/{break_id}/resolve")
def resolve(break_id: int, resolved_by: str = "analyst"):
    resolve_break(break_id, resolved_by)
    return {"status": "resolved", "break_id": break_id}


@app.post("/api/run")
def run_recon():
    """Trigger a fresh reconciliation run. Returns break summary."""
    engine = ReconEngine()
    _, breaks = engine.run()

    from db.database import save_quotes, save_breaks, save_run_summary
    from datetime import datetime
    from config import INSTRUMENTS

    all_quotes = [q for qs in engine._quotes.values() for q in qs]
    save_quotes(all_quotes)
    save_breaks(breaks)
    save_run_summary(
        run_date=datetime.utcnow().strftime("%Y-%m-%d"),
        total=len(INSTRUMENTS),
        breaks=breaks,
        sources=["yahoo", "fred", "ecb"],
    )

    return {
        "total_instruments": len(INSTRUMENTS),
        "total_quotes": len(all_quotes),
        "breaks": len(breaks),
        "critical": sum(1 for b in breaks if b.severity == "CRITICAL"),
        "warning": sum(1 for b in breaks if b.severity == "WARNING"),
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "price-recon"}
