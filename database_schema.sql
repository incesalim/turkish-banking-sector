-- BDDK Banking Data - Database Schema
-- Hybrid approach: Combination of raw storage and normalized tables
-- Database: SQLite/PostgreSQL compatible

-- ============================================================================
-- 1. RAW DATA STORAGE (Complete API responses)
-- ============================================================================

CREATE TABLE IF NOT EXISTS raw_api_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    bank_type_code VARCHAR(10) NOT NULL,
    bank_type_name VARCHAR(100),
    response_json TEXT NOT NULL,  -- Full JSON response
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_number, year, month, currency, bank_type_code)
);

CREATE INDEX idx_raw_period ON raw_api_responses(year, month);
CREATE INDEX idx_raw_table ON raw_api_responses(table_number);

-- ============================================================================
-- 2. METADATA & REFERENCE TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS bank_types (
    code VARCHAR(10) PRIMARY KEY,
    name_tr VARCHAR(100) NOT NULL,
    name_en VARCHAR(100),
    category VARCHAR(50),  -- 'sector', 'deposit', 'participation', etc.
    description TEXT
);

INSERT OR IGNORE INTO bank_types (code, name_tr, name_en, category) VALUES
('10001', 'Sektör', 'Entire Sector', 'sector'),
('10002', 'Mevduat', 'Deposit Banks', 'deposit'),
('10003', 'Katılım', 'Participation Banks', 'participation'),
('10004', 'Kalkınma ve Yatırım', 'Development & Investment Banks', 'development'),
('10005', 'Yerli Özel', 'Local Private Banks', 'private'),
('10006', 'Kamu', 'State Banks', 'state'),
('10007', 'Yabancı', 'Foreign Banks', 'foreign'),
('10008', 'Mevduat-Yerli Özel', 'Deposit Banks - Local Private', 'deposit_private'),
('10009', 'Mevduat-Kamu', 'Deposit Banks - State', 'deposit_state'),
('10010', 'Mevduat-Yabancı', 'Deposit Banks - Foreign', 'deposit_foreign');

CREATE TABLE IF NOT EXISTS table_definitions (
    table_number INTEGER PRIMARY KEY,
    name_tr VARCHAR(200) NOT NULL,
    name_en VARCHAR(200),
    description TEXT,
    unit VARCHAR(50),  -- 'million TL', 'thousand TL', 'percentage', 'count'
    typical_rows INTEGER,
    category VARCHAR(50)
);

INSERT OR IGNORE INTO table_definitions VALUES
(1, 'Bilanço', 'Balance Sheet', 'Main balance sheet items', 'million TL', 62, 'balance_sheet'),
(2, 'Kar Zarar', 'Income Statement', 'Profit and loss statement', 'million TL', 53, 'income_statement'),
(3, 'Krediler', 'Loans', 'Loan breakdown by maturity', 'million TL', 20, 'loans'),
(4, 'Tüketici Kredileri', 'Consumer Loans', 'Consumer loan details', 'million TL', 41, 'loans'),
(5, 'Sektörel Kredi Dağılımı', 'Sectoral Loan Distribution', 'Loans by economic sector', 'thousand TL', 70, 'loans'),
(6, 'KOBİ Kredileri', 'SME Loans', 'Small and medium enterprise loans', 'million TL', 8, 'loans'),
(7, 'Sendikasyon Seküritizasyon', 'Syndication & Securitization', 'Syndicated loans', 'million TL', 3, 'loans'),
(8, 'Menkul Kıymetler', 'Securities', 'Securities portfolio', 'million TL', 29, 'securities'),
(9, 'Mevduat Türler İtibarıyla', 'Deposits by Type', 'Deposits by amount bracket', 'million TL', 26, 'deposits'),
(10, 'Mevduat Vade İtibarıyla', 'Deposits by Maturity', 'Deposits by maturity', 'million TL', 24, 'deposits'),
(11, 'Likidite Durumu', 'Liquidity Position', 'Liquidity gap analysis', 'million TL', 44, 'liquidity'),
(12, 'Sermaye Yeterliliği', 'Capital Adequacy', 'Capital adequacy components', 'million TL', 31, 'capital'),
(13, 'Yabancı Para Pozisyonu', 'FX Position', 'Foreign currency position', 'million TL', 11, 'fx'),
(14, 'Bilanço Dışı İşlemler', 'Off-Balance Sheet', 'Off-balance sheet items', 'million TL', 52, 'off_balance'),
(15, 'Rasyolar', 'Ratios', 'Key financial ratios', 'percentage', 32, 'ratios'),
(16, 'Diğer Bilgiler', 'Other Information', 'Additional metadata', 'count', 7, 'metadata'),
(17, 'Yurt Dışı Şube Rasyoları', 'Foreign Branch Ratios', 'Foreign branch metrics', 'percentage', 3, 'ratios');

