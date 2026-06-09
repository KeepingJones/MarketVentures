import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Shared fund database — all 5 projects read/write here ────────────────────
SHARED_DB_PATH = Path(os.getenv("SHARED_DB_PATH", r"C:\Users\ewanj\MarketVentures\fund.db"))

FRED_API_KEY      = os.getenv("FRED_API_KEY", "")
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY", "PKSTJB2CUNA2PKJGLOIZHMF6HZ")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "HqGchrqnzruyQztbU7EFZtW23RQkfsahwFz3A2iCMg71")
ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "phi3.5")

PAPER_TRADE_MODE = True  # NEVER change — no live capital
API_PORT         = int(os.getenv("API_PORT", "8002"))

# ── Vault / plan reference ────────────────────────────────────────────────────
VAULT_PLAN    = r"C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md"
TRADING_BOT   = r"C:\Users\ewanj\trading-bot"   # prior work to reuse

# ── Fund parameters ───────────────────────────────────────────────────────────
FUND_BASE_CURRENCY  = "GBP"
FUND_INITIAL_NAV    = 1_000_000.0   # £1M paper fund
FX_HEDGE_RATIO      = 1.0           # 100% hedge on non-GBP exposure

# ── Risk limits ───────────────────────────────────────────────────────────────
MAX_POSITION_PCT        = 0.10   # max 10% NAV in any single name
MAX_DAILY_LOSS_PCT      = 0.02   # halt trading if daily P&L < -2%
MAX_POSITION_ADV_PCT    = 0.10   # max 10% of 30-day ADV per position
VAR_95_LIMIT_PCT        = 0.03   # 1-day VaR (95%) < 3% NAV
VAR_LOOKBACK_DAYS       = 252

STRESS_SCENARIOS = {
    "GFC_2008":        {"equity": -0.40, "credit": -0.30, "vol_spike": 0.20},
    "COVID_2020":      {"equity": -0.35, "credit": -0.20, "vol_spike": 0.25},
    "RATE_SHOCK_2022": {"equity": -0.20, "govt_bond": -0.15, "credit": -0.10},
    "GBP_CRISIS_1992": {"fx_gbp": -0.15, "equity": -0.10},
}

# ── FX forward pricing (interest rate parity) ─────────────────────────────────
FRED_RATE_SERIES = {
    "USD": "DFF",               # SOFR proxy (Fed Funds effective rate)
    "GBP": "IUDSOIA",           # SONIA
    "EUR": "ECBESTRVOLWGTTRMD", # €STR
    "JPY": "IRSTCI01JPM156N",   # JP overnight call rate
}

# ── Universe of instruments to trade ─────────────────────────────────────────
# Pulled from price-recon config — same instruments, consistent universe
PRICE_RECON_CONFIG = r"C:\Users\ewanj\MarketVentures\price-recon\config.py"
