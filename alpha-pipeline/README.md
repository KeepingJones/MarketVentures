# alpha-pipeline — Multi-Asset Signal & Paper Trading Engine

**Business problem:** How does raw market data become a trading decision? A prop desk doesn't just buy when a price goes up — it runs the idea through a quality gate, generates a statistically validated signal, sizes it against VaR and liquidity limits, hedges the FX exposure, then routes to the broker. This project demonstrates the full front-office data lifecycle.

`alpha-pipeline` is a 5-strategy signal engine with parametric VaR, QuantLib Greeks, IRP-priced FX forwards, and a LangGraph orchestration layer — connected to Alpaca paper API for execution. No live capital. Ever.

**PAPER_TRADE_MODE = True is hardcoded in `config.py` and cannot be removed.**

---

## What it demonstrates

- **5 signal strategies** — equity momentum (z-score moving average), FX carry (interest rate differential), rates (yield curve slope), credit (spread compression), commodity trend
- **GBP-denominated fund** — all positions marked in GBP via live FX rates from FRED and ECB
- **FX hedging via IRP** — simulated FX forwards for USD/EUR/JPY exposure using `F = S × (1+r_d)^(T/365) / (1+r_f)^(T/365)` with SOFR vs SONIA from FRED
- **FX P&L attribution** — separates underlying asset performance from currency contribution
- **Parametric VaR** — 1-day 95%/99%, 252-day lookback, 0.5 average pairwise correlation for portfolio VaR
- **Options Greeks** — Delta, Gamma, Vega, Theta via QuantLib (BSM model), VIX regime gating
- **Stress testing** — GFC 2008, COVID 2020, Rate Shock 2022, GBP Crisis 1992
- **Performance attribution** — Sharpe ratio, Sortino ratio, CAGR vs SONIA (5.2%)
- **Data quality gate** — every feed validated before signal logic runs; quality_gate_passed flag on every signal
- **Liquidity control** — ADV-based position sizing (max 10% of 30-day ADV), days-to-liquidate, L1/L2/L3 tiers
- **LangGraph agent** — orchestrates fetch → quality → signal → risk → execute; each step is a typed graph node
- **Alpaca paper execution** — equities routed to Alpaca Paper API; FX/bonds/commodities use internal ledger

---

## Architecture

```
Market data                   Signal engine                         Outputs
───────────                   ─────────────                         ───────
yfinance  ──┐
fredapi   ──┤──► data/fetcher.py ──► signals/ ──► risk/var.py ──► db/ ──► api/
ECB API   ──┘         │               │               │
                      │         ┌─────┴──────┐   risk/fx_hedge.py
                data/quality    │            │   risk/performance.py
                _gate.py     equity_     fx_carry/              │
                             momentum/   rates/             ┌───┴──────────┐
                                         credit/       dashboard/     reports/
                                         commodity/   Streamlit UI   snapshot DB
                             │
                     execution/agent.py (LangGraph)
                             │
                    ┌────────┴──────────┐
               alpaca paper          internal
               (equities)            ledger (FX/bonds)
```

---

## Signal strategies

| Strategy | Asset class | Signal logic | Entry threshold |
|---|---|---|---|
| Equity momentum | Equities | MA(20) vs MA(60) z-score | z > 0.3 → long |
| FX carry | FX | Rate differential vs forward premium | carry > 1.5% → long high-yielder |
| Rates slope | Govt bonds | 10Y – 2Y spread vs EMA | spread widening → short duration |
| Credit compression | Corp bonds | ICE BofA spread vs 90-day avg | compression → risk-on |
| Commodity trend | Commodities | 20-day momentum vs vol-adj threshold | trend + vol low → long |

---

## Risk limits

| Metric | Limit | Enforcement |
|---|---|---|
| 1-day VaR 95% | 2% of NAV | Quality gate blocks signal if breached |
| Max drawdown | 15% of peak NAV | Agent halts execution |
| Single position | 10% of 30-day ADV | Position sizer enforced pre-trade |
| FX unhedged | 20% of NAV | FX forward auto-created on trade |

---

## Acceptance criteria

- [x] Live data ingestion across 5+ asset classes
- [x] GBP NAV calculated with FX conversion
- [x] FX forward hedge simulation with IRP pricing
- [x] FX P&L attribution (underlying vs currency)
- [x] VaR at position + portfolio level (95%/99%)
- [x] Options Greeks via QuantLib
- [x] Stress test under 4 scenarios (GFC/COVID/rate shock/GBP crisis)
- [x] Liquidity-adjusted position sizing enforced
- [x] LangGraph agent orchestrating signal → risk → execution
- [x] Performance dashboard: Sharpe, Sortino, CAGR, drawdown, total return
- [x] PAPER_TRADE_MODE = True visible in README

---

## Quick start

```bash
# 1. Clone and set up
git clone https://github.com/KeepingJones/MarketVentures.git
cd MarketVentures/alpha-pipeline
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — add ALPACA_API_KEY and ALPACA_SECRET_KEY (paper keys from alpaca.markets)
# Add FRED_API_KEY (free at fred.stlouisfed.org)

# 3. Initialise DB
python -c "from db.database import init_db; init_db()"

# 4. Run the agent (one cycle: fetch → signal → risk → execute → snapshot)
python main.py

# 5. Launch dashboard
streamlit run dashboard/app.py
# Open http://localhost:8501
```

---

## Running tests

```bash
cd MarketVentures/alpha-pipeline
python -m pytest tests/ -v
```

Tests cover VaR (position + portfolio + stress), signal direction/confidence, FX hedge IRP math, and performance attribution (Sharpe/Sortino/CAGR).

---

## Safety

`PAPER_TRADE_MODE = True` is hardcoded in `config.py`. All Alpaca calls go to `https://paper-api.alpaca.markets`. No live brokerage credentials are stored in this repo — see `.env.example` for the required variable names.

---

## Part of the GBP fund portfolio ecosystem

alpha-pipeline is project 3 of 5. All projects share a common SQLite database at the repo root.

| # | Project | What it adds |
|---|---|---|
| 1 | price-recon | Price validation, break detection, EOD Excel reporting |
| 2 | market-data-hub | Data catalogue, vendor registry, quality scoring |
| 3 | **alpha-pipeline** (this) | Signal generation, risk, FX hedging, paper execution |
| 4 | data-onboard | Vendor onboarding workflow, coverage gap analysis |
| 5 | market-ops | Unified operations dashboard, stakeholder PDF report |

---

## Stack

Python · LangGraph · QuantLib · yfinance · fredapi · ECB API · Alpaca Paper API · SQLite · Streamlit
