-- Vendor onboarding pipeline — one row per vendor per pipeline run
CREATE TABLE IF NOT EXISTS vendor_pipeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_name TEXT NOT NULL,
    vendor_id TEXT UNIQUE NOT NULL,       -- slug, e.g. "refinitiv_2024"
    contact_email TEXT,
    api_endpoint TEXT,
    claimed_asset_classes TEXT NOT NULL,  -- JSON array
    current_stage TEXT NOT NULL,          -- from config.PIPELINE_STAGES
    stage_status TEXT NOT NULL DEFAULT 'pending',  -- pending | pass | fail | in_progress
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Stage-level history — each stage transition recorded
CREATE TABLE IF NOT EXISTS pipeline_stage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendor_pipeline(vendor_id),
    stage TEXT NOT NULL,
    status TEXT NOT NULL,     -- pass | fail | in_progress
    notes TEXT,
    operator TEXT DEFAULT 'system',
    timestamp TEXT NOT NULL
);

-- QA assessment results per vendor
CREATE TABLE IF NOT EXISTS qa_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendor_pipeline(vendor_id),
    completeness_pct REAL NOT NULL,
    latency_minutes REAL NOT NULL,
    accuracy_pct REAL NOT NULL,
    overall_pass INTEGER NOT NULL,  -- 1 = pass, 0 = fail
    notes TEXT,
    assessed_at TEXT NOT NULL
);

-- OpenFIGI identifier mappings
CREATE TABLE IF NOT EXISTS figi_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendor_pipeline(vendor_id),
    vendor_ticker TEXT NOT NULL,
    figi TEXT,
    security_type TEXT,
    market_sector TEXT,
    match_status TEXT NOT NULL,   -- "matched" | "no_match" | "multiple_matches"
    mapped_at TEXT NOT NULL
);

-- Coverage gap analysis results
CREATE TABLE IF NOT EXISTS coverage_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id TEXT NOT NULL REFERENCES vendor_pipeline(vendor_id),
    asset_class TEXT NOT NULL,
    gap_type TEXT NOT NULL,       -- "new_coverage" | "duplicate" | "partial_overlap"
    notes TEXT,
    analysed_at TEXT NOT NULL
);

-- Alt data extracted signals (PDF → JSON)
CREATE TABLE IF NOT EXISTS alt_data_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    ticker TEXT,
    sentiment TEXT,
    revenue_guidance TEXT,
    earnings_surprise TEXT,
    key_risks TEXT,               -- JSON array
    source_type TEXT,
    confidence REAL,
    extracted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON vendor_pipeline(current_stage);
CREATE INDEX IF NOT EXISTS idx_stage_log_vendor ON pipeline_stage_log(vendor_id);
CREATE INDEX IF NOT EXISTS idx_qa_vendor ON qa_assessments(vendor_id);
