"""
price-recon entry point.

Run modes:
  python main.py          — single reconciliation run, generate Excel report
  python main.py --serve  — start FastAPI server (dashboard + API)
  python main.py --schedule — run every day at 17:00 London time
"""
import argparse
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_once():
    from db.database import init_db, save_quotes, save_breaks, save_run_summary
    from recon.engine import ReconEngine
    from recon.escalation import log_escalations
    from reports.excel import generate_eod_report
    from config import INSTRUMENTS, PAPER_TRADE_MODE

    logger.info(f"price-recon - PAPER_TRADE_MODE={PAPER_TRADE_MODE}")
    init_db()

    engine = ReconEngine()
    quotes, breaks = engine.run()

    all_quotes = [q for qs in quotes.values() for q in qs]
    save_quotes(all_quotes)
    save_breaks(breaks)
    save_run_summary(
        run_date=datetime.utcnow().strftime("%Y-%m-%d"),
        total=len(INSTRUMENTS),
        breaks=breaks,
        sources=["yahoo", "fred", "ecb"],
    )

    escalations = log_escalations(breaks)

    report_path = generate_eod_report(breaks, all_quotes)
    logger.info(f"Excel report saved: {report_path}")

    print(f"\n{'='*60}")
    print(f"  price-recon EOD run - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")
    print(f"  Instruments checked:  {len(INSTRUMENTS)}")
    print(f"  Total quotes fetched: {len(all_quotes)}")
    print(f"  Price breaks found:   {len(breaks)}")
    print(f"    Critical:           {sum(1 for b in breaks if b.severity == 'CRITICAL')}")
    print(f"    Warning:            {sum(1 for b in breaks if b.severity == 'WARNING')}")
    print(f"  Escalations raised:   {len(escalations)}")
    print(f"  Report:               {report_path.name}")
    print(f"{'='*60}\n")

    return breaks


def serve():
    import uvicorn
    from api.routes import app
    logger.info("Starting price-recon API server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def schedule_daily():
    import schedule
    import time

    logger.info("Scheduling daily reconciliation at 17:00 UTC")
    schedule.every().day.at("17:00").do(run_once)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="price-recon — EOD pricing reconciliation")
    parser.add_argument("--serve", action="store_true", help="Start API + dashboard server")
    parser.add_argument("--schedule", action="store_true", help="Run on daily schedule at 17:00 UTC")
    args = parser.parse_args()

    if args.serve:
        serve()
    elif args.schedule:
        schedule_daily()
    else:
        run_once()
