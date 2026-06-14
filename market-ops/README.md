# market-ops — Live Market Data Operations Dashboard

**Business problem:** The Head of Market Data, COO, and CRO each need a different view of the same data — but there's no single system that shows feed health, risk exposure, liquidity profile, FX hedging status, and open price breaks in one place. The morning meeting runs on a PDF pulled together manually by someone who should be solving actual problems.

`market-ops` is the unified operations dashboard that ties all four other projects together — reading from the shared `fund.db` to present a single view, and generating a formatted PDF stakeholder report at the press of a button.

---

## What it demonstrates

- **Unified aggregation** — reads from all 4 upstream projects' tables via shared SQLite (`fund.db`); market-ops is read-only except for its own ops tables
- **Live break monitoring** — open price breaks from price-recon, severity-classified, with CRITICAL alert if threshold exceeded
- **Portfolio risk view** — NAV, drawdown, VaR 95%/99% from alpha-pipeline snapshots; alert if VaR > 3% of NAV
- **FX hedging status** — active forwards from alpha-pipeline, roll calendar, notional exposure by currency
- **Data feed health** — vendor quality scores from market-data-hub, SLA breach tracker, latency vs contract
- **SLA penalty engine** — commercial rebate calculation: `breach_hours × 1% × monthly_vendor_fee` per hour of contractual breach
- **Vendor onboarding pipeline** — status of vendors in-flight from data-onboard (intake → QA → go-live)
- **PDF stakeholder report** — ReportLab PDF: Executive Summary, Risk, Liquidity, FX Hedging, Data Health sections — generated on demand
- **Alert engine** — CRITICAL alerts for VaR limit breaches (`>3% NAV`) and open critical breaks (`>5`)

---

## Architecture

```
Upstream projects (read-only)      market-ops                    Outputs
─────────────────────────────      ──────────                    ───────
price-recon  (price_breaks)  ──┐
alpha-pipeline (positions,   ──┤──► db/database.py ──► api/routes.py ──► dashboard/
               snapshots,    ──┤         │                              index.html
               fx_forwards)  ──┤     aggregation                      (Chart.js)
market-data-hub (quality_    ──┤         │
               scores,       ──┤   reports/pdf.py ──► reports/output/
               vendor_sla)   ──┤                      market-ops-YYYY-MM-DD.pdf
data-onboard (vendor_        ──┘
              pipeline)
```

---

## Dashboard tabs

| Tab | Content |
|---|---|
| Breaks | Open price breaks by severity, asset class heat map |
| Positions | Portfolio P&L by asset class, liquidity tier breakdown |
| Catalogue | Vendor quality scorecards, SLA breach log, penalty calculator |
| Pipeline | Data-onboard vendor pipeline status by stage |

---

## Alert thresholds

| Alert | Threshold | Level |
|---|---|---|
| VaR 95% limit breach | >3% of NAV | CRITICAL |
| Open critical breaks | >5 unresolved | CRITICAL |
| Vendor feed stale | >2× SLA latency | WARNING |
| SLA uptime breach | <99.9% in 30-day window | WARNING |

---

## SLA penalty calculation

```
penalty_usd = breach_hours × 0.01 × monthly_vendor_fee_usd
```

Example: Bloomberg charges $24,000/year ($2,000/month). A 5-hour outage → `5 × 0.01 × $2,000 = $100` rebate owed.

---

## Acceptance criteria

- [x] Live aggregation from all 4 upstream projects via shared fund.db
- [x] Open breaks panel with severity classification
- [x] VaR and drawdown display with limit breach alerts
- [x] Vendor quality scorecard with SLA penalty engine
- [x] PDF stakeholder report (5 sections, ReportLab)
- [x] Active FX forwards with notional and forward rate

---

## Quick start

```bash
# 1. Clone and set up
git clone https://github.com/KeepingJones/MarketVentures.git
cd MarketVentures/market-ops
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — point SHARED_DB_PATH to the repo root fund.db

# 3. Start dashboard
python main.py
# Open http://localhost:8004

# 4. Generate PDF report
curl -X POST http://localhost:8004/api/report/generate
```

---

## Running tests

```bash
cd MarketVentures/market-ops
python -m pytest tests/ -v
```

Tests cover SLA penalty math, alert threshold logic, PDF data shape validation, and DB schema.

---

## Safety

`PAPER_TRADE_MODE = True` hardcoded in `config.py`. market-ops is read-only from upstream tables — it aggregates, never writes positions or trades.

---

## Part of the GBP fund portfolio ecosystem

| # | Project | What it adds |
|---|---|---|
| 1 | price-recon | Price validation, break detection, EOD Excel reporting |
| 2 | market-data-hub | Data catalogue, vendor registry, quality scoring |
| 3 | alpha-pipeline | Signal generation, risk, FX hedging, paper execution |
| 4 | data-onboard | Vendor onboarding workflow, coverage gap analysis |
| 5 | **market-ops** (this) | Unified operations dashboard, stakeholder PDF report |

---

## Stack

Python · FastAPI · SQLite (shared fund.db, read-only) · Chart.js · ReportLab
