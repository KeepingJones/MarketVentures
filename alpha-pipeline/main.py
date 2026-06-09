"""
alpha-pipeline — Live Multi-Asset Signal & Paper Trading Engine
Project 3 of 5 in the GBP fund portfolio ecosystem.

Plan: C:\\Users\\ewanj\\AI Context\\AI Context\\Job-Hunt\\master-plan.md
Prior work to reuse: C:\\Users\\ewanj\\trading-bot
Shared DB: C:\\Users\\ewanj\\fund.db

PAPER_TRADE_MODE = True. No live capital. Ever.

Run modes:
  python main.py           — single signal + risk check pass
  python main.py --serve   — start API + Streamlit dashboard
  python main.py --loop    — run continuously on schedule
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


def run_once():
    from config import PAPER_TRADE_MODE, SHARED_DB_PATH, FUND_BASE_CURRENCY, FUND_INITIAL_NAV
    from db.database import init_db, get_nav_gbp
    from execution.agent import run_agent
    from risk.var import portfolio_var, stress_test
    from db.database import get_positions, save_snapshot

    logger.info(f"alpha-pipeline — PAPER_TRADE_MODE={PAPER_TRADE_MODE}")
    logger.info(f"Fund: {FUND_INITIAL_NAV:,.0f} {FUND_BASE_CURRENCY} paper NAV")
    logger.info(f"Shared DB: {SHARED_DB_PATH}")
    init_db()

    result = run_agent()
    executed = result.get("executed", [])
    errors = result.get("errors", [])
    logger.info(f"Agent complete — {len(executed)} trades executed, {len(errors)} errors")
    for err in errors:
        logger.warning(f"  {err}")

    positions = get_positions()
    nav = get_nav_gbp() or FUND_INITIAL_NAV
    var_result = portfolio_var(positions) if positions else {}
    stress_result = stress_test(positions) if positions else {}

    save_snapshot(
        nav_gbp=nav,
        peak_nav_gbp=max(nav, FUND_INITIAL_NAV),
        drawdown_pct=max(0, (FUND_INITIAL_NAV - nav) / FUND_INITIAL_NAV * 100),
        var_95=var_result.get("var_95_gbp", 0.0),
        var_99=var_result.get("var_99_gbp", 0.0),
        stress=stress_result.get("stress_results", {}),
        open_breaks=0, critical_breaks=0,
    )
    logger.info(f"NAV: £{nav:,.0f} | VaR 95%: £{var_result.get('var_95_gbp', 0):,.0f}")


def serve():
    import subprocess
    import sys
    from config import API_PORT
    logger.info(f"Starting alpha-pipeline Streamlit dashboard on http://localhost:{API_PORT}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard/app.py",
                    "--server.port", str(API_PORT), "--server.headless", "true"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="alpha-pipeline — paper trading engine")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    if args.serve:
        serve()
    else:
        run_once()
