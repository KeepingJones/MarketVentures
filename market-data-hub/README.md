# market-data-hub — Market Data Management Platform

**Business problem:** No single view of what data the firm has, what it costs, who uses it, or whether it's any good. Vendor SLAs get missed. Data quality issues reach the trading desk. New vendor onboarding takes weeks with no structured process.

`market-data-hub` is the data catalogue, vendor registry, quality scoring engine, and cost allocation dashboard — the system a Head of Market Data builds before anything else.

---

## What it demonstrates

- **Vendor registry** — Yahoo Finance, FRED, ECB, Alpha Vantage, Bloomberg (mock): SLAs, cost, delivery method, asset class coverage
- **Dataset catalogue** — 13 datasets tagged with quality score, coverage, frequency, and licence type
- **Live quality scoring** — hits real APIs on schedule, measures freshness, completeness, and accuracy vs Yahoo benchmark; scores each vendor 0–100
- **Usage tracking** — which desk (equity, FX, rates, credit, quant) pulls which datasets; recorded in shared `fund.db`
- **Cost allocation** — vendor spend split proportionally across desks; the CFO's number
- **Risk data flagging** — which datasets are on the critical risk path (VaR inputs, stress scenarios, Greeks) — highlighted red in the dashboard
- **Entitlements engine** — licence gates: `display_only` / `derived_data` / `execution_licensed` / `internal_only` / `redistributable`. Desk entitlement matrix enforced per request. Blocks automated use of display-only data — the compliance failure that gets firms fined by the FCA/SEC
- **LLM catalogue query** — natural language questions over the catalogue via Ollama (`phi3.5` by default); requires local Ollama install
- **LLM RAG over vendor contracts** — keyword-ranked contract chunks fed to Ollama to answer "can we redistribute this to our offshore desk?" type questions

---

## Architecture

```
External APIs                  market-data-hub                       Outputs
────────────                   ───────────────                       ───────
Yahoo Finance  ──┐
FRED           ──┤──► data/quality_scorer.py ──► db/database.py ──► fund.db
ECB REST       ──┤         │                          │
Alpha Vantage  ──┤     quality_scores            vendor_registry       │
Bloomberg mock ──┘     usage_events              datasets          api/routes.py
                                                 entitlement_checks    │
                                                                  dashboard/
                                                                 index.html (Chart.js)
                                                                 /api/query (Ollama)
```

---

## Vendor registry

| Vendor | Delivery | SLA | Cost/yr | Status |
|---|---|---|---|---|
| Yahoo Finance | yfinance API | 15 min | Free | Active |
| FRED (St. Louis Fed) | REST API | Daily | Free | Active |
| ECB | REST API | Daily | Free | Active |
| Alpha Vantage | REST API | 15 min | Free (25 req/day) | Active |
| Bloomberg B-Pipe | BLPAPI server | Real-time | $24,000 | Inactive (mock) |

---

## Desk entitlement matrix

| Desk | Display Only | Derived Data | Execution Licensed |
|---|---|---|---|
| Equity | ✓ | ✓ | ✓ |
| FX | ✓ | ✓ | ✓ |
| Rates | ✓ | ✓ | ✓ |
| Credit | ✓ | ✓ | — |
| Quant | ✓ | ✓ | ✓ |
| Risk | ✓ | ✓ | — |
| Operations | ✓ | — | — |

---

## Acceptance criteria

- [x] 5+ real data sources catalogued with live quality scores
- [x] Usage tracking connected to shared fund.db
- [x] Cost allocation dashboard showing spend per desk
- [x] Risk data flagging (critical path datasets highlighted)
- [x] Entitlement engine enforcing licence type × desk matrix
- [x] LLM query working over the catalogue
- [x] Chart.js dashboard: quality bar chart, desk usage doughnut, vendor/dataset tables

---

## Quick start

```bash
# 1. Clone and set up
git clone https://github.com/KeepingJones/MarketVentures.git
cd MarketVentures/market-data-hub
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — add FRED_API_KEY (free) and ALPHA_VANTAGE_KEY (free)

# 3. Seed catalogue and start API
python main.py
# Dashboard: http://localhost:8001

# 4. Run quality scoring pass
python main.py --score
```

---

## Running tests

```bash
cd MarketVentures/market-data-hub
python -m pytest tests/ -v
```

Tests cover quality scoring math, entitlement logic, vendor config completeness, and DB schema operations.

---

## Safety

`PAPER_TRADE_MODE = True` hardcoded in `config.py`. Data catalogue only — no order routing, no live capital.

---

## Part of the GBP fund portfolio ecosystem

| # | Project | What it adds |
|---|---|---|
| 1 | price-recon | Price validation, break detection, EOD Excel reporting |
| 2 | **market-data-hub** (this) | Data catalogue, vendor registry, quality scoring |
| 3 | alpha-pipeline | Signal generation, risk, FX hedging, paper execution |
| 4 | data-onboard | Vendor onboarding workflow, coverage gap analysis |
| 5 | market-ops | Unified operations dashboard, stakeholder PDF report |

---

## Stack

Python · FastAPI · SQLite (shared fund.db) · Chart.js · Ollama · yfinance · fredapi
