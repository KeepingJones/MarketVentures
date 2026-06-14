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
Live data sources                   Reconciliation engine                 Outputs
─────────────────────               ──────────────────────                ────────
Yahoo Finance (yfinance)  ──┐
FRED (fredapi)            ──┤──► data/sources/  ──► recon/engine.py ──► db/ ──► api/
ECB REST API              ──┤       │                     │
Bloomberg mock (B-PIPE)   ──┘       └── data/models.py    ├── recon/classifier.py
                                                           ├── recon/liquidity.py
                                                           └── recon/escalation.py
                                                                          │
                                                               ┌──────────┴──────────┐
                                                          reports/          dashboard/
                                                         Excel EOD         Chart.js UI
```

> **Bloomberg note:** `data/sources/bloomberg_mock.py` simulates Bloomberg B-PIPE pricing with realistic field names (`PX_LAST`, `BID`, `ASK`, `CRNCY`). To wire in a real Bloomberg terminal: install `blpapi`, replace `_bloomberg_field_request()` with a live `BDP` call, and remove the Yahoo base-price lookup. The rest of the engine is unchanged.

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
git clone https://github.com/KeepingJones/MarketVentures.git
cd MarketVentures/price-recon
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — add your FRED_API_KEY (free at fred.stlouisfed.org)

# 3. Run reconciliation (fetches live prices, classifies breaks, saves to fund.db)
python main.py

# 4. Start API + dashboard
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