-- ============================================================================
-- 3. NORMALIZED CORE TABLES
-- ============================================================================

-- 3.1 Balance Sheet (Table 1)
CREATE TABLE IF NOT EXISTS balance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    bank_type_code VARCHAR(10) NOT NULL,
    item_order INTEGER NOT NULL,
    item_name VARCHAR(300) NOT NULL,
    is_subtotal BOOLEAN DEFAULT FALSE,
    amount_tl DECIMAL(20, 2),
    amount_fx DECIMAL(20, 2),
    amount_total DECIMAL(20, 2),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_type_code) REFERENCES bank_types(code),
    UNIQUE(year, month, currency, bank_type_code, item_order)
);

CREATE INDEX idx_bs_period ON balance_sheet(year, month);
CREATE INDEX idx_bs_bank_type ON balance_sheet(bank_type_code);

-- 3.2 Income Statement (Table 2)
CREATE TABLE IF NOT EXISTS income_statement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    bank_type_code VARCHAR(10) NOT NULL,
    item_order INTEGER NOT NULL,
    item_name VARCHAR(300) NOT NULL,
    is_subtotal BOOLEAN DEFAULT FALSE,
    amount_tl DECIMAL(20, 2),
    amount_fx DECIMAL(20, 2),
    amount_total DECIMAL(20, 2),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_type_code) REFERENCES bank_types(code),
    UNIQUE(year, month, currency, bank_type_code, item_order)
);

CREATE INDEX idx_is_period ON income_statement(year, month);
CREATE INDEX idx_is_bank_type ON income_statement(bank_type_code);

-- 3.3 Loans (Tables 3-7 combined)
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL,  -- 3, 4, 5, 6, or 7
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    bank_type_code VARCHAR(10) NOT NULL,
    item_order INTEGER NOT NULL,
    item_name VARCHAR(300) NOT NULL,
    is_subtotal BOOLEAN DEFAULT FALSE,
    -- Generic columns (use based on table)
    short_term_tl DECIMAL(20, 2),
    short_term_fx DECIMAL(20, 2),
    short_term_total DECIMAL(20, 2),
    medium_long_tl DECIMAL(20, 2),
    medium_long_fx DECIMAL(20, 2),
    medium_long_total DECIMAL(20, 2),
    total_tl DECIMAL(20, 2),
    total_fx DECIMAL(20, 2),
    total_amount DECIMAL(20, 2),
    npl_amount DECIMAL(20, 2),
    non_cash_amount DECIMAL(20, 2),
    customer_count INTEGER,
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_type_code) REFERENCES bank_types(code),
    UNIQUE(table_number, year, month, currency, bank_type_code, item_order)
);

CREATE INDEX idx_loans_period ON loans(year, month);
CREATE INDEX idx_loans_table ON loans(table_number);

-- 3.4 Deposits (Tables 9-10 combined)
CREATE TABLE IF NOT EXISTS deposits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL,  -- 9 or 10
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    bank_type_code VARCHAR(10) NOT NULL,
    item_order INTEGER NOT NULL,
    item_name VARCHAR(300) NOT NULL,
    is_subtotal BOOLEAN DEFAULT FALSE,
    -- Table 9: By amount bracket
    bracket_10k DECIMAL(20, 2),
    bracket_50k DECIMAL(20, 2),
    bracket_250k DECIMAL(20, 2),
    bracket_1m DECIMAL(20, 2),
    bracket_over_1m DECIMAL(20, 2),
    -- Table 10: By maturity
    demand DECIMAL(20, 2),
    maturity_1m DECIMAL(20, 2),
    maturity_1_3m DECIMAL(20, 2),
    maturity_3_6m DECIMAL(20, 2),
    maturity_6_12m DECIMAL(20, 2),
    maturity_over_12m DECIMAL(20, 2),
    -- Common
    total_amount DECIMAL(20, 2),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_type_code) REFERENCES bank_types(code),
    UNIQUE(table_number, year, month, currency, bank_type_code, item_order)
);

