"""
market-data-hub — Market Data Management Platform
Project 2 of 5 in the GBP fund portfolio ecosystem.

Shared DB: ./fund.db

Run modes:
  python main.py          — seed vendors + catalogue, start API
  python main.py --score  — run live quality scoring pass on all vendors
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
            logging.getLogger("market-data-hub").critical(
                "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
            )
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _excepthook


_setup_logging()
logger = logging.getLogger(__name__)


def seed():
    from config import VENDORS, SHARED_DB_PATH, PAPER_TRADE_MODE
    from db.database import init_db, seed_vendors, seed_datasets
    logger.info(f"market-data-hub starting — PAPER_TRADE_MODE={PAPER_TRADE_MODE}")
    logger.info(f"Shared DB: {SHARED_DB_PATH}")
    init_db()
    seed_vendors()
    seed_datasets()
    logger.info(f"Seeded {len(VENDORS)} vendors + datasets into catalogue")


def score():
    from data.quality_scorer import run_all_scoring
    logger.info("Running quality scoring pass on all active vendors")
    results = run_all_scoring()
    for r in results:
        logger.info(f"  {r['vendor_id']}: {r.get('overall', 0):.1f}/100")


def serve():
    import uvicorn
    from config import API_PORT
    logger.info(f"Starting market-data-hub API on http://localhost:{API_PORT}")
    uvicorn.run("api.routes:app", host="0.0.0.0", port=API_PORT, reload=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="market-data-hub — data catalogue platform")
    parser.add_argument("--score", action="store_true", help="Run quality scoring pass")
    args = parser.parse_args()

    if args.score:
        score()
    else:
        seed()
        serve()
