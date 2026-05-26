-- Database schema untuk multi-brand

CREATE TABLE IF NOT EXISTS brands (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) UNIQUE NOT NULL,
    brand_name VARCHAR(100) NOT NULL,
    jubelio_store_id VARCHAR(100),
    api_base_url VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) NOT NULL,
    jubelio_order_id VARCHAR(100) UNIQUE,
    order_number VARCHAR(100),
    total_price DECIMAL(15,2),
    status VARCHAR(50),
    channel VARCHAR(100),
    customer_name VARCHAR(200),
    customer_phone VARCHAR(50),
    order_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB,
    INDEX idx_orders_brand (brand_id),
    INDEX idx_orders_date (order_date)
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) NOT NULL,
    sku VARCHAR(100) UNIQUE,
    product_name VARCHAR(255),
    price DECIMAL(15,2),
    stock INTEGER,
    category VARCHAR(100),
    last_sync TIMESTAMP,
    raw_data JSONB,
    INDEX idx_products_brand (brand_id),
    INDEX idx_products_sku (sku)
);

CREATE TABLE IF NOT EXISTS stock_history (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) NOT NULL,
    sku VARCHAR(100),
    quantity INTEGER,
    warehouse VARCHAR(100),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB,
    INDEX idx_stock_brand_sku (brand_id, sku)
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(100) UNIQUE,
    order_id VARCHAR(100),
    amount DECIMAL(15,2),
    payment_method VARCHAR(50),
    transaction_date TIMESTAMP,
    raw_data JSONB,
    INDEX idx_transactions_brand (brand_id)
);

CREATE TABLE IF NOT EXISTS sync_logs (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR(50),
    data_type VARCHAR(50),
    status VARCHAR(20),
    records_count INTEGER,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    INDEX idx_logs_brand_date (brand_id, started_at)
);

CREATE TABLE IF NOT EXISTS tokens (
    brand_id VARCHAR(50) PRIMARY KEY,
    access_token TEXT,
    refresh_token TEXT,
    expires_at BIGINT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add SLA tables
CREATE TABLE IF NOT EXISTS sla_events (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    level VARCHAR(20) NOT NULL,
    duration FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL,
    threshold INT NOT NULL,
    warning_threshold INT NOT NULL,
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sla_metric_time (metric_name, event_time)
);

CREATE TABLE IF NOT EXISTS sla_daily_summary (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    total_events INT DEFAULT 0,
    breach_count INT DEFAULT 0,
    warning_count INT DEFAULT 0,
    avg_duration FLOAT,
    max_duration FLOAT,
    p95_duration FLOAT,
    sla_compliance_rate FLOAT,
    UNIQUE KEY unique_metric_date (metric_name, date)
);

-- Stored procedure untuk update daily SLA summary
CREATE OR REPLACE FUNCTION update_sla_daily_summary()
RETURNS void AS $$
BEGIN
    INSERT INTO sla_daily_summary (metric_name, date, total_events, breach_count, warning_count, avg_duration, max_duration, p95_duration, sla_compliance_rate)
    SELECT 
        metric_name,
        DATE(event_time) as date,
        COUNT(*) as total_events,
        SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as breach_count,
        SUM(CASE WHEN status = 'warning' THEN 1 ELSE 0 END) as warning_count,
        AVG(duration) as avg_duration,
        MAX(duration) as max_duration,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration) as p95_duration,
        (COUNT(*) - SUM(CASE WHEN status IN ('timeout', 'failed') THEN 1 ELSE 0 END))::float / COUNT(*) * 100 as sla_compliance_rate
    FROM sla_events
    WHERE DATE(event_time) = CURRENT_DATE - INTERVAL '1 day'
    GROUP BY metric_name, DATE(event_time)
    ON CONFLICT (metric_name, date) DO UPDATE SET
        total_events = EXCLUDED.total_events,
        breach_count = EXCLUDED.breach_count,
        warning_count = EXCLUDED.warning_count,
        avg_duration = EXCLUDED.avg_duration,
        max_duration = EXCLUDED.max_duration,
        p95_duration = EXCLUDED.p95_duration,
        sla_compliance_rate = EXCLUDED.sla_compliance_rate;
END;
$$ LANGUAGE plpgsql;