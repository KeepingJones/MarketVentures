-- market-ops is READ-ONLY from all upstream tables.
-- Only tables it owns: SLA events and fund snapshots for the ops dashboard.

-- SLA outage events logged by market-ops (observing vendor feed health)
CREATE TABLE IF NOT EXISTS ops_sla_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,       -- "outage_start" | "outage_end" | "latency_breach"
    duration_minutes REAL,
    feed_latency_minutes REAL,
    notes TEXT,
    timestamp TEXT NOT NULL
);

-- Fund NAV snapshots for ops reporting (duplicated subset from alpha-pipeline for fast reads)
CREATE TABLE IF NOT EXISTS ops_fund_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nav_gbp REAL NOT NULL,
    peak_nav_gbp REAL NOT NULL,
    drawdown_pct REAL NOT NULL,
    var_95_gbp REAL,
    var_99_gbp REAL,
    open_breaks INTEGER DEFAULT 0,
    critical_breaks INTEGER DEFAULT 0,
    active_vendors INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ops_sla_vendor ON ops_sla_events(vendor_id);
CREATE INDEX IF NOT EXISTS idx_ops_sla_ts ON ops_sla_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_ops_fund_ts ON ops_fund_snapshots(timestamp);
