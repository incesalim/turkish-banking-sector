# BDDK Table Structure Analysis

**Date**: October 2025 Data
**Total Tables**: 17
**Source**: BDDK Monthly Bulletin API

## Key Observations

### Common Columns Across All Tables:
- **BankaAdi**: Bank name/type (e.g., "Sektör", specific bank names)
- **BasitSira**: Sort order number
- **Ad**: Item name/description (main data row label)
- **BasitFont**: Font styling (e.g., "bold" for headers/subtotals)

### Common Data Patterns:
- **TP**: Turkish Lira (Türk Parası)
- **YP**: Foreign Currency (Yabancı Para)
- **Toplam**: Total
- **Nakdi**: Cash/Cash loans
- **Gayri Nakdi**: Non-cash
- **Takipteki**: Non-performing

---

## Table Details

### Table 1: Bilanço (Balance Sheet)
**Rows**: 62
**Purpose**: Main balance sheet data

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **TP**: TL amounts
- **YP**: Foreign currency amounts
- **Toplam**: Total

**Key Metrics**: Cash, securities, loans, deposits, equity, total assets

---

### Table 2: Kar Zarar (Profit & Loss)
**Rows**: 53
**Purpose**: Income statement data

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **TP**: TL amounts
- **YP**: Foreign currency amounts
- **Toplam**: Total

**Key Metrics**: Interest income, fee income, operating expenses, net profit

---

### Table 3: Krediler (Loans)
**Rows**: 20
**Purpose**: Loan breakdown by maturity

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **KisaTP/KisaYP/KisaToplam**: Short-term (TP, YP, Total)
- **OrtaUzunTP/OrtaUzunYP/OrtaUzunToplam**: Medium-long term
- **ToplamTP/ToplamYP/Toplam**: Total loans

**Key Metrics**: Short-term loans, medium-long term loans by currency

---

### Table 4: Tüketici Kredileri (Consumer Loans)
**Rows**: 41
**Purpose**: Consumer loan details

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **TP**: TL consumer loans
- **YP**: Foreign currency consumer loans
- **Toplam**: Total

**Key Metrics**: Housing loans, vehicle loans, general purpose loans

---

### Table 5: Sektörel Kredi Dağılımı (Sectoral Loan Distribution)
**Rows**: 70
**Purpose**: Loans by economic sector
**Unit**: Thousand TL (bin TL)

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **KisaVadeliNakdi**: Short-term cash loans
- **OrtaUzunVadeliNakdi**: Medium-long term cash loans
- **Nakdi**: Total cash loans
- **Takipteki**: Non-performing loans
- **ToplamNakdi**: Total cash loans including NPL
- **GayriNakdi**: Non-cash loans

**Key Sectors**: Agriculture, manufacturing, construction, trade, services, etc.

---

### Table 6: KOBİ Kredileri (SME Loans)
**Rows**: 8
**Purpose**: Small and medium enterprise loans

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **NakdiKrediTP/YP/Toplam**: Cash loans
- **TakipKrediTP/YP/Toplam**: NPL
- **GayriNakdiKrediTP/YP/Toplam**: Non-cash loans
- **NetMusteri**: Number of customers

**Key Metrics**: SME cash loans, NPLs, guarantees, customer count

---

### Table 7: Sendikasyon Seküritizasyon (Syndication & Securitization)
**Rows**: 3
**Purpose**: Syndicated loans and securitization

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **TP/YP/Toplam**

**Key Metrics**: Syndication loans, securitization amounts

---

### Table 8: Menkul Kıymetler (Securities)
**Rows**: 29
**Purpose**: Securities portfolio breakdown

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **TP/YP/Toplam**

**Key Metrics**: Government bonds, corporate bonds, shares, other securities

---

### Table 9: Mevduat Türler İtibarıyla (Deposits by Type)
**Rows**: 26
**Purpose**: Deposit breakdown by amount brackets

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **OnBin**: Up to 10,000 TL
- **ElliBin**: 10,000-50,000 TL
- **IkiyuzelliBin**: 50,000-250,000 TL
- **Milyon**: 250,000-1,000,000 TL
- **Milyonarti**: Over 1,000,000 TL
- **Toplam**: Total

**Key Metrics**: Deposit concentration by size

---

### Table 10: Mevduat Vade İtibarıyla (Deposits by Maturity)
**Rows**: 24
**Purpose**: Deposit breakdown by maturity

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **Vadesiz**: Demand deposits
- **BirAyaKadar**: Up to 1 month
- **BirAyUcAy**: 1-3 months
- **UcAyAltiAy**: 3-6 months
- **AltiAyBirYil**: 6-12 months
- **BirYil**: Over 1 year
- **Toplam**: Total

**Key Metrics**: Maturity structure of deposits

---

