-- Initialised automatically on first run by database.py

CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,   -- SHA256(company_lower + title_lower + apply_url)
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    company_size_raw TEXT,              -- raw string from scraper
    company_size_resolved INTEGER,      -- resolved headcount number (nullable)
    date_posted     TEXT,               -- ISO 8601 date
    salary_raw      TEXT,               -- raw salary string
    salary_min      INTEGER,
    salary_max      INTEGER,
    location        TEXT,
    is_remote       INTEGER DEFAULT 0,  -- 0/1 boolean
    apply_url       TEXT,
    source          TEXT,               -- scraper name
    description_raw TEXT,               -- raw job description (may be truncated)
    passed_filters  INTEGER,            -- NULL = not yet evaluated, 0 = failed, 1 = passed
    excluded_reason TEXT,               -- which filter rejected it
    status          TEXT DEFAULT 'open',  -- open | closed
    first_seen      TEXT,               -- ISO 8601 timestamp
    last_seen       TEXT,               -- ISO 8601 timestamp (updated each run)
    sheet_row       INTEGER             -- row number in Google Sheet (for updates)
);

CREATE TABLE IF NOT EXISTS leads (
    job_id                  TEXT PRIMARY KEY REFERENCES jobs(id),
    hiring_manager_name     TEXT,
    hiring_manager_title    TEXT,
    linkedin_url            TEXT,
    email                   TEXT,
    email_confidence        INTEGER,    -- 0-100
    enriched_at             TEXT,       -- ISO 8601 timestamp
    hunter_credits_used     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS company_cache (
    domain              TEXT PRIMARY KEY,
    company_name        TEXT,
    linkedin_url        TEXT,
    employee_count      INTEGER,
    employee_range      TEXT,
    resolved_at         TEXT            -- ISO 8601 timestamp
);

CREATE TABLE IF NOT EXISTS run_log (
    run_id          TEXT PRIMARY KEY,   -- YYYYMMDD_HHMMSS
    started_at      TEXT,
    finished_at     TEXT,
    jobs_found      INTEGER DEFAULT 0,
    jobs_new        INTEGER DEFAULT 0,
    jobs_closed     INTEGER DEFAULT 0,
    enriched        INTEGER DEFAULT 0,
    scraper_errors  TEXT,               -- JSON array of {scraper, error}
    flags           TEXT                -- JSON notes
);

CREATE INDEX IF NOT EXISTS idx_jobs_company   ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_status    ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_filters   ON jobs(passed_filters, status);
