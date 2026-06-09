import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Shared fund database — all 5 projects read/write here ────────────────────
# market-ops is READ ONLY from this DB — it aggregates, never writes
SHARED_DB_PATH = Path(os.getenv("SHARED_DB_PATH", r"C:\Users\ewanj\MarketVentures\fund.db"))

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3.5")

PAPER_TRADE_MODE = True
API_PORT         = int(os.getenv("API_PORT", "8004"))

# ── Vault / plan reference ────────────────────────────────────────────────────
VAULT_PLAN = r"C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md"

# ── Upstream project API endpoints ───────────────────────────────────────────
# market-ops aggregates data from all other projects
PRICE_RECON_API    = os.getenv("PRICE_RECON_API",    "http://localhost:8000")
MARKET_DATA_HUB_API = os.getenv("MARKET_DATA_HUB_API", "http://localhost:8001")
ALPHA_PIPELINE_API = os.getenv("ALPHA_PIPELINE_API", "http://localhost:8002")
DATA_ONBOARD_API   = os.getenv("DATA_ONBOARD_API",   "http://localhost:8003")

# ── Report settings ───────────────────────────────────────────────────────────
REPORT_OUTPUT_DIR  = Path(os.getenv("REPORT_OUTPUT_DIR", "./reports/output"))
FUND_BASE_CURRENCY = "GBP"

# ── Risk limits for breach alerts ─────────────────────────────────────────────
VAR_95_LIMIT_PCT   = 0.03   # alert if 1-day VaR (95%) > 3% NAV
CRITICAL_BREAKS_THRESHOLD = 5  # alert if > 5 critical price breaks open

# ── SLA penalty engine ────────────────────────────────────────────────────────
# When a vendor breaches their contractual SLA, calculate the commercial rebate.
# SLA definitions per vendor — override per vendor in VENDORS config
DEFAULT_SLA_UPTIME_PCT    = 99.9   # contractual uptime guarantee
DEFAULT_LATENCY_SLA_MIN   = 15     # max acceptable feed latency in minutes

# Penalty calculation: % of monthly vendor fee per hour of SLA breach
# e.g. vendor charges $2,000/month, breaches 5 hours → 5 * 0.01 * $2,000 = $100 rebate
SLA_PENALTY_RATE_PER_HOUR = 0.01   # 1% of monthly cost per hour of breach

# Outage tracking window for monthly SLA calculation
SLA_TRACKING_WINDOW_DAYS  = 30

REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
