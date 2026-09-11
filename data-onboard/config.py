import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Shared fund database — all 5 projects read/write here ────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
SHARED_DB_PATH = Path(os.getenv("SHARED_DB_PATH", str(ROOT_DIR / "fund.db")))

FRED_API_KEY      = os.getenv("FRED_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "phi3.5")

PAPER_TRADE_MODE = True
API_PORT         = int(os.getenv("API_PORT", "8003"))

# ── OpenFIGI ──────────────────────────────────────────────────────────────────
# Free API — maps vendor identifiers to Bloomberg FIGIs
# Docs: https://www.openfigi.com/api
OPENFIGI_API_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_API_KEY = os.getenv("OPENFIGI_API_KEY", "")   # optional, higher rate limits with key

# ── Pipeline stages ───────────────────────────────────────────────────────────
PIPELINE_STAGES = [
    "intake",           # vendor submits info + sample data
    "gap_analysis",     # compare coverage vs existing catalogue
    "legal_check",      # licence, data usage rights, GDPR
    "tech_spec",        # LLM-generated integration spec
    "qa_period",        # 30-day live quality assessment
    "go_live",          # sign-off and add to market-data-hub catalogue
]

# QA assessment thresholds
QA_MIN_COMPLETENESS_PCT = 95.0   # < 95% complete = fail
QA_MAX_LATENCY_MINUTES  = 30     # > 30 min stale = fail
QA_MIN_ACCURACY_PCT     = 99.0   # > 1% deviation from benchmark = fail

# ── Unstructured alt data ingestion ──────────────────────────────────────────
# Pipeline: PDF (earnings transcript / SEC filing / research report)
#           → LLM extraction → structured JSON signal
ALT_DATA_INPUT_DIR  = "./alt_data/input"    # drop PDFs here
ALT_DATA_OUTPUT_DIR = "./alt_data/output"   # structured JSON signals written here

# Expected output schema per document
ALT_DATA_SIGNAL_SCHEMA = {
    "ticker":            str,   # primary ticker mentioned (e.g. "AAPL")
    "sentiment":         str,   # "bullish" | "bearish" | "neutral"
    "revenue_guidance":  str,   # "raised" | "lowered" | "maintained" | "N/A"
    "earnings_surprise": str,   # "beat" | "miss" | "in-line" | "N/A"
    "key_risks":         list,  # list of risk factors cited
    "source_type":       str,   # "earnings_transcript" | "sec_filing" | "research_report"
    "confidence":        float, # LLM self-reported confidence 0.0–1.0
}

# LLM prompt for extraction (Ollama)
ALT_DATA_EXTRACTION_PROMPT = """You are a financial analyst. Extract structured information from this document.
Return ONLY valid JSON matching this exact schema: {schema}
Do not include explanation or markdown. Document text: {text}"""
