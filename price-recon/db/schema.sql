-- Price quotes from each source
CREATE TABLE IF NOT EXISTS price_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    source TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    currency TEXT NOT NULL,
    price REAL NOT NULL,
    bid REAL,
    ask REAL,
    volume INTEGER,
    timestamp TEXT NOT NULL,
    is_stale INTEGER DEFAULT 0
);

-- Reconciliation breaks
CREATE TABLE IF NOT EXISTS price_breaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    source_a TEXT NOT NULL,
    source_b TEXT NOT NULL,
    price_a REAL NOT NULL,
    price_b REAL NOT NULL,
    diff_pct REAL NOT NULL,
    tolerance_pct REAL NOT NULL,
    break_cause TEXT NOT NULL,
    severity TEXT NOT NULL,  -- INFO | WARNING | CRITICAL
    timestamp TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    resolved_at TEXT,
    resolved_by TEXT
);

-- FX rates
CREATE TABLE IF NOT EXISTS fx_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair TEXT NOT NULL,
    rate REAL NOT NULL,
    source TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- Instrument reference (populated from config)
CREATE TABLE IF NOT EXISTS instruments (
    ticker TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL,
    currency TEXT NOT NULL,
    name TEXT NOT NULL,
    liquidity_tier TEXT,
    adv_usd_30d REAL
);

-- Daily reconciliation run summary
CREATE TABLE IF NOT EXISTS recon_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    total_instruments INTEGER NOT NULL,
    total_breaks INTEGER NOT NULL,
    critical_breaks INTEGER NOT NULL,
    warning_breaks INTEGER NOT NULL,
    info_breaks INTEGER NOT NULL,
    sources_used TEXT NOT NULL,  -- JSON array
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_breaks_ticker ON price_breaks(ticker);
CREATE INDEX IF NOT EXISTS idx_breaks_severity ON price_breaks(severity);
CREATE INDEX IF NOT EXISTS idx_breaks_resolved ON price_breaks(resolved);
CREATE INDEX IF NOT EXISTS idx_quotes_ticker ON price_quotes(ticker);
CREATE INDEX IF NOT EXISTS idx_quotes_timestamp ON price_quotes(timestamp);
