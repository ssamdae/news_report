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

CREATE INDEX IF NOT EXISTS idx_daily_price_trade_date
    ON daily_price (trade_date);

CREATE INDEX IF NOT EXISTS idx_signal_event_signal_date
    ON signal_event (signal_date);

CREATE INDEX IF NOT EXISTS idx_signal_event_stock_code
    ON signal_event (stock_code);

CREATE INDEX IF NOT EXISTS idx_job_run_started_at
    ON job_run (started_at);
