-- Paper portfolio positions
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    currency TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_entry_price REAL NOT NULL,
    current_price REAL,
    market_value_gbp REAL,
    unrealised_pnl_gbp REAL DEFAULT 0,
    liquidity_tier TEXT,
    fx_hedge_ratio REAL DEFAULT 1.0,
    updated_at TEXT NOT NULL
);

-- Paper trades (executed orders)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    direction TEXT NOT NULL,    -- "buy" | "sell"
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    price_gbp REAL NOT NULL,    -- price converted to GBP
    value_gbp REAL NOT NULL,
    signal_source TEXT,         -- which signal triggered this
    broker TEXT NOT NULL,       -- "alpaca" | "internal_ledger"
    alpaca_order_id TEXT,
    timestamp TEXT NOT NULL
);

-- Portfolio snapshots (taken on each run)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nav_gbp REAL NOT NULL,
    peak_nav_gbp REAL NOT NULL,
    drawdown_pct REAL NOT NULL,
    var_95_gbp REAL,
    var_99_gbp REAL,
    stress_gfc_gbp REAL,
    stress_covid_gbp REAL,
    stress_rate_shock_gbp REAL,
    open_breaks INTEGER DEFAULT 0,
    critical_breaks INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL
);

-- Signal log — every signal generated
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    signal_type TEXT NOT NULL,      -- "momentum" | "mean_reversion" | "carry" | "trend" etc.
    direction TEXT NOT NULL,        -- "long" | "short" | "flat"
    confidence REAL NOT NULL,       -- 0.0–1.0
    price REAL NOT NULL,
    var_impact_gbp REAL,
    liquidity_tier TEXT,
    quality_gate_passed INTEGER DEFAULT 1,  -- 0 = blocked by price-recon break
    executed INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL
);

-- FX forward positions (simulated hedges)
CREATE TABLE IF NOT EXISTS fx_forwards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair TEXT NOT NULL,             -- e.g. "GBPUSD"
    notional_gbp REAL NOT NULL,
    spot_rate REAL NOT NULL,
    forward_rate REAL NOT NULL,
    tenor_days INTEGER NOT NULL,
    domestic_rate REAL NOT NULL,    -- SONIA
    foreign_rate REAL NOT NULL,     -- SOFR / ESTR / etc.
    pnl_gbp REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp);
