"""
market-ops — Live Market Data Operations Dashboard
Project 5 of 5 in the GBP fund portfolio ecosystem.

Plan: C:\\Users\\ewanj\\AI Context\\AI Context\\Job-Hunt\\master-plan.md
Shared DB: C:\\Users\\ewanj\\fund.db (read-only — aggregation layer only)

Reads from all 4 upstream projects via shared DB + REST APIs:
  price-recon     → http://localhost:8000  (breaks)
  market-data-hub → http://localhost:8001  (catalogue, vendor SLAs)
  alpha-pipeline  → http://localhost:8002  (NAV, VaR, Greeks, positions)
  data-onboard    → http://localhost:8003  (onboarding pipeline status)

Run modes:
  python main.py           — start dashboard + API (WebSocket live updates)
  python main.py --report  — generate PDF stakeholder report to reports/output/
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _init_db():
    from db.database import init_db
    init_db()
    logger.info("market-ops DB initialised (ops schema only — upstream tables are read-only)")


def serve():
    import uvicorn
    from config import API_PORT, SHARED_DB_PATH, PRICE_RECON_API, ALPHA_PIPELINE_API

    _init_db()

    logger.info(f"market-ops starting on http://localhost:{API_PORT}")
    logger.info(f"Shared DB: {SHARED_DB_PATH}")
    logger.info(f"Upstream APIs: price-recon={PRICE_RECON_API}, alpha-pipeline={ALPHA_PIPELINE_API}")
    logger.info("WebSocket live push: ws://localhost:%s/ws/live (30s interval)", API_PORT)
    logger.info("Dashboard: http://localhost:%s/", API_PORT)

    uvicorn.run("api.routes:app", host="0.0.0.0", port=API_PORT, log_level="info")


def generate_report():
    from config import CRITICAL_BREAKS_THRESHOLD, VAR_95_LIMIT_PCT
    from db.database import (
        get_latest_positions, get_portfolio_snapshot, get_vendor_quality_scores,
        get_active_fx_forwards, get_open_breaks, compute_sla_penalties,
        get_pnl_by_asset_class, get_breaks_summary,
    )
    from reports.pdf import generate_pdf_report

    _init_db()

    logger.info("Aggregating fund state for PDF report…")
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

    data = {
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

    out_path = generate_pdf_report(data)
    logger.info(f"PDF report saved: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="market-ops — operations dashboard")
    parser.add_argument("--report", action="store_true", help="Generate PDF stakeholder report")
    args = parser.parse_args()

    if args.report:
        generate_report()
    else:
        serve()