### Table 11: Likidite Durumu (Liquidity Position)
**Rows**: 44
**Purpose**: Liquidity gap analysis

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **YediGun**: 7 days
- **BirAy**: 1 month
- **UcAy**: 3 months
- **OnikiAy**: 12 months
- **TumVarlikYukumluluk**: Total

**Key Metrics**: Assets and liabilities by maturity buckets

---

### Table 12: Sermaye Yeterliliği (Capital Adequacy)
**Rows**: 31
**Purpose**: Capital adequacy components

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **Toplam**: Total amount

**Key Metrics**: Tier 1 capital, Tier 2 capital, risk-weighted assets, CAR

---

### Table 13: Yabancı Para Pozisyonu (FX Position)
**Rows**: 11
**Purpose**: Foreign currency position

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **Toplam**: Total amount

**Key Metrics**: FX assets, FX liabilities, net FX position

---

### Table 14: Bilanço Dışı İşlemler (Off-Balance Sheet)
**Rows**: 52
**Purpose**: Off-balance sheet items

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **TP/YP/Toplam**

**Key Metrics**: Guarantees, letters of credit, derivatives, commitments

---

### Table 15: Rasyolar (Ratios)
**Rows**: 32
**Purpose**: Key financial ratios

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **Rasyo**: Ratio value (%)

**Key Metrics**:
- NPL ratio
- Capital adequacy ratio
- Liquidity ratios
- Profitability ratios
- Leverage ratios

---

### Table 16: Diğer Bilgiler (Other Information)
**Rows**: 7
**Purpose**: Additional metadata

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **Adet**: Count

**Key Metrics**: Number of banks, branches, employees, ATMs

---

### Table 17: Yurt Dışı Şube Rasyoları (Foreign Branch Ratios)
**Rows**: 3
**Purpose**: Foreign branch metrics

**Columns**:
- BankaAdi, BasitSira, Ad, BasitFont
- **Rasyo**: Ratio value (%)

**Key Metrics**: Foreign branch loans/total, deposits/total, profit/total

---

## Database Design Recommendations

### Option 1: Single Wide Table (Simple)
Store all tables in one table with these columns:
- `table_number` (1-17)
- `table_name` (e.g., "Bilanço")
- `year`, `month`, `currency`
- `bank_type` (Sektör, Mevduat, etc.)
- `row_order` (BasitSira)
- `item_name` (Ad)
- `font_style` (BasitFont)
- `column_name` (e.g., "TP", "YP", "Toplam")
- `value` (numeric)
- `download_date`

**Pros**: Simple, flexible
**Cons**: Not normalized, harder to query specific metrics

### Option 2: Separate Table per Category (Normalized)
Create focused tables:
- `balance_sheet` (Table 1)
- `income_statement` (Table 2)
- `loans` (Tables 3, 4, 5, 6, 7)
- `deposits` (Tables 9, 10)
- `securities` (Table 8)
- `liquidity` (Table 11)
- `capital` (Table 12)
- `fx_position` (Table 13)
- `off_balance_sheet` (Table 14)
- `ratios` (Tables 15, 17)
- `metadata` (Table 16)

**Pros**: Normalized, easy to query
**Cons**: More complex setup

### Option 3: Hybrid (Recommended)
**Core Tables**:
- `raw_data`: Store raw JSON responses
- `balance_sheet_monthly`: Cleaned Table 1 data
- `income_statement_monthly`: Cleaned Table 2 data
- `loans_monthly`: Combined Tables 3-7
- `deposits_monthly`: Combined Tables 9-10
- `ratios_monthly`: Combined Tables 15, 17

**Metadata Table**:
- `data_dictionary`: Column definitions, Turkish-English mappings

**Pros**: Balance of normalization and simplicity
**Cons**: Requires initial setup

---

## Data Quality Considerations

### 1. Common Column Names
All tables share: `BankaAdi`, `BasitSira`, `Ad`, `BasitFont`

### 2. Currency Conventions
- **TP** = Turkish Lira
- **YP** = Foreign Currency (usually USD/EUR aggregated)

### 3. Units Vary by Table
- Most tables: Million TL
- Table 5: Thousand TL (bin TL)
- Ratios: Percentages or counts

### 4. Font Style Indicates Hierarchy
- `"bold"` = Header/subtotal row
- `""` (empty) = Detail row

### 5. Row Relationships
- Some rows are sums of others (indicated in `Ad` field)
- Example: "Toplam KOBİ Kredileri (2+3+4)" means sum of rows 2, 3, 4

---

## Next Steps

1. **Choose database schema** (recommend Option 3: Hybrid)
2. **Create table definitions** with proper data types
3. **Write data transformation functions** to clean and normalize
4. **Implement incremental loading** strategy
5. **Add data validation** rules
6. **Create data quality checks**
