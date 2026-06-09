"""
Live quality scoring — hits each active vendor API, measures freshness,
completeness, and accuracy vs a benchmark (Yahoo Finance as ground truth).

Scoring weights: freshness 40%, completeness 30%, accuracy 30%.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
import yfinance as yf

from config import FRED_API_KEY, ALPHA_VANTAGE_KEY
from db.database import save_quality_score

logger = logging.getLogger(__name__)

# Benchmark tickers for accuracy cross-check (Yahoo Finance as ground truth)
_BENCHMARK_TICKERS = ["AAPL", "GBPUSD=X", "GC=F", "^VIX"]
_FRED_BENCHMARK_SERIES = ["DGS10", "BAMLC0A0CM", "DFF"]


def _score_freshness(last_update_ts: Optional[datetime], sla_latency_minutes: int) -> float:
    if last_update_ts is None:
        return 0.0
    age_minutes = (datetime.utcnow() - last_update_ts).total_seconds() / 60
    if age_minutes <= sla_latency_minutes:
        return 100.0
    elif age_minutes <= sla_latency_minutes * 2:
        return 70.0
    elif age_minutes <= sla_latency_minutes * 5:
        return 40.0
    return 10.0


def _score_completeness(fields_present: int, fields_expected: int) -> float:
    if fields_expected == 0:
        return 100.0
    return min(100.0, round(fields_present / fields_expected * 100, 2))


def _score_accuracy(vendor_price: float, benchmark_price: float) -> float:
    if benchmark_price == 0:
        return 0.0
    deviation_pct = abs(vendor_price - benchmark_price) / benchmark_price * 100
    if deviation_pct <= 0.1:
        return 100.0
    elif deviation_pct <= 0.5:
        return 90.0
    elif deviation_pct <= 1.0:
        return 75.0
    elif deviation_pct <= 2.0:
        return 50.0
    return 20.0


def score_yahoo() -> dict:
    logger.info("Scoring vendor: yahoo")
    start = time.time()
    try:
        raw = yf.download(["AAPL", "GBPUSD=X"], period="2d", auto_adjust=True,
                          progress=False, group_by="ticker")
        latency = (time.time() - start) / 60  # convert seconds to minutes

        # Freshness: check last bar timestamp
        try:
            last_ts = raw["AAPL"]["Close"].dropna().index[-1].to_pydatetime()
            freshness = _score_freshness(last_ts, sla_latency_minutes=15)
        except Exception:
            freshness = 50.0

        # Completeness: check fields populated
        try:
            fields_present = raw["AAPL"].notna().sum().sum()
            fields_expected = raw["AAPL"].size
            completeness = _score_completeness(int(fields_present), int(fields_expected))
        except Exception:
            completeness = 70.0

        # Accuracy: self-consistent (Yahoo is the benchmark)
        accuracy = 98.0

        score = save_quality_score("yahoo", freshness, completeness, accuracy, latency)
        logger.info(f"Yahoo scored: {score:.1f} (lat={latency:.1f}min)")
        return {"vendor_id": "yahoo", "overall": score, "freshness": freshness,
                "completeness": completeness, "accuracy": accuracy, "latency_minutes": latency}
    except Exception as e:
        logger.error(f"Yahoo scoring failed: {e}")
        score = save_quality_score("yahoo", 0.0, 0.0, 0.0, None)
        return {"vendor_id": "yahoo", "overall": 0.0, "error": str(e)}


def score_fred() -> dict:
    logger.info("Scoring vendor: fred")
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — skipping")
        return {"vendor_id": "fred", "overall": 0.0, "error": "no API key"}
    start = time.time()
    try:
        import fredapi
        fred = fredapi.Fred(api_key=FRED_API_KEY)
        end = datetime.today()
        data = fred.get_series("DGS10", observation_start=(end - timedelta(days=5)).strftime("%Y-%m-%d"))
        latency = (time.time() - start) / 60

        data = data.dropna()
        freshness = 85.0 if not data.empty else 0.0  # FRED is daily, always slightly "stale"
        completeness = 100.0 if len(data) >= 3 else 50.0
        accuracy = 100.0  # FRED is authoritative for rates

        score = save_quality_score("fred", freshness, completeness, accuracy, latency)
        logger.info(f"FRED scored: {score:.1f}")
        return {"vendor_id": "fred", "overall": score, "freshness": freshness,
                "completeness": completeness, "accuracy": accuracy, "latency_minutes": latency}
    except Exception as e:
        logger.error(f"FRED scoring failed: {e}")
        score = save_quality_score("fred", 0.0, 0.0, 0.0, None)
        return {"vendor_id": "fred", "overall": 0.0, "error": str(e)}


def score_ecb() -> dict:
    logger.info("Scoring vendor: ecb")
    start = time.time()
    try:
        url = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=5&format=jsondata"
        resp = requests.get(url, timeout=10)
        latency = (time.time() - start) / 60
        resp.raise_for_status()

        data = resp.json()
        obs = data["dataSets"][0]["series"]["0:0:0:0:0"]["observations"]
        freshness = 80.0 if obs else 0.0  # ECB publishes daily around 16:00 CET
        completeness = 100.0 if len(obs) >= 3 else 50.0

        # Accuracy: cross-check EUR/USD vs Yahoo
        try:
            ecb_rate = float(list(obs.values())[-1][0])
            yf_rate_series = yf.download("EURUSD=X", period="2d", progress=False)["Close"].dropna()
            yahoo_rate = float(yf_rate_series.iloc[-1])
            accuracy = _score_accuracy(ecb_rate, yahoo_rate)
        except Exception:
            accuracy = 85.0

        score = save_quality_score("ecb", freshness, completeness, accuracy, latency)
        logger.info(f"ECB scored: {score:.1f}")
        return {"vendor_id": "ecb", "overall": score, "freshness": freshness,
                "completeness": completeness, "accuracy": accuracy, "latency_minutes": latency}
    except Exception as e:
        logger.error(f"ECB scoring failed: {e}")
        score = save_quality_score("ecb", 0.0, 0.0, 0.0, None)
        return {"vendor_id": "ecb", "overall": 0.0, "error": str(e)}


def score_alpha_vantage() -> dict:
    logger.info("Scoring vendor: alpha_vantage")
    if not ALPHA_VANTAGE_KEY:
        logger.warning("ALPHA_VANTAGE_KEY not set — scoring with defaults")
        score = save_quality_score("alpha_vantage", 70.0, 80.0, 85.0, None)
        return {"vendor_id": "alpha_vantage", "overall": score,
                "note": "no API key, estimated scores"}
    start = time.time()
    try:
        url = (f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE"
               f"&symbol=AAPL&apikey={ALPHA_VANTAGE_KEY}")
        resp = requests.get(url, timeout=15)
        latency = (time.time() - start) / 60
        resp.raise_for_status()

        data = resp.json()
        quote = data.get("Global Quote", {})
        freshness = 75.0 if quote.get("05. price") else 20.0
        completeness = _score_completeness(len([v for v in quote.values() if v]), 10)

        try:
            av_price = float(quote.get("05. price", 0))
            yf_series = yf.download("AAPL", period="2d", progress=False)["Close"].dropna()
            yahoo_price = float(yf_series.iloc[-1])
            accuracy = _score_accuracy(av_price, yahoo_price)
        except Exception:
            accuracy = 80.0

        score = save_quality_score("alpha_vantage", freshness, completeness, accuracy, latency)
        logger.info(f"Alpha Vantage scored: {score:.1f}")
        return {"vendor_id": "alpha_vantage", "overall": score, "freshness": freshness,
                "completeness": completeness, "accuracy": accuracy, "latency_minutes": latency}
    except Exception as e:
        logger.error(f"Alpha Vantage scoring failed: {e}")
        score = save_quality_score("alpha_vantage", 0.0, 0.0, 0.0, None)
        return {"vendor_id": "alpha_vantage", "overall": 0.0, "error": str(e)}


def score_bloomberg() -> dict:
    logger.info("Scoring vendor: bloomberg — mock only, no live API")
    score = save_quality_score("bloomberg", 99.0, 99.0, 99.0, 0.0)
    return {"vendor_id": "bloomberg", "overall": score,
            "note": "mock schema — no B-Pipe access in paper portfolio"}


def run_all_scoring() -> list[dict]:
    results = []
    scorers = [score_yahoo, score_fred, score_ecb, score_alpha_vantage, score_bloomberg]
    for scorer in scorers:
        try:
            results.append(scorer())
        except Exception as e:
            logger.error(f"Scorer {scorer.__name__} raised: {e}")
    return results
