# market-ops — Live Market Data Operations Dashboard

**Business problem:** The Head of Market Data, COO, and CRO each need a different view of the same data — but there's no single system that shows feed health, risk exposure, liquidity profile, FX hedging status, and open price breaks in one place.

`market-ops` is the unified operations dashboard that ties all four other projects together — the centrepiece that a stakeholder actually looks at every morning.

---

## Vault plan

Full spec: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md` (Project 5)
Portfolio plan: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\portfolio-plan.md`

---

## How it links to the other projects

```
price-recon    → open breaks panel, exception tracker
market-data-hub → feed health board, vendor SLA tracker, dataset quality panel
alpha-pipeline  → portfolio NAV, VaR, Greeks, stress test P&L, FX hedge status
data-onboard   → vendor onboarding pipeline status
market-ops     ← YOU ARE HERE — reads all of the above via shared fund.db
```

Shared database: `C:\Users\ewanj\fund.db` — reads everything, writes nothing (pure aggregation layer).

---

## What it demonstrates

- **Live pricing panel** — all asset classes updating every few minutes
- **Credit data** — ICE BofA IG/HY spreads live from FRED, mock Bloomberg CRAT ratings feed
- **Derivatives monitor** — VIX term structure, equity options IV vs historical vol
- **Feed health board** — green/amber/red per source, latency vs SLA
- **SLA Penalty & Vendor Spend Analytics** — tracks actual vendor uptime against contractual SLA (e.g. 99.9%). Automatically calculates commercial penalty/rebate owed when a vendor breaches their SLA. The number nobody currently builds but every fund CFO wants.
- **Risk dashboard** — portfolio VaR (95%/99%), Greeks by asset class, stress P&L, limit breach alerts
- **Liquidity panel** — L1/L2/L3 breakdown, days-to-liquidate, liquidity stress scenario
- **FX/hedging panel** — GBP NAV live, currency exposure (hedged vs unhedged), hedge effectiveness, forward roll calendar
- **Exception tracker** — live breaks from price-recon, open vs resolved
- **PDF stakeholder report** — executive summary (NAV, P&L, risk vs limits, data health), risk section, liquidity, FX, data health — designed for Head of Market Data and COO via ReportLab

---

## Acceptance criteria

- [ ] All asset classes live in pricing panel
- [ ] VaR, Greeks, stress test live and updating
- [ ] Liquidity L1/L2/L3 visible
- [ ] FX hedging panel with GBP NAV and residual exposure
- [ ] PDF report generates cleanly with all sections
- [ ] Breaks feed from price-recon via shared DB
- [ ] All panels chart-first, not table-first

---

## Quick start

```bash
cd C:\Users\ewanj\market-ops
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py
# Dashboard: http://localhost:8004
```

---

## Stack

Python · FastAPI · React · WebSockets · SQLite (shared fund.db) · Chart.js · yfinance · fredapi · QuantLib · ReportLab

**Depends on:** All 4 prior projects must be running and writing to fund.db
