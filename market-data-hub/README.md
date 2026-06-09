# market-data-hub — Market Data Management Platform

**Business problem:** No single view of what data the firm has, what it costs, who uses it, or whether it's any good. Vendor SLAs get missed. Data quality issues reach the trading desk. New vendor onboarding takes weeks with no structured process.

`market-data-hub` is the data catalogue, vendor registry, quality scoring engine, and cost allocation dashboard — the system a Head of Market Data builds before anything else.

---

## Vault plan

Full spec: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md` (Project 2)
Portfolio plan: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\portfolio-plan.md`

---

## How it links to the other projects

```
price-recon        → feeds break data into this hub's data quality scores
market-data-hub    ← YOU ARE HERE — central catalogue
alpha-pipeline     → reads catalogue to know which datasets are available + quality-gated
data-onboard       → vendors get added here after passing onboarding pipeline
market-ops         → reads catalogue for vendor SLA tracking + feed health board
```

Shared database: `C:\Users\ewanj\fund.db` — all 5 projects read/write here.

---

## What it demonstrates

- **Vendor registry** — Bloomberg, Refinitiv, ICE, FRED, Alpha Vantage: contracts, SLAs, cost, delivery method
- **Dataset catalogue** — all asset classes tagged with quality score, coverage, frequency
- **Live quality scoring** — hits real APIs on schedule, scores freshness, completeness, accuracy vs benchmark
- **Usage tracking** — which desk (equity, FX, rates, credit, quant) pulls which datasets
- **Cost allocation** — vendor spend per desk (the CFO's number)
- **Risk data flagging** — which datasets are on the critical risk path (VaR inputs, stress scenarios, Greeks)
- **LLM-powered discovery** — natural language queries over the catalogue via Ollama
- **Vendor comparison** — side-by-side coverage, quality, cost per dataset
- **Data Entitlements & Licensing Engine** — datasets tagged with licence type (*Display Only* / *Derived Data Allowed* / *Execution Licensed*). Desk requests are checked against entitlements before data is served. Blocks automated use of display-only data — the compliance failure that gets hedge funds fined by the LSE/SEC.
- **LLM RAG over vendor contracts** — dummy MSA PDFs indexed via Ollama + vector search. Chat interface answers *"Can we redistribute this ICE data to our offshore team?"* by citing the exact contract clause. Replaces 3-day legal turnaround for routine data usage questions.

---

## Asset class coverage

| Vendor | Equities | FX | Rates/Macro | Credit | Commodities | Options/Deriv | Status |
|---|---|---|---|---|---|---|---|
| Yahoo Finance | ✓ | ✓ | partial | — | ✓ | ✓ | Live |
| FRED | — | — | ✓ | ✓ (spreads) | — | — | Live |
| ECB | — | ✓ (EUR) | ✓ | — | — | — | Live |
| Alpha Vantage | ✓ | ✓ | ✓ | — | ✓ | — | Live |
| Bloomberg (mock) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Mock schema |

---

## Acceptance criteria

- [ ] 5+ real data sources catalogued with live quality scores
- [ ] Usage tracking connected to shared fund.db
- [ ] Cost allocation dashboard showing spend per desk
- [ ] Risk data flagging (critical path datasets highlighted)
- [ ] LLM query working over the catalogue
- [ ] README architecture diagram and screenshot

---

## Quick start

```bash
cd C:\Users\ewanj\market-data-hub
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -c "from db.database import init_db; init_db()"
python main.py
# Dashboard: http://localhost:8001
```

---

## Stack

Python · FastAPI · SQLite (shared fund.db) · React · Ollama · yfinance · fredapi · schedule

**Build order:** price-recon must be running first (quality scores read break data from fund.db)

## Safety

`PAPER_TRADE_MODE = True` hardcoded. Data catalogue only — no order routing.
