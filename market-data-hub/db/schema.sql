-- Vendor registry — all known data providers
CREATE TABLE IF NOT EXISTS vendors (
    id TEXT PRIMARY KEY,              -- e.g. "yahoo", "fred", "bloomberg"
    name TEXT NOT NULL,
    delivery TEXT NOT NULL,           -- "API (yfinance)", "REST API", "Server API"
    cost_usd_annual REAL DEFAULT 0,
    sla_latency_minutes INTEGER DEFAULT 15,
    status TEXT NOT NULL DEFAULT 'active',  -- active | inactive | onboarding
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Vendor coverage per asset class
CREATE TABLE IF NOT EXISTS vendor_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendors(id),
    asset_class TEXT NOT NULL
);

-- Dataset catalogue — individual data series catalogued
CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendors(id),
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    frequency TEXT NOT NULL,          -- "realtime" | "15min" | "daily" | "weekly"
    coverage TEXT,                    -- geographic/instrument coverage description
    licence_type TEXT NOT NULL,       -- from config.LICENCE_TYPES
    on_risk_path INTEGER DEFAULT 0,   -- 1 = VaR input / stress scenario / Greeks
    quality_score REAL,               -- 0.0–100.0, updated by quality_scorer
    last_scored_at TEXT,
    created_at TEXT NOT NULL
);

-- Live quality scores (one row per vendor per scoring run)
CREATE TABLE IF NOT EXISTS quality_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendors(id),
    freshness_score REAL NOT NULL,    -- 0–100: how recent is the data
    completeness_score REAL NOT NULL, -- 0–100: % fields populated
    accuracy_score REAL NOT NULL,     -- 0–100: deviation vs benchmark
    overall_score REAL NOT NULL,      -- weighted average
    latency_minutes REAL,             -- actual feed latency measured
    scored_at TEXT NOT NULL
);

-- Usage events — desk pulls a dataset
CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendors(id),
    dataset_id INTEGER REFERENCES datasets(id),
    desk TEXT NOT NULL,               -- from config.DESKS
    event_type TEXT NOT NULL,         -- "query" | "stream" | "download"
    records_fetched INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL
);

-- Entitlement checks — audit log of licence gate decisions
CREATE TABLE IF NOT EXISTS entitlement_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL,
    dataset_id INTEGER,
    desk TEXT NOT NULL,
    licence_type TEXT NOT NULL,
    allowed INTEGER NOT NULL,         -- 1 = permitted, 0 = blocked
    reason TEXT,
    timestamp TEXT NOT NULL
);

-- SLA uptime events — used by market-ops penalty engine
CREATE TABLE IF NOT EXISTS vendor_sla_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendors(id),
    event_type TEXT NOT NULL,         -- "outage_start" | "outage_end" | "latency_breach"
    duration_minutes REAL,
    notes TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quality_vendor ON quality_scores(vendor_id);
CREATE INDEX IF NOT EXISTS idx_usage_desk ON usage_events(desk);
CREATE INDEX IF NOT EXISTS idx_usage_vendor ON usage_events(vendor_id);
CREATE INDEX IF NOT EXISTS idx_datasets_vendor ON datasets(vendor_id);
CREATE INDEX IF NOT EXISTS idx_datasets_risk ON datasets(on_risk_path);
