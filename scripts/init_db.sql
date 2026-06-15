-- Day 04 eComBot seed schema.
-- Runs automatically the first time the Postgres container initializes.

CREATE TABLE IF NOT EXISTS orders (
    order_id        VARCHAR(20) PRIMARY KEY,
    customer_name   VARCHAR(100) NOT NULL,
    status          VARCHAR(30) NOT NULL,
    eta             VARCHAR(50) NOT NULL,
    carrier         VARCHAR(50) NOT NULL,
    product_id      VARCHAR(20) NOT NULL,
    product_name    VARCHAR(100) NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 1,
    total_amount    NUMERIC(10,2) NOT NULL,
    currency        VARCHAR(10) NOT NULL DEFAULT 'INR',
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products (
    product_id      VARCHAR(20) PRIMARY KEY,
    product_name    VARCHAR(100) NOT NULL,
    category        VARCHAR(50) NOT NULL,
    price           NUMERIC(10,2) NOT NULL,
    currency        VARCHAR(10) NOT NULL DEFAULT 'INR',
    stock_status    VARCHAR(30) NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT true,
    description     TEXT NOT NULL,
    warranty        VARCHAR(100) NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_history (
    id          BIGSERIAL PRIMARY KEY,
    session_id  VARCHAR(100) NOT NULL,
    user_id     VARCHAR(100) NOT NULL,
    role        VARCHAR(20) NOT NULL,
    content     TEXT NOT NULL,
    tool_calls  JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_history_session
    ON session_history (session_id, created_at);

INSERT INTO products (
    product_id, product_name, category, price, currency, stock_status, active,
    description, warranty
)
VALUES
    ('PRD-101', 'Galaxy A55 5G', 'phone', 38999.00, 'INR', 'In Stock', true,
     'Mid-range Android phone with AMOLED display and 5G support.', '1 year manufacturer warranty'),
    ('PRD-102', 'Redmi Note 13 Pro', 'phone', 24999.00, 'INR', 'In Stock', true,
     'Value-focused Android phone with high-refresh display and fast charging.', '1 year manufacturer warranty'),
    ('PRD-103', 'StreamMax 4K TV Decoder', 'tv decoder', 4999.00, 'INR', 'Out of Stock', true,
     '4K streaming decoder for smart TV and OTT apps.', '6 months service warranty'),
    ('PRD-104', 'BassPro Wireless Earbuds', 'accessory', 2999.00, 'INR', 'In Stock', true,
     'Bluetooth earbuds with charging case and noise reduction.', '6 months accessory warranty'),
    ('PRD-105', 'OldGen HDMI Adapter', 'accessory', 799.00, 'INR', 'Inactive', false,
     'Legacy HDMI adapter retained for failure-path tests.', 'No active warranty')
ON CONFLICT (product_id) DO NOTHING;

INSERT INTO orders (
    order_id, customer_name, status, eta, carrier, product_id, product_name,
    quantity, total_amount, currency
)
VALUES
    ('ORD-001', 'Priya Sharma', 'Shipped', '5 Jun 2026', 'BlueDart',
     'PRD-101', 'Galaxy A55 5G', 1, 38999.00, 'INR'),
    ('ORD-002', 'Priya Sharma', 'Processing', '7 Jun 2026', 'DTDC',
     'PRD-104', 'BassPro Wireless Earbuds', 2, 5998.00, 'INR'),
    ('ORD-003', 'Ravi Patel', 'Delivered', 'Already delivered', 'FedEx',
     'PRD-102', 'Redmi Note 13 Pro', 1, 24999.00, 'INR'),
    ('ORD-004', 'Aisha Mehta', 'Cancelled', 'Not applicable', 'None',
     'PRD-103', 'StreamMax 4K TV Decoder', 1, 4999.00, 'INR'),
    ('ORD-005', 'Kenji Tanaka', 'Return Requested', 'Under review', 'Ecom Returns',
     'PRD-104', 'BassPro Wireless Earbuds', 1, 2999.00, 'INR')
ON CONFLICT (order_id) DO NOTHING;
