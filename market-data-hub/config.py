import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Shared fund database — all 5 projects read/write here ────────────────────
SHARED_DB_PATH = Path(os.getenv("SHARED_DB_PATH", r"C:\Users\ewanj\MarketVentures\fund.db"))

FRED_API_KEY     = os.getenv("FRED_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "phi3.5")

PAPER_TRADE_MODE = True  # Data catalogue only — no order routing
API_PORT         = int(os.getenv("API_PORT", "8001"))

# ── Vault / plan reference ────────────────────────────────────────────────────
VAULT_PLAN   = r"C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md"
PORTFOLIO_PLAN = r"C:\Users\ewanj\AI Context\AI Context\Job-Hunt\portfolio-plan.md"

# ── Vendor registry ───────────────────────────────────────────────────────────
# Each entry defines a catalogued data vendor. Status: active | inactive | onboarding
VENDORS = [
    {
        "id": "yahoo",
        "name": "Yahoo Finance",
        "delivery": "API (yfinance)",
        "cost_usd_annual": 0,
        "sla_latency_minutes": 15,
        "coverage": ["equity", "fx", "commodity", "option", "volatility", "govt_bond"],
        "status": "active",
    },
    {
        "id": "fred",
        "name": "FRED (St. Louis Fed)",
        "delivery": "REST API (fredapi)",
        "cost_usd_annual": 0,
        "sla_latency_minutes": 1440,  # daily
        "coverage": ["rate", "macro", "govt_bond", "corp_bond", "credit_spread"],
        "status": "active",
    },
    {
        "id": "ecb",
        "name": "European Central Bank",
        "delivery": "REST API",
        "cost_usd_annual": 0,
        "sla_latency_minutes": 1440,
        "coverage": ["fx"],
        "status": "active",
    },
    {
        "id": "alpha_vantage",
        "name": "Alpha Vantage",
        "delivery": "REST API",
        "cost_usd_annual": 0,
        "sla_latency_minutes": 15,
        "coverage": ["equity", "fx", "commodity", "macro"],
        "status": "active",
    },
    {
        "id": "bloomberg",
        "name": "Bloomberg B-Pipe",
        "delivery": "Server API (B-Pipe/BLPAPI)",
        "cost_usd_annual": 24000,
        "sla_latency_minutes": 0,  # real-time
        "coverage": ["equity", "fx", "govt_bond", "corp_bond", "credit", "commodity", "option"],
        "status": "inactive",  # mock schema only — no free API
    },
]

# ── Desk usage tracking ───────────────────────────────────────────────────────
DESKS = ["equity", "fx", "rates", "credit", "quant", "risk", "operations"]

# ── Data entitlements — licence types ────────────────────────────────────────
# Tags applied to every dataset in the catalogue.
# When a desk requests data, the entitlement engine checks their permissions.
LICENCE_TYPES = [
    "display_only",         # human viewing only — cannot feed automated systems
    "derived_data",         # can generate derived signals, cannot redistribute raw
    "execution_licensed",   # can feed live trading algorithms
    "internal_only",        # cannot be shared with offshore / third parties
    "redistributable",      # can be sent to external counterparties
]

# Desk → allowed licence types (which data a desk is entitled to consume)
DESK_ENTITLEMENTS = {
    "equity":     ["display_only", "derived_data", "execution_licensed"],
    "fx":         ["display_only", "derived_data", "execution_licensed"],
    "rates":      ["display_only", "derived_data", "execution_licensed"],
    "credit":     ["display_only", "derived_data"],
    "quant":      ["display_only", "derived_data", "execution_licensed"],
    "risk":       ["display_only", "derived_data"],
    "operations": ["display_only"],
}

# ── RAG — vendor contracts ────────────────────────────────────────────────────
CONTRACTS_DIR   = "./contracts"   # place dummy MSA PDFs here
CONTRACTS_INDEX = "./db/contracts_index.json"  # chunked text index
RAG_CHUNK_SIZE  = 500   # characters per chunk
RAG_TOP_K       = 5     # top-k chunks to pass to LLM for each query
