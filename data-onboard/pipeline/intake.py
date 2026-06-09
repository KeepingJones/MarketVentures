"""
Vendor intake — stage 1 of the onboarding pipeline.

Accepts a vendor intake form (dict), validates required fields,
seeds the vendor into the pipeline DB, performs initial gap analysis
against existing market-data-hub catalogue, and uses Ollama to
generate an integration specification document.
"""
import json
import logging
from typing import Optional

import httpx

from config import (
    OLLAMA_URL, OLLAMA_MODEL,
    OPENFIGI_API_URL, OPENFIGI_API_KEY,
)
from db.database import (
    create_vendor, advance_stage,
    save_coverage_gap, save_figi_mapping,
)

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["vendor_name", "vendor_id", "contact_email", "api_endpoint", "asset_classes"]

# Asset classes already covered by existing vendors (from market-data-hub)
EXISTING_COVERAGE = {
    "equity", "fx", "govt_bond", "corp_bond", "commodity",
    "volatility", "rate", "macro", "credit_spread",
}


def validate_intake(form: dict) -> list[str]:
    errors = []
    for f in REQUIRED_FIELDS:
        if not form.get(f):
            errors.append(f"Missing required field: {f}")
    if form.get("asset_classes") and not isinstance(form["asset_classes"], list):
        errors.append("asset_classes must be a list")
    return errors


def run_gap_analysis(vendor_id: str, claimed_asset_classes: list[str]) -> dict:
    new_coverage = []
    duplicates = []
    partial = []

    for ac in claimed_asset_classes:
        if ac not in EXISTING_COVERAGE:
            new_coverage.append(ac)
            save_coverage_gap(vendor_id, ac, "new_coverage",
                              f"{ac} not yet in catalogue — adds value")
        else:
            duplicates.append(ac)
            save_coverage_gap(vendor_id, ac, "duplicate",
                              f"{ac} already covered — check quality differential")

    return {
        "new_coverage": new_coverage,
        "duplicates": duplicates,
        "partial_overlap": partial,
        "recommendation": "proceed" if new_coverage else "low_value_add",
    }


def validate_openfigi(vendor_id: str, tickers: list[str]) -> list[dict]:
    if not tickers:
        return []

    headers = {"Content-Type": "application/json"}
    if OPENFIGI_API_KEY:
        headers["X-OPENFIGI-APIKEY"] = OPENFIGI_API_KEY

    results = []
    # OpenFIGI accepts batches of 10
    for i in range(0, len(tickers), 10):
        batch = tickers[i:i+10]
        payload = [{"idType": "TICKER", "idValue": t} for t in batch]
        try:
            resp = httpx.post(OPENFIGI_API_URL, json=payload, headers=headers, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            for ticker, item in zip(batch, data):
                figidata = item.get("data", [])
                if not figidata:
                    save_figi_mapping(vendor_id, ticker, None, "", "", "no_match")
                    results.append({"ticker": ticker, "status": "no_match"})
                elif len(figidata) == 1:
                    figi = figidata[0].get("figi", "")
                    save_figi_mapping(vendor_id, ticker, figi,
                                      figidata[0].get("securityType", ""),
                                      figidata[0].get("marketSector", ""), "matched")
                    results.append({"ticker": ticker, "figi": figi, "status": "matched"})
                else:
                    save_figi_mapping(vendor_id, ticker, None, "", "", "multiple_matches")
                    results.append({"ticker": ticker, "status": "multiple_matches",
                                    "count": len(figidata)})
        except Exception as e:
            logger.error(f"OpenFIGI batch failed: {e}")
            for ticker in batch:
                results.append({"ticker": ticker, "status": "error", "error": str(e)})
    return results


def generate_integration_spec(form: dict, gap_analysis: dict) -> str:
    prompt = f"""You are a market data engineer. Generate a concise integration specification document for a new data vendor.

Vendor details:
{json.dumps(form, indent=2)}

Coverage gap analysis:
{json.dumps(gap_analysis, indent=2)}

Write a structured integration specification with these sections:
1. Vendor Overview
2. Technical Integration (API endpoint, authentication, data format)
3. Asset Class Coverage (new vs duplicate)
4. Data Quality Requirements (completeness, latency, accuracy thresholds)
5. Testing Plan (30-day QA period milestones)
6. Go-Live Checklist

Be specific. Use the vendor details provided."""

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        return resp.json().get("response", "LLM spec generation unavailable.")
    except Exception as e:
        logger.error(f"LLM spec generation failed: {e}")
        return f"Integration spec for {form.get('vendor_name', 'Unknown vendor')} - LLM unavailable."


def process_intake(form: dict, sample_tickers: Optional[list[str]] = None) -> dict:
    errors = validate_intake(form)
    if errors:
        return {"status": "error", "errors": errors}

    vendor_id = form["vendor_id"]
    create_vendor(
        vendor_name=form["vendor_name"],
        vendor_id=vendor_id,
        contact_email=form.get("contact_email", ""),
        api_endpoint=form.get("api_endpoint", ""),
        asset_classes=form.get("asset_classes", []),
    )
    logger.info(f"Vendor {vendor_id} created in pipeline")

    gap = run_gap_analysis(vendor_id, form.get("asset_classes", []))

    figi_results = []
    if sample_tickers:
        figi_results = validate_openfigi(vendor_id, sample_tickers)

    spec = generate_integration_spec(form, gap)
    advance_stage(vendor_id, "gap_analysis", "pass", "Intake complete, gap analysis done")

    return {
        "status": "success",
        "vendor_id": vendor_id,
        "gap_analysis": gap,
        "figi_validation": figi_results,
        "integration_spec": spec,
        "next_stage": "legal_check",
    }
