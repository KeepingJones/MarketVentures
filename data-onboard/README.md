# data-onboard — Vendor Data Onboarding & Integration Workflow

**Business problem:** Onboarding a new data vendor is 8 weeks of email chains with no structured process. Things fall through the cracks at go-live. A vendor passes legal but fails the technical integration. Another passes technical but has poor data quality that only shows up in production.

`data-onboard` formalises this into a structured pipeline: intake → coverage gap analysis → legal/compliance check → technical spec → QA period → go-live sign-off.

---

## Vault plan

Full spec: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md` (Project 4)
Portfolio plan: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\portfolio-plan.md`

---

## How it links to the other projects

```
price-recon      → demonstrates the problem this solves (bad data = breaks)
market-data-hub  → vendors approved here get added to the catalogue there
alpha-pipeline   → new data sources flow in via this pipeline
data-onboard     ← YOU ARE HERE — vendor onboarding workflow
market-ops       → vendor SLA tracker reads onboarding status
```

Shared database: `C:\Users\ewanj\fund.db` — vendor pipeline state written here.

---

## What it demonstrates

- **Structured pipeline** — intake → gap analysis → legal check → tech spec → QA → go-live
- **Live QA module** — connects to the actual vendor API at intake, runs 30-day quality assessment (completeness, freshness, accuracy vs benchmark)
- **OpenFIGI validation** — maps vendor identifiers to Bloomberg FIGIs, catches mapping mismatches before production (https://openfigi.com/api)
- **Coverage gap analysis** — compares new vendor against existing catalogue from market-data-hub
- **Liquidity data assessment** — does vendor provide bid-ask, volume, depth?
- **Risk data assessment** — does vendor cover VaR inputs, stress scenarios, Greeks?
- **FX coverage check** — does vendor provide GBP cross rates, forward points?
- **LLM spec generation** — auto-produces integration specification document from intake form via Ollama
- **Unstructured Alternative Data Ingestion** — dedicated pipeline that takes a PDF (earnings transcript, SEC filing, research report) and uses an LLM to extract a structured JSON signal: `{"sentiment": "bearish", "revenue_guidance": "lowered", "ticker": "AAPL"}`. Operationalises unstructured alpha sources — the kind of data that actually generates edge.
- **Status dashboard** — pipeline view of all vendors in onboarding

---

## Acceptance criteria

- [ ] Full pipeline with 5+ stages and stage-gating
- [ ] Live QA module connects to real API and produces quality report
- [ ] OpenFIGI identifier validation working
- [ ] Coverage gap analysis against market-data-hub catalogue
- [ ] LLM-generated integration spec document
- [ ] Status dashboard showing all vendors in pipeline

---

## Quick start

```bash
cd C:\Users\ewanj\data-onboard
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -c "from db.database import init_db; init_db()"
python main.py
# Dashboard: http://localhost:8003
```

---

## Stack

Python · FastAPI · SQLite (shared fund.db) · React · Ollama · yfinance · Alpha Vantage · fredapi · OpenFIGI API

**Depends on:** market-data-hub (catalogue for gap analysis)
