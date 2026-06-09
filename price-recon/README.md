# price-recon — EOD Pricing Reconciliation Engine

**Business problem:** At the end of every trading day, a market data team is handed hundreds of price discrepancies across a multi-asset book. Which price is right? Why did it break? Who owns the fix? Without a systematic answer to those questions, EOD NAV is late and risk is measured against the wrong prices.

`price-recon` automates this — fetching live prices from multiple sources, classifying every break by root cause, and producing the Excel report the Head of Market Data actually reads.

---

## What it demonstrates

- **Multi-source price validation** across equities, FX, government bonds, corporate bonds, credit spreads, commodity futures, and volatility indices
- **Break classification by root cause** — stale price, source outage, corporate action, FX conversion artefact, spread within normal, data quality, genuine discrepancy
- **Liquidity-adjusted tolerances** — L1 (large cap equities, benchmark FX) uses tight thresholds; L3 (illiquid credit, exotic FX) gets wider — same logic as production Bloomberg vs internal pricing systems
- **FX rate monitoring** treated as severity-1: a stale GBP/USD marks the entire non-GBP book incorrectly
- **GBP-denominated fund** — all breaks reported in GBP terms with FX contribution isolated
- **Escalation routing** — critical breaks auto-escalated by asset class
- **Excel EOD report** — automated via OpenPyXL, formatted for distribution to desk heads
- **Live dashboard** — Chart.js, break summary by asset class, severity heatmap

---

## Architecture

```
Live data sources                   Reconciliation engine          Outputs
─────────────────────               ──────────────────────         ────────
Yahoo Finance (yfinance)  ──┐
FRED (fredapi)            ──┤──► data/sources/  ──► recon/engine.py ──► db/  ──► api/
ECB REST API              ──┤       │                     │
Alpha Vantage             ──┘       └── data/models.py    └── recon/classifier.py
                                                          └── recon/liquidity.py
                                                          └── recon/escalation.py

                                                                         │
                                                              ┌──────────┴──────────┐
                                                         reports/          dashboard/
                                                        Excel EOD         Chart.js UI
```

---

## Asset class coverage

| Asset class | Sources | Tolerance | Liquidity tier |
|---|---|---|---|
| Equities | Yahoo Finance, Alpha Vantage | 50bp | L1–L3 by ADV |
| FX | Yahoo Finance, ECB | 10bp | L1 |
| Government bonds | FRED, Yahoo Finance (ETF) | 5bp | L1 |
| Corporate bonds | FRED ICE BofA spreads | 100bp | L2–L3 |
| Commodity futures | Yahoo Finance | 100bp | L1–L2 |
| Volatility indices | Yahoo Finance (^VIX) | 200bp | L1 |

---

## Acceptance criteria

- [x] Live prices ingested from 3+ sources via API
- [x] 6 asset classes covered
- [x] Break classification with 7 root cause types
- [x] Liquidity tiering (L1/L2/L3) applied to tolerance thresholds
- [x] Excel EOD report auto-generated with break summary by asset class
- [ ] Dashboard live in browser
- [x] README leads with business problem

---

## Quick start

```bash
# 1. Clone and set up
cd C:\Users\ewanj\price-recon
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Environment — keys already copied from trading-bot
#    FRED_API_KEY is pre-filled in .env

# 3. Initialise database
python -c "from db.database import init_db; init_db()"

# 4. Run reconciliation
python main.py

# 5. Start API + dashboard
uvicorn api.routes:app --reload
# Open http://localhost:8000
```

---

## Safety

`PAPER_TRADE_MODE = True` is hardcoded in `config.py`. This project handles market data only — no order routing, no live capital.

---

## Part of the GBP fund portfolio ecosystem

price-recon is project 1 of 5, all sharing a common SQLite database.

| # | Project | What it adds |
|---|---|---|
| 1 | **price-recon** (this) | Price validation, break detection, EOD reporting |
| 2 | market-data-hub | Data catalogue, vendor registry, quality scoring |
| 3 | alpha-pipeline | Signal generation, risk, FX hedging, paper execution |
| 4 | data-onboard | Vendor onboarding workflow, coverage gap analysis |
| 5 | market-ops | Unified operations dashboard, stakeholder PDF report |