CREATE INDEX idx_deposits_period ON deposits(year, month);

-- 3.5 Ratios (Tables 15, 17 combined)
CREATE TABLE IF NOT EXISTS financial_ratios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL,  -- 15 or 17
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    bank_type_code VARCHAR(10) NOT NULL,
    item_order INTEGER NOT NULL,
    item_name VARCHAR(300) NOT NULL,
    ratio_value DECIMAL(10, 6),
    ratio_category VARCHAR(100),  -- 'asset_quality', 'profitability', 'liquidity', 'capital'
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_type_code) REFERENCES bank_types(code),
    UNIQUE(table_number, year, month, bank_type_code, item_order)
);

CREATE INDEX idx_ratios_period ON financial_ratios(year, month);
CREATE INDEX idx_ratios_category ON financial_ratios(ratio_category);

-- ============================================================================
-- 4. FLEXIBLE STORAGE FOR OTHER TABLES
-- ============================================================================

-- For tables with varying structures (8, 11, 12, 13, 14, 16)
CREATE TABLE IF NOT EXISTS other_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    currency VARCHAR(10),
    bank_type_code VARCHAR(10) NOT NULL,
    item_order INTEGER NOT NULL,
    item_name VARCHAR(300) NOT NULL,
    is_subtotal BOOLEAN DEFAULT FALSE,
    column_name VARCHAR(100),  -- Dynamic column name
    value_numeric DECIMAL(20, 2),
    value_text TEXT,
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_type_code) REFERENCES bank_types(code)
);

CREATE INDEX idx_other_period ON other_data(year, month, table_number);

-- ============================================================================
-- 5. DATA QUALITY & AUDIT
-- ============================================================================

CREATE TABLE IF NOT EXISTS download_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER,
    year INTEGER,
    month INTEGER,
    currency VARCHAR(10),
    bank_type_code VARCHAR(10),
    status VARCHAR(20),  -- 'success', 'failed', 'partial'
    rows_downloaded INTEGER,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_log_status ON download_log(status, completed_at);

-- ============================================================================
-- 6. USEFUL VIEWS
-- ============================================================================

-- Latest period view
CREATE VIEW IF NOT EXISTS v_latest_period AS
SELECT MAX(year) as latest_year, MAX(month) as latest_month
FROM balance_sheet;

-- Sector overview (latest)
CREATE VIEW IF NOT EXISTS v_sector_overview AS
SELECT
    bs.year,
    bs.month,
    bs.item_name,
    bs.amount_total as balance_sheet_amount,
    inc.amount_total as income_statement_amount
FROM balance_sheet bs
LEFT JOIN income_statement inc
    ON bs.year = inc.year
    AND bs.month = inc.month
    AND bs.bank_type_code = inc.bank_type_code
    AND bs.item_order = inc.item_order
WHERE bs.bank_type_code = '10001'  -- Sector total
ORDER BY bs.year DESC, bs.month DESC, bs.item_order;

-- Key ratios summary
CREATE VIEW IF NOT EXISTS v_key_ratios AS
SELECT
    year,
    month,
    bank_type_code,
    MAX(CASE WHEN item_name LIKE '%Takipteki%' THEN ratio_value END) as npl_ratio,
    MAX(CASE WHEN item_name LIKE '%Sermaye Yeterlilik%' THEN ratio_value END) as capital_adequacy,
    MAX(CASE WHEN item_name LIKE '%Aktif Karlılık%' OR item_name LIKE '%ROA%' THEN ratio_value END) as roa,
    MAX(CASE WHEN item_name LIKE '%Özkaynak Karlılık%' OR item_name LIKE '%ROE%' THEN ratio_value END) as roe
FROM financial_ratios
WHERE table_number = 15
GROUP BY year, month, bank_type_code
ORDER BY year DESC, month DESC;
