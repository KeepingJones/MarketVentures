# MarketVentures — Development Standards

> Read this before adding any code to any project.
> Plan: `master-plan.md`
> Enhancement plan: `build-improve-learn.md`

---

## Project structure

```
MarketVentures/
├── PORTFOLIO.md          ← project map, shared DB, build order
├── DEVELOPMENT.md        ← this file
├── fund.db               ← shared SQLite database (auto-created on first run)
├── pyproject.toml        ← uv workspace root (TODO: migrate from requirements.txt)
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
├── shared/               ← shared Python package (TODO: extract from each project)
│   ├── models.py         ← Pydantic models — single source of truth
│   ├── schemas.py        ← Pandera validation schemas
│   ├── db.py             ← DB connection factory (SQLite write + DuckDB read)
│   ├── logging.py        ← structlog config
│   └── fx.py             ← FX forward pricing (interest rate parity)
├── price-recon/          port 8000  ← COMPLETE — build here first
├── market-data-hub/      port 8001  ← next
├── alpha-pipeline/       port 8002
├── data-onboard/         port 8003
└── market-ops/           port 8004  ← last, reads everything
```

---

## Shared database

**Path:** `C:\Users\ewanj\MarketVentures\fund.db`

Every project reads the path from `SHARED_DB_PATH` env var (set in each `.env`). Default fallback is the absolute path above.

**Two-layer DB strategy:**
- **SQLite** — all writes (quotes, breaks, positions, trades, events). Transactional, reliable.
- **DuckDB** — all reads for dashboards and analytics. Attach the SQLite file and query it with columnar performance.

```python
# Analytics queries — always use DuckDB
import duckdb
conn = duckdb.connect()
conn.execute(f"ATTACH '{DB_PATH}' AS fund (TYPE SQLITE)")
df = conn.execute("SELECT asset_class, AVG(diff_pct) FROM fund.price_breaks GROUP BY 1").df()
```

Do not use SQLite for dashboard aggregations. The performance difference on large tables is 10-100x.

---

## Code standards

### Linting and formatting

All code must pass `ruff check .` and `ruff format .` before commit.

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]
```

Run: `uvx ruff check . --fix && uvx ruff format .`

### Type hints

All function signatures must have type hints. Run `mypy <project>/` — zero errors expected on new code.

### No bare `except`

Always catch specific exceptions. `except Exception as e: logger.error(...)` is the minimum.

---

## Data validation

Every DataFrame entering the system must be validated against a Pandera schema before processing.

```python
from shared.schemas import PriceQuoteSchema
import pandera.pandas as pa

@pa.check_types
def process_quotes(df: pa.typing.DataFrame[PriceQuoteSchema]) -> list[PriceBreak]:
    ...
```

Schema violations are treated as `DATA_QUALITY` breaks — not silently dropped.

**Key schemas (in `shared/schemas.py`):**

| Schema | Validates | Used in |
|---|---|---|
| `PriceQuoteSchema` | ticker, price > 0, valid source, valid asset_class | price-recon, alpha-pipeline |
| `FXRateSchema` | pair format, rate > 0, source | price-recon, alpha-pipeline |
| `PositionSchema` | ticker, quantity, market_value_gbp, liquidity_tier | alpha-pipeline, market-ops |
| `BreakSchema` | diff_pct >= 0, valid severity, valid cause | price-recon, market-ops |

---

## Logging

All projects use `structlog` with JSON output. No `print()` statements in production paths.

```python
import structlog
log = structlog.get_logger()

# Every significant event is a structured log
log.info("recon_run_complete",
         breaks=len(breaks),
         critical=sum(1 for b in breaks if b.severity == "CRITICAL"),
         duration_ms=elapsed_ms,
         sources=["yahoo", "fred", "ecb"])
```

---

## Testing

Every project needs tests before it's considered done. Minimum coverage: **60% on business logic modules**.

Test locations: `<project>/tests/`

```
price-recon/tests/
├── conftest.py              ← shared fixtures (mock quotes, mock breaks)
├── test_classifier.py       ← unit tests for all 7 break cause paths
├── test_liquidity.py        ← L1/L2/L3 tier assignment, tolerance scaling
├── test_engine.py           ← reconciliation with mocked source responses
└── test_excel.py            ← Excel report generates without error
```

Run: `uv run pytest price-recon/tests/ -v --tb=short`

**Fixture pattern — mock external API calls, never hit live APIs in tests:**
```python
@pytest.fixture
def mock_yahoo_response(monkeypatch):
    def fake_download(*args, **kwargs):
        return pd.DataFrame({"Close": [185.50, 185.60]})
    monkeypatch.setattr("yfinance.download", fake_download)
```

---

## Architecture patterns

### Adding a new data source

1. Create `data/sources/<name>.py` with a `get_quotes() -> list[PriceQuote]` function
2. Apply `PriceQuoteSchema` validation before returning
3. Add to `recon/engine.py` fetch loop
4. Add to `config.py` INSTRUMENTS or FRED_SERIES_MAP

### Adding a new API endpoint

1. Add route to `api/routes.py`
2. Route must return typed Pydantic response model
3. Add to `health` endpoint response (`"endpoints": [...]`)

### Adding a new DB table

1. Add `CREATE TABLE IF NOT EXISTS` to `db/schema.sql`
2. Add read/write functions to `db/database.py`
3. Test with a fixture that calls `init_db()` on a temp SQLite file

---

## Pre-commit setup

Install once per machine:
```bash
pip install pre-commit
pre-commit install
```

Hooks run on every `git commit`:
- `ruff` — lint + format
- `mypy` — type check
- `no-commit-to-main` — force feature branches

---

## CI (GitHub Actions)

On every push: ruff → mypy → pytest. See `.github/workflows/ci.yml`.

Badge in PORTFOLIO.md README: `![CI](https://github.com/KeepingJones/MarketVentures/actions/workflows/ci.yml/badge.svg)`

---

## Safety

`PAPER_TRADE_MODE = True` is hardcoded in every `config.py`.

If you ever see `PAPER_TRADE_MODE = False` in a diff, reject it. No live capital. Ever.

---

## What this portfolio demonstrates

| Feature | What it signals to a hiring manager |
|---|---|
| Pandera schemas | Production data quality thinking, not just happy-path code |
| DuckDB analytics layer | Architectural judgement — right tool for the job |
| structlog JSON logging | Built for observability, not just debugging |
| Pre-commit + ruff + mypy | Code hygiene, CI-ready, team-ready |
| pytest with mocked APIs | Tests that don't break when Yahoo Finance is down |
| Redis Pub/Sub in market-ops | Understands event-driven architecture |
| Docker compose | Anyone can clone and run it in 5 minutes |
| Mermaid diagrams | Communicates architecture clearly without Confluence |
| Entitlements engine | Knows the compliance layer exists, not just the data layer |
| "Why not KDB+?" in README | Aware of the industry standard, made an informed choice |
