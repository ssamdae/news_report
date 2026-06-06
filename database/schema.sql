CREATE TABLE IF NOT EXISTS stock_master (
    stock_code VARCHAR(20) PRIMARY KEY,
    stock_name VARCHAR(255) NOT NULL,
    market VARCHAR(20) NOT NULL,
    sector VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    listed_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stock_keyword_map (
    id BIGSERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL REFERENCES stock_master(stock_code),
    keyword TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (stock_code, keyword)
);

CREATE TABLE IF NOT EXISTS daily_price (
    stock_code VARCHAR(20) NOT NULL REFERENCES stock_master(stock_code),
    trade_date DATE NOT NULL,
    open_price NUMERIC(20, 2) NOT NULL,
    high_price NUMERIC(20, 2) NOT NULL,
    low_price NUMERIC(20, 2) NOT NULL,
    close_price NUMERIC(20, 2) NOT NULL,
    prev_close_price NUMERIC(20, 2),
    volume BIGINT NOT NULL,
    trading_value NUMERIC(20, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (stock_code, trade_date)
);

CREATE TABLE IF NOT EXISTS signal_event (
    id BIGSERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL REFERENCES stock_master(stock_code),
    signal_date DATE NOT NULL,
    signal_name VARCHAR(50) NOT NULL,
    condition_version VARCHAR(20) NOT NULL DEFAULT 'v1',
    trading_value NUMERIC(20, 2),
    close_price NUMERIC(20, 2),
    volume BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (signal_date, stock_code, signal_name)
);

CREATE TABLE IF NOT EXISTS job_run (
    id BIGSERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    target_date DATE,
    status VARCHAR(30) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    collected_count INTEGER NOT NULL DEFAULT 0,
    signal_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS news_article (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20),
    stock_name VARCHAR(100),
    title TEXT,
    link TEXT UNIQUE,
    published_at TIMESTAMP,
    source VARCHAR(100),
    keyword TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pdf_signal_item (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE,
    theme_name TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    change_rate NUMERIC(10, 2),
    trading_value NUMERIC(20, 2),
    pdf_file_name TEXT NOT NULL,
    raw_line TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (
        pdf_file_name,
        theme_name,
        stock_name,
        change_rate,
        trading_value
    )
);

CREATE TABLE IF NOT EXISTS theme_master (
    id BIGSERIAL PRIMARY KEY,
    theme_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS theme_alias (
    id BIGSERIAL PRIMARY KEY,
    alias_name TEXT NOT NULL UNIQUE,
    theme_id BIGINT REFERENCES theme_master(id),
    canonical_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE theme_alias
    ALTER COLUMN theme_id DROP NOT NULL;

ALTER TABLE theme_alias
    ADD COLUMN IF NOT EXISTS canonical_name TEXT;

UPDATE theme_alias
SET canonical_name = alias_name
WHERE canonical_name IS NULL;

ALTER TABLE theme_alias
    ALTER COLUMN canonical_name SET NOT NULL;

CREATE TABLE IF NOT EXISTS stock_theme_map (
    id BIGSERIAL PRIMARY KEY,
    stock_name TEXT NOT NULL,
    theme_id BIGINT NOT NULL REFERENCES theme_master(id),
    first_seen_date DATE,
    last_seen_date DATE,
    hit_count INTEGER NOT NULL DEFAULT 0,
    avg_change_rate NUMERIC(10, 2),
    max_change_rate NUMERIC(10, 2),
    total_trading_value NUMERIC(24, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (stock_name, theme_id)
);

CREATE TABLE IF NOT EXISTS stock_canonical_theme_map (
    id BIGSERIAL PRIMARY KEY,
    stock_name TEXT NOT NULL,
    canonical_theme TEXT NOT NULL,
    first_seen_date DATE,
    last_seen_date DATE,
    hit_count INTEGER NOT NULL DEFAULT 0,
    avg_change_rate NUMERIC(10, 2),
    max_change_rate NUMERIC(10, 2),
    total_trading_value NUMERIC(24, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (stock_name, canonical_theme)
);

CREATE INDEX IF NOT EXISTS idx_daily_price_trade_date
    ON daily_price (trade_date);

CREATE INDEX IF NOT EXISTS idx_signal_event_signal_date
    ON signal_event (signal_date);

CREATE INDEX IF NOT EXISTS idx_signal_event_stock_code
    ON signal_event (stock_code);

CREATE INDEX IF NOT EXISTS idx_job_run_started_at
    ON job_run (started_at);

CREATE INDEX IF NOT EXISTS idx_news_article_stock_code
    ON news_article (stock_code);

CREATE INDEX IF NOT EXISTS idx_news_article_created_at
    ON news_article (created_at);

CREATE INDEX IF NOT EXISTS idx_stock_keyword_map_stock_code
    ON stock_keyword_map (stock_code);

CREATE INDEX IF NOT EXISTS idx_stock_keyword_map_active
    ON stock_keyword_map (is_active);

CREATE INDEX IF NOT EXISTS idx_pdf_signal_item_report_date
    ON pdf_signal_item (report_date);

CREATE INDEX IF NOT EXISTS idx_pdf_signal_item_stock_name
    ON pdf_signal_item (stock_name);

CREATE INDEX IF NOT EXISTS idx_theme_alias_theme_id
    ON theme_alias (theme_id);

CREATE INDEX IF NOT EXISTS idx_theme_alias_canonical_name
    ON theme_alias (canonical_name);

CREATE INDEX IF NOT EXISTS idx_stock_theme_map_theme_id
    ON stock_theme_map (theme_id);

CREATE INDEX IF NOT EXISTS idx_stock_theme_map_stock_name
    ON stock_theme_map (stock_name);

CREATE INDEX IF NOT EXISTS idx_stock_theme_map_hit_count
    ON stock_theme_map (hit_count DESC);

CREATE INDEX IF NOT EXISTS idx_stock_canonical_theme_map_canonical_theme
    ON stock_canonical_theme_map (canonical_theme);

CREATE INDEX IF NOT EXISTS idx_stock_canonical_theme_map_stock_name
    ON stock_canonical_theme_map (stock_name);

CREATE INDEX IF NOT EXISTS idx_stock_canonical_theme_map_hit_count
    ON stock_canonical_theme_map (hit_count DESC);
