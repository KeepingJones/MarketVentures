# Architectural Decisions

Key decisions made during the build of MarketVentures, with rationale. Each entry is written to be defensible in an interview — "why did you choose X?" — not just "we used X."

---

## D1 — Shared SQLite database over per-project databases

**Decision:** All 5 projects read and write a single `fund.db` at the repo root.

**Why:** In a real fund, all these systems talk to the same data warehouse or operational DB. Cross-project queries (e.g. market-ops reading price breaks from price-recon AND positions from alpha-pipeline in a single aggregation) are much simpler when the data is co-located. SQLite is single-writer but that's fine for a paper portfolio with daily batch cadence — no concurrent write contention.

**Trade-off:** A production system would use Postgres (or KDB+ for tick data), with each service owning its schema via a migration tool. SQLite's lack of ALTER TABLE flexibility and single-writer limitation would bite under concurrent intraday load. If this were production, each project's tables would be partitioned into separate schemas in Postgres with a read-replica for market-ops.

---

## D2 — Per-project `pytest.ini` over root-level test config

**Decision:** Each project has its own `pytest.ini` with `pythonpath = .`, and tests are run from within each project directory.

**Why:** Both `price-recon/data/` and `alpha-pipeline/data/` are Python packages named `data`. Adding both parent directories to `sys.path` simultaneously (as a root `conftest.py` would) causes whichever is found first on the path to shadow the other. Per-project `pytest.ini` ensures each test run only sees one `data` package.

**Trade-off:** Can't run all tests from the repo root with a single `pytest` invocation. CI scripts run each project separately; this is explicit and avoids the collision.

---

## D3 — Bloomberg mock over skipping Bloomberg entirely

**Decision:** `price-recon/data/sources/bloomberg_mock.py` simulates B-PIPE pricing with realistic field names (`PX_LAST`, `BID`, `ASK`, `CRNCY`, `SECURITY_TYP`).

**Why:** Bloomberg awareness is a meaningful hiring signal for market data roles. Even without B-Pipe access, the mock shows that I know how the API works — the comments show the exact production swap-in. A recruiter or senior engineer reading the code sees immediately that this isn't someone who has never touched Bloomberg.

**Trade-off:** The mock uses Yahoo Finance as the base price + noise rather than fixed static prices. This means tests that call the mock depend on network availability for the Yahoo base. VaR and signal tests use completely mocked return series instead.

---

## D4 — Parametric VaR over historical simulation

**Decision:** `alpha-pipeline/risk/var.py` uses parametric (normal distribution) VaR rather than historical or Monte Carlo simulation.

**Why:** Parametric VaR is the industry standard for daily risk reports at funds that don't run intraday Greeks. It's fast (no resampling), well-understood by risk managers, and has an explicit, testable formula: `VaR = Z × σ × MV`. Historical simulation requires a full returns database going back 252+ days; for a paper portfolio that may have only run for a few days, parametric VaR is the only option that produces meaningful numbers.

**Trade-off:** Parametric VaR underestimates tail risk for fat-tailed distributions (equities, credit). Historical simulation or Monte Carlo would capture this better. The stress tests (GFC/COVID/rate shock) compensate by applying scenario-based P&L shocks that are explicitly tail events.

---

## D5 — Interest Rate Parity for FX forward pricing over a simpler proxy

**Decision:** `alpha-pipeline/risk/fx_hedge.py` prices FX forwards using the IRP formula: `F = S × (1 + r_d)^(T/365) / (1 + r_f)^(T/365)`, sourcing domestic (SONIA) and foreign (SOFR, ESTR) rates from FRED.

**Why:** IRP is the correct pricing model — it's arbitrage-free. A simpler approach (e.g. apply a flat 50bp forward premium) would be wrong and visible to any quant interviewer. Pulling live rates from FRED also demonstrates API integration and shows the hedge changes with the rate environment.

**Trade-off:** FRED rate series have a 1-day lag, so the forward price uses yesterday's rates. In production, you'd use Bloomberg or Refinitiv for real-time rate quotes. The error is small (rates change slowly) but it's documented.

---

## D6 — LangGraph for agent orchestration over a simple pipeline script

**Decision:** `alpha-pipeline/execution/agent.py` uses LangGraph to orchestrate the fetch → signal → risk → execute workflow as a typed state graph with named nodes.

**Why:** LangGraph is the correct tool for AI-adjacent agentic workflows that need conditional branching, retries, and a clear audit trail of which steps ran. It demonstrates familiarity with the LLM application engineering stack, which is increasingly relevant in quant/market data roles. The alternative (a sequential Python script) is simpler but can't branch on quality gate failures or be extended with LLM-generated signal explanations without a rewrite.

**Trade-off:** LangGraph adds a dependency and conceptual overhead for what is, in the current implementation, mostly a linear pipeline. The branching is limited. The payoff would be larger if we added an LLM node to generate plain-English trade rationale alongside the signal.

---

## D7 — Sharpe ratio vs SONIA (5.2%) not vs zero

**Decision:** `alpha-pipeline/risk/performance.py` uses the SONIA rate (5.2%) as the risk-free rate in Sharpe/Sortino calculations, not 0%.

**Why:** Sharpe ratio is only meaningful as a comparison to the risk-free return. For a GBP fund as of mid-2026, SONIA at ~5.2% is the correct benchmark — simply holding cash earns that. Using 0% would make any positive-return strategy look good regardless of whether it outperformed cash, which is not how institutions measure performance.

**Trade-off:** SONIA changes over time and is hardcoded. In production, `_RF_ANNUAL` would be read from the FRED SONIA series on startup. For a paper portfolio this is acceptable; for a live fund it would need to be updated at least weekly.

---

## D8 — OpenFIGI for instrument identifier mapping over a static lookup

**Decision:** `data-onboard/pipeline/intake.py` calls the OpenFIGI API to resolve vendor tickers to Bloomberg FIGIs during onboarding.

**Why:** Identifier management (SEDOL, ISIN, FIGI, vendor proprietary ID) is a real operational problem in market data. A new vendor might deliver data keyed by their own internal code; without a mapping to a standard identifier (FIGI, ISIN), you can't join it to the rest of the book. OpenFIGI is the free, Bloomberg-endorsed mapping service. Implementing this demonstrates awareness of the operational data problem, not just the quant problem.

**Trade-off:** OpenFIGI's free tier is rate-limited (10 requests/minute without a key, 25 with). For large instrument universes, batch submission and caching would be required. The current implementation batches in groups of 10 (the API limit) but doesn't cache results across runs.
