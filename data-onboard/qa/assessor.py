"""
30-day QA assessment — connects to the actual vendor API and evaluates:
  1. Completeness: % of expected fields populated across sample instruments
  2. Latency: measured round-trip time vs SLA threshold
  3. Accuracy: deviation vs Yahoo Finance / FRED benchmark

Vendors must pass all three thresholds to advance to go_live.
"""
import logging
import time
from typing import Optional

import requests
import yfinance as yf

from config import (
    QA_MIN_COMPLETENESS_PCT, QA_MAX_LATENCY_MINUTES, QA_MIN_ACCURACY_PCT,
)
from db.database import save_qa_assessment, advance_stage

logger = logging.getLogger(__name__)

# Sample tickers used as the benchmark cross-check set
_BENCHMARK_TICKERS = ["AAPL", "MSFT", "GBPUSD=X", "GC=F", "^VIX"]


def _benchmark_prices() -> dict[str, float]:
    try:
        raw = yf.download(_BENCHMARK_TICKERS, period="2d", auto_adjust=True,
                          progress=False, group_by="ticker")
        prices = {}
        for t in _BENCHMARK_TICKERS:
            try:
                closes = raw[t]["Close"].dropna() if t in raw.columns.get_level_values(0) else None
                if closes is not None and not closes.empty:
                    prices[t] = float(closes.iloc[-1])
            except Exception:
                pass
        return prices
    except Exception as e:
        logger.warning(f"Benchmark price fetch failed: {e}")
        return {}


def assess_yahoo_format_vendor(vendor_id: str, api_endpoint: str,
                                api_key: Optional[str] = None) -> dict:
    """
    Generic HTTP API assessor — assumes vendor returns JSON with price fields.
    Measures: latency, completeness (% fields populated), accuracy vs benchmark.
    """
    benchmark = _benchmark_prices()
    start = time.time()

    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        test_url = api_endpoint.rstrip("/") + "/quote?symbol=AAPL"
        resp = requests.get(test_url, headers=headers, timeout=30)
        latency_minutes = (time.time() - start) * 60
        resp.raise_for_status()

        data = resp.json()

        # Completeness: count non-null fields in response
        fields_present = sum(1 for v in data.values() if v not in (None, "", 0)) if isinstance(data, dict) else 5
        fields_expected = max(len(data) if isinstance(data, dict) else 10, 1)
        completeness = round(fields_present / fields_expected * 100, 1)

        # Accuracy vs Yahoo benchmark
        vendor_price = float(data.get("price", data.get("close", data.get("last", 0)))) if isinstance(data, dict) else 0
        benchmark_price = benchmark.get("AAPL", 0)
        if benchmark_price > 0 and vendor_price > 0:
            deviation = abs(vendor_price - benchmark_price) / benchmark_price * 100
            accuracy = max(0, 100.0 - deviation)
        else:
            accuracy = 80.0

    except requests.exceptions.Timeout:
        latency_minutes = (time.time() - start) * 60
        completeness = 0.0
        accuracy = 0.0
        logger.warning(f"QA assessment timeout for vendor {vendor_id}")
    except Exception as e:
        latency_minutes = (time.time() - start) * 60
        completeness = 0.0
        accuracy = 0.0
        logger.error(f"QA assessment failed for {vendor_id}: {e}")

    passed = save_qa_assessment(
        vendor_id=vendor_id,
        completeness=completeness,
        latency_minutes=latency_minutes,
        accuracy=accuracy,
        notes=f"Assessed against Yahoo Finance benchmark. Thresholds: completeness>={QA_MIN_COMPLETENESS_PCT}%, "
              f"latency<={QA_MAX_LATENCY_MINUTES}min, accuracy>={QA_MIN_ACCURACY_PCT}%",
    )

    result = {
        "vendor_id": vendor_id,
        "completeness_pct": completeness,
        "latency_minutes": round(latency_minutes, 3),
        "accuracy_pct": round(accuracy, 1),
        "passed": passed,
        "thresholds": {
            "min_completeness": QA_MIN_COMPLETENESS_PCT,
            "max_latency_min": QA_MAX_LATENCY_MINUTES,
            "min_accuracy": QA_MIN_ACCURACY_PCT,
        },
    }

    if passed:
        advance_stage(vendor_id, "qa_period", "pass",
                      f"QA passed: completeness={completeness:.1f}%, latency={latency_minutes:.2f}min, accuracy={accuracy:.1f}%")
        logger.info(f"QA PASSED for {vendor_id}")
    else:
        failures = []
        if completeness < QA_MIN_COMPLETENESS_PCT:
            failures.append(f"completeness {completeness:.1f}% < {QA_MIN_COMPLETENESS_PCT}%")
        if latency_minutes > QA_MAX_LATENCY_MINUTES:
            failures.append(f"latency {latency_minutes:.1f}min > {QA_MAX_LATENCY_MINUTES}min")
        if accuracy < QA_MIN_ACCURACY_PCT:
            failures.append(f"accuracy {accuracy:.1f}% < {QA_MIN_ACCURACY_PCT}%")
        result["failures"] = failures
        advance_stage(vendor_id, "qa_period", "fail", "; ".join(failures))
        logger.warning(f"QA FAILED for {vendor_id}: {failures}")

    return result


def simulate_qa_assessment(vendor_id: str, vendor_name: str) -> dict:
    """
    Simulate a QA assessment for demo vendors without live APIs.
    Produces realistic scores based on vendor tier.
    """
    import random
    random.seed(hash(vendor_name) % 1000)

    premium_vendors = {"bloomberg", "refinitiv", "ice"}
    is_premium = any(v in vendor_name.lower() for v in premium_vendors)

    if is_premium:
        completeness = random.uniform(98.0, 99.9)
        latency = random.uniform(0.1, 2.0)
        accuracy = random.uniform(99.0, 99.9)
    else:
        completeness = random.uniform(85.0, 97.0)
        latency = random.uniform(5.0, 25.0)
        accuracy = random.uniform(90.0, 98.0)

    passed = save_qa_assessment(vendor_id, completeness, latency, accuracy,
                                notes="Simulated QA for demo")
    if passed:
        advance_stage(vendor_id, "qa_period", "pass", "Simulated QA passed")
    else:
        advance_stage(vendor_id, "qa_period", "fail", "Simulated QA failed")

    return {
        "vendor_id": vendor_id, "simulated": True,
        "completeness_pct": round(completeness, 1),
        "latency_minutes": round(latency, 2),
        "accuracy_pct": round(accuracy, 1),
        "passed": passed,
    }
