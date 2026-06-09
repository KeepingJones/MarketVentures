"""
data-onboard — Vendor Data Onboarding & Integration Workflow
Project 4 of 5 in the GBP fund portfolio ecosystem.

Plan: C:\\Users\\ewanj\\AI Context\\AI Context\\Job-Hunt\\master-plan.md
Shared DB: C:\\Users\\ewanj\\fund.db

Run modes:
  python main.py               — start API + status dashboard
  python main.py --intake      — run intake form for new vendor
  python main.py --qa VENDOR   — run 30-day QA assessment for vendor
"""
import argparse
import logging
import logging.handlers
import sys
from pathlib import Path


def _setup_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    app_file = logging.handlers.RotatingFileHandler(
        log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    app_file.setFormatter(fmt)

    err_file = logging.handlers.RotatingFileHandler(
        log_dir / "error.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    err_file.setLevel(logging.ERROR)
    err_file.setFormatter(fmt)

    logging.basicConfig(level=logging.INFO, handlers=[console, app_file, err_file])

    def _excepthook(exc_type, exc_value, exc_tb):
        if not issubclass(exc_type, KeyboardInterrupt):
            logging.getLogger("data-onboard").critical(
                "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
            )
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _excepthook


_setup_logging()
logger = logging.getLogger(__name__)


def intake():
    from config import PIPELINE_STAGES, SHARED_DB_PATH, PAPER_TRADE_MODE
    from db.database import init_db
    from pipeline.intake import process_intake

    logger.info(f"data-onboard — PAPER_TRADE_MODE={PAPER_TRADE_MODE}")
    logger.info(f"Shared DB: {SHARED_DB_PATH}")
    logger.info(f"Pipeline stages: {PIPELINE_STAGES}")
    init_db()

    # Demo intake for a sample vendor
    form = {
        "vendor_name": "Refinitiv Elektron",
        "vendor_id": "refinitiv_demo",
        "contact_email": "integration@refinitiv.com",
        "api_endpoint": "https://api.refinitiv.com/data/v1",
        "asset_classes": ["equity", "fx", "govt_bond", "corp_bond", "option"],
    }
    result = process_intake(form, sample_tickers=["AAPL", "MSFT", "GBPUSD=X"])
    logger.info(f"Intake result: {result['status']}")
    if result.get("gap_analysis"):
        gap = result["gap_analysis"]
        logger.info(f"  New coverage: {gap.get('new_coverage', [])}")
        logger.info(f"  Duplicates: {gap.get('duplicates', [])}")


def qa(vendor_id: str):
    from config import QA_MIN_COMPLETENESS_PCT, QA_MAX_LATENCY_MINUTES
    from db.database import init_db, get_vendor
    from qa.assessor import simulate_qa_assessment

    init_db()
    vendor = get_vendor(vendor_id)
    if not vendor:
        logger.error(f"Vendor {vendor_id} not found in pipeline")
        return

    logger.info(f"Running QA assessment for vendor: {vendor_id} ({vendor['vendor_name']})")
    logger.info(f"Thresholds — completeness: {QA_MIN_COMPLETENESS_PCT}%, latency: {QA_MAX_LATENCY_MINUTES}min")
    result = simulate_qa_assessment(vendor_id, vendor["vendor_name"])
    logger.info(f"QA {'PASSED' if result['passed'] else 'FAILED'}: "
                f"completeness={result['completeness_pct']:.1f}%, "
                f"latency={result['latency_minutes']:.1f}min, "
                f"accuracy={result['accuracy_pct']:.1f}%")


def serve():
    import uvicorn
    from config import API_PORT, SHARED_DB_PATH
    from db.database import init_db
    logger.info(f"Starting data-onboard API on http://localhost:{API_PORT}")
    logger.info(f"Shared DB: {SHARED_DB_PATH}")
    init_db()
    uvicorn.run("api.routes:app", host="0.0.0.0", port=API_PORT, reload=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="data-onboard — vendor onboarding pipeline")
    parser.add_argument("--intake", action="store_true")
    parser.add_argument("--qa", metavar="VENDOR_ID")
    args = parser.parse_args()

    if args.intake:
        intake()
    elif args.qa:
        qa(args.qa)
    else:
        serve()
