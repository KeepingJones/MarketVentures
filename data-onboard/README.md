# data-onboard — Vendor Data Onboarding & Integration Workflow

![data-onboard workflow](docs/onboard_workflow.png)

**Business problem:** Onboarding a new data vendor is 8 weeks of email chains with no structured process. Things fall through the cracks at go-live. A vendor passes legal but fails the technical integration. Another passes technical but has poor data quality that only shows up in production.


`data-onboard` formalises this into a 6-stage structured pipeline: intake â†’ coverage gap analysis â†’ legal/compliance check â†’ tech spec â†’ 30-day QA period â†’ go-live sign-off. Vendors that don't meet QA thresholds don't go live.

---

## Architecture

```mermaid
graph LR
    A[Vendor intake JSON] --> B[QA assessment<br/>live API checks]
    B --> C[OpenFIGI<br/>identifier validation]
    C --> D[Coverage gap analysis<br/>vs market-data-hub catalogue]
    D --> E[LLM integration spec<br/>Ollama]
    E --> F[30-day QA gate]
    F --> G[Go-live<br/>catalogued in fund.db]
```

---

## What it demonstrates

- **6-stage onboarding pipeline** â€” each stage has a pass/fail gate with audit trail in `fund.db`
- **Coverage gap analysis** â€” new vendors checked against existing catalogue; "low value add" recommendation if all asset classes are already covered
- **OpenFIGI identifier mapping** â€” vendor tickers resolved to Bloomberg FIGIs (openfigi.com free API), flagging unresolvable instruments before go-live
- **LLM integration spec generation** â€” Ollama generates a structured integration document (vendor overview, API auth, data format, testing plan, go-live checklist) from the intake form
- **30-day QA assessment** â€” measures completeness (â‰¥95%), latency (â‰¤30 min), accuracy vs Yahoo benchmark (â‰¥99%); simulated mode for demo vendors
- **Alt data ingestion pipeline** â€” PDF documents (earnings transcripts, SEC filings, research reports) â†’ LLM extraction â†’ structured JSON signal output (`ticker`, `sentiment`, `revenue_guidance`, `earnings_surprise`, `confidence`)
- **Pipeline stage audit log** â€” every stage transition recorded with timestamp, outcome, and notes

---

## Pipeline stages

```
Vendor submits intake form
         â”‚
    [1] intake â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ validate required fields
         â”‚
    [2] gap_analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ coverage vs existing catalogue
         â”‚                           â†’ proceed / low_value_add
    [3] legal_check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ licence type, GDPR, redistribution rights
         â”‚
    [4] tech_spec â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ LLM-generated integration document
         â”‚
    [5] qa_period â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 30-day live assessment:
         â”‚                             completeness â‰¥ 95%
         â”‚                             latency â‰¤ 30 min
         â”‚                             accuracy â‰¥ 99%
         â”‚
    [6] go_live â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ sign-off â†’ add to market-data-hub catalogue
```

---

## QA thresholds

| Metric | Pass threshold | Why |
|---|---|---|
| Completeness | â‰¥ 95% fields populated | Sparse data breaks VaR inputs silently |
| Latency | â‰¤ 30 min stale | EOD risk run requires same-day prices |
| Accuracy | â‰¥ 99% vs benchmark | >1% deviation invalidates stress tests |

---

## Acceptance criteria

- [x] 6-stage pipeline with stage gate logic
- [x] Intake validation (all required fields enforced)
- [x] Coverage gap analysis vs existing catalogue
- [x] OpenFIGI ticker â†’ FIGI resolution (batched, 10 per request)
- [x] LLM integration spec via Ollama
- [x] 30-day QA assessment with pass/fail thresholds
- [x] Alt data extraction pipeline (PDF â†’ LLM â†’ structured JSON)
- [x] All stages logged in shared fund.db with audit trail

---

## Quick start

```bash
# 1. Clone and set up
git clone https://github.com/KeepingJones/MarketVentures.git
cd MarketVentures/data-onboard
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env â€” OPENFIGI_API_KEY is optional (free tier works without it)

# 3. Start API
python main.py
# Dashboard: http://localhost:8003

# 4. Submit a vendor for onboarding (example)
curl -X POST http://localhost:8003/api/onboard \
  -H "Content-Type: application/json" \
  -d '{"vendor_name":"Acme Data","vendor_id":"acme","contact_email":"data@acme.com","api_endpoint":"https://api.acme.com","asset_classes":["equity","crypto"]}'
```

---

## Running tests

```bash
cd MarketVentures/data-onboard
python -m pytest tests/ -v
```

Tests cover intake validation, gap analysis logic, QA threshold pass/fail criteria, pipeline stage ordering, and alt data schema shape.

---

## Safety

`PAPER_TRADE_MODE = True` hardcoded in `config.py`. Onboarding pipeline only â€” no order routing, no live capital.

---

## Part of the GBP fund portfolio ecosystem

| # | Project | What it adds |
|---|---|---|
| 1 | price-recon | Price validation, break detection, EOD Excel reporting |
| 2 | market-data-hub | Data catalogue, vendor registry, quality scoring |
| 3 | alpha-pipeline | Signal generation, risk, FX hedging, paper execution |
| 4 | **data-onboard** (this) | Vendor onboarding workflow, coverage gap analysis |
| 5 | market-ops | Unified operations dashboard, stakeholder PDF report |

---

## Stack

Python Â· FastAPI Â· SQLite (shared fund.db) Â· OpenFIGI API Â· Ollama Â· yfinance

