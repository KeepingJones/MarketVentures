# GBP Fund Portfolio — Project Ecosystem

> Central index for all 5 market data portfolio projects.
> Full plan: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md`

---

## The story

Five projects. One shared database. One paper GBP fund.

The fund holds positions across equities, FX, government bonds, corporate bonds, credit, commodities, and equity options/derivatives. Everything runs on live data. All five projects serve or depend on the same central state in `C:\Users\ewanj\MarketVentures\fund.db`.

**Goal:** demonstrate the full market data operation — not just the tools, but the risk, liquidity, FX hedging, data quality, and stakeholder reporting that make it real. Target roles: prop trading, hedge funds, market data vendors.

---

## Project map

```
price-recon  ──────►  market-data-hub  ──────►  market-ops
    │                       │                        ▲
    │ (quality)         (catalogue)              (aggregates all)
    │                       │
    └──────────►  alpha-pipeline  ──────►  data-onboard
                  (signals/risk)        (vendor pipeline)
```

| # | Project | Port | Status | What it builds |
|---|---|---|---|---|
| 1 | [price-recon](price-recon/README.md) | 8000 | **Building** | EOD price reconciliation, break detection, Excel reports |
| 2 | [market-data-hub](market-data-hub/README.md) | 8001 | Scaffolded | Data catalogue, vendor registry, quality scoring |
| 3 | [alpha-pipeline](alpha-pipeline/README.md) | 8002 | Scaffolded | Signal generation, VaR, FX hedging, paper execution |
| 4 | [data-onboard](data-onboard/README.md) | 8003 | Scaffolded | Vendor onboarding pipeline, OpenFIGI validation |
| 5 | [market-ops](market-ops/README.md) | 8004 | Scaffolded | Unified ops dashboard, PDF stakeholder report |

---

## Shared database

**Path:** `C:\Users\ewanj\MarketVentures\fund.db`

All projects point to this via `SHARED_DB_PATH` in their `.env`. The schema is owned by each project (tables are namespaced by project). market-ops is read-only.

---

## API keys (already configured in each .env)

| Key | Where from | Used by |
|---|---|---|
| `FRED_API_KEY` | fred.stlouisfed.org | All projects (rates, macro, credit spreads) |
| `ALPACA_API_KEY` | paper-api.alpaca.markets | alpha-pipeline (paper equity execution) |
| `OLLAMA_*` | localhost:11434 | market-data-hub, data-onboard, alpha-pipeline (LLM) |

---

## Build order

1. **price-recon** — complete, runnable now
2. **market-data-hub** — next: `db/database.py`, `data/quality_scorer.py`, `api/routes.py`, `dashboard/`
3. **alpha-pipeline** — after hub: signals/, risk/var.py, risk/fx_hedge.py, execution/paper.py
4. **data-onboard** — after hub: pipeline/, qa/assessor.py, api/routes.py
5. **market-ops** — last: reads everything, builds the unified view

---

## To start any project

```bash
cd C:\Users\ewanj\MarketVentures\<project-name>
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Safety

`PAPER_TRADE_MODE = True` is hardcoded in every config.py. No live capital. Ever.

*Vault: C:\Users\ewanj\AI Context\AI Context\Job-Hunt\*
