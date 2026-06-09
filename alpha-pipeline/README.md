# alpha-pipeline — Live Multi-Asset Signal & Paper Trading Engine

**Business problem:** How does raw market data actually become a trading decision? This is the full data lifecycle from a front office perspective — ingestion → quality gate → signal → risk check → paper execution → performance attribution.

`alpha-pipeline` is a rebuild of Alpha Command (`C:\Users\ewanj\trading-bot`), extended to cover all asset classes with proper risk, liquidity, and FX hedging layers.

**PAPER_TRADE_MODE = True. No live capital. Ever.**

---

## Vault plan

Full spec: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\master-plan.md` (Project 3)
Portfolio plan: `C:\Users\ewanj\AI Context\AI Context\Job-Hunt\portfolio-plan.md`
Prior work to reuse: `C:\Users\ewanj\trading-bot` — risk, position sizing, LangGraph patterns

---

## How it links to the other projects

```
price-recon    → quality gates: bad prices suppress signals
market-data-hub → catalogue gates: only use quality-scored datasets
alpha-pipeline ← YOU ARE HERE — consumes data, generates signals, papers trades
data-onboard   → new vendors flow into market-data-hub, then here
market-ops     → reads paper portfolio positions, P&L, VaR, Greeks for live display
```

Shared database: `C:\Users\ewanj\fund.db` — writes positions, trades, P&L, VaR here.

---

## What it demonstrates

- **Live multi-asset ingestion** — equities, FX, govt bonds/rates, credit spreads, commodity futures, equity options chains
- **GBP-denominated fund** — all positions marked in GBP via live FX rates
- **FX hedging** — simulated FX forwards for USD/EUR/JPY exposure using interest rate parity (spot + SOFR vs SONIA differential from FRED)
- **FX P&L attribution** — separates underlying asset performance from currency contribution
- **Data quality gate** — every feed validated before reaching signal logic
- **Signal generation** — equities (momentum/mean reversion), FX (carry), rates (yield curve slope), credit (spread compression), commodities (trend), options (VIX vol regime)
- **Risk** — parametric VaR (1-day 95%/99%), Options Greeks via QuantLib, stress testing (GFC/COVID/rate shock)
- **Liquidity** — ADV-based position sizing (max 10% of 30-day ADV), days-to-liquidate, L1/L2/L3 classification (reused from price-recon)
- **LangGraph orchestration** — agent cross-checks quality, signal confidence, VaR impact, liquidity before routing to execution
- **Paper execution** — Alpaca Paper API for equities, internal ledger for FX/bonds/commodities

---

## Key files from trading-bot to reuse

| File | Pattern |
|---|---|
| `C:\Users\ewanj\trading-bot\risk\portfolio_risk.py` | VaR, stress testing, drawdown control |
| `C:\Users\ewanj\trading-bot\src\quant\position_sizing.py` | Kelly, volatility targeting |
| `C:\Users\ewanj\trading-bot\src\data\price_cache.py` | 5-min TTL cache pattern |
| `C:\Users\ewanj\trading-bot\src\agent\nodes\` | LangGraph node patterns |
| `C:\Users\ewanj\trading-bot\config.py` | Config + env var pattern |

---

## Acceptance criteria

- [ ] Live data ingestion across 5+ asset classes
- [ ] GBP NAV calculated with FX conversion
- [ ] FX forward hedge simulation with IRP pricing
- [ ] VaR at position + portfolio level (95%/99%)
- [ ] Options Greeks via QuantLib
- [ ] Stress test under 3 scenarios
- [ ] Liquidity-adjusted position sizing enforced
- [ ] LangGraph agent orchestrating signal → risk → execution
- [ ] PAPER_TRADE_MODE = True visible in README
- [ ] Performance dashboard: Sharpe, drawdown, signal attribution by asset class

---

## Quick start

```bash
cd C:\Users\ewanj\alpha-pipeline
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -c "from db.database import init_db; init_db()"
python main.py
# Dashboard: http://localhost:8002
```

---

## Stack

Python · LangGraph · QuantLib · yfinance · fredapi · ECB API · Alpaca Paper API · SQLite (shared fund.db) · Streamlit

**Depends on:** price-recon (quality gates), market-data-hub (catalogue)
