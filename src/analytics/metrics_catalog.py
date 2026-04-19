"""
BDDK Metrics Catalog
====================
This module defines all metrics that can be derived from BDDK raw data.
Each metric includes its definition, source, calculation logic, and available filters.

Data Sources:
- balance_sheet: Asset and liability line items
- loans: Loan portfolio with NPL data
- deposits: Deposit breakdown by maturity and size

Dimensions:
- time: year, month
- bank_type: See BANK_TYPES dict below. Primary: 10001 (Sector), 10003 (Private), 10004 (State), 10005 (Foreign), 10006 (Participation), 10007 (Dev&Inv)
- currency: TL, FX, TOTAL (derived from column suffixes)
"""

# =============================================================================
# BANK TYPE DEFINITIONS
# =============================================================================
# Banks are classified by two dimensions: business model and ownership.
#
# Hierarchy:
#   SECTOR (10001) = Deposit Banks (10002) + Participation Banks (10006) + Dev & Investment Banks (10007)
#   Deposit Banks (10002) = Private (10003) + State (10004) + Foreign (10005)
#
# Therefore: 10001 = 10003 + 10004 + 10005 + 10006 + 10007
#
# Codes 10008, 10009, 10010 are cross-cutting by ownership only (across all business models).

BANK_TYPES = {
    # Sector total
    "10001": {"name": "Sector", "name_tr": "Sektör", "description": "All banks (= 10003+10004+10005+10006+10007)"},

    # By business model
    "10002": {"name": "Deposit Banks", "name_tr": "Mevduat Bankaları", "description": "All deposit-taking banks (= 10003+10004+10005)"},
    "10006": {"name": "Participation Banks", "name_tr": "Katılım Bankaları", "description": "Islamic/participation banks (all ownership types)"},
    "10007": {"name": "Dev & Investment Banks", "name_tr": "Kalkınma ve Yatırım Bankaları", "description": "Development and investment banks (all ownership types)"},

    # Deposit banks by ownership
    "10003": {"name": "Private Deposit Banks", "name_tr": "Özel Mevduat Bankaları", "description": "Deposit banks with domestic private ownership"},
    "10004": {"name": "State Deposit Banks", "name_tr": "Kamu Mevduat Bankaları", "description": "Deposit banks with state/public ownership"},
    "10005": {"name": "Foreign Deposit Banks", "name_tr": "Yabancı Mevduat Bankaları", "description": "Deposit banks with foreign capital ownership"},

    # Cross-cutting by ownership only (across all business models)
    "10008": {"name": "Domestic Private (All)", "name_tr": "Yerli Özel Bankalar", "description": "All banks with domestic private ownership (deposit+participation+dev&inv)"},
    "10009": {"name": "Public Banks (All)", "name_tr": "Kamu Bankaları", "description": "All banks with state/public ownership (deposit+participation+dev&inv)"},
    "10010": {"name": "Foreign Banks (All)", "name_tr": "Yabancı Bankalar", "description": "All banks with foreign capital ownership (deposit+participation+dev&inv)"},
}

# Primary bank types for analysis (by business model + ownership breakdown)
PRIMARY_BANK_TYPES = ["10001", "10003", "10004", "10005", "10006", "10007"]


# =============================================================================
# CURRENCY DEFINITIONS
# =============================================================================
CURRENCY_TYPES = {
    "TL": {"name": "Turkish Lira", "column_suffix": "_tl", "name_tr": "TL"},
    "FX": {"name": "Foreign Currency", "column_suffix": "_fx", "name_tr": "YP"},
    "TOTAL": {"name": "Total", "column_suffix": "_total", "name_tr": "Toplam"},
}


# =============================================================================
# METRICS CATALOG
# =============================================================================
METRICS_CATALOG = {

    # =========================================================================
    # ASSET METRICS
    # =========================================================================
    "total_assets": {
        "name": "Total Assets",
        "name_tr": "Toplam Aktifler",
        "description": "Total assets of the banking sector",
        "category": "assets",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%TOPLAM AKT%'",
            "value_columns": {
                "TL": "amount_tl",
                "FX": "amount_fx",
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type", "currency"],
        "derived_metrics": ["asset_growth_yoy", "asset_growth_mom"],
    },

    "cash_and_central_bank": {
        "name": "Cash & Central Bank",
        "name_tr": "Nakit ve Merkez Bankası",
        "description": "Cash and claims on central bank",
        "category": "assets",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Nakit%' OR item_name LIKE '%Merkez Bankası%Alacak%'",
            "value_columns": {
                "TL": "amount_tl",
                "FX": "amount_fx",
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type", "currency"],
    },

    "securities_portfolio": {
        "name": "Securities Portfolio",
        "name_tr": "Menkul Kıymetler",
        "description": "Total securities (FVPL + FVOCI + Amortized Cost)",
        "category": "assets",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Menkul%Değ%' OR item_name LIKE '%Menk%Kıymet%'",
            "value_columns": {
                "TL": "amount_tl",
                "FX": "amount_fx",
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
            "notes": "Includes FVPL, FVOCI, and amortized cost securities",
        },
        "dimensions": ["time", "bank_type", "currency"],
    },

    # =========================================================================
    # CREDIT / LOAN METRICS
    # =========================================================================
    "total_loans": {
        "name": "Total Loans",
        "name_tr": "Toplam Krediler",
        "description": "Total loan portfolio",
        "category": "credit",
        "unit": "million_tl",
        "source": {
            "table": "loans",
            "filter": "item_name LIKE '%TOPLAM%' AND table_number = 3",
            "value_columns": {
                "TL": "total_tl",
                "FX": "total_fx",
                "TOTAL": "total_amount",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type", "currency"],
        "derived_metrics": ["loan_growth_yoy", "loan_growth_mom"],
    },

    "loans_short_term": {
        "name": "Short-term Loans",
        "name_tr": "Kısa Vadeli Krediler",
        "description": "Loans with maturity less than 1 year",
        "category": "credit",
        "unit": "million_tl",
        "source": {
            "table": "loans",
            "filter": "item_name LIKE '%TOPLAM%' AND table_number = 3",
            "value_columns": {
                "TL": "short_term_tl",
                "FX": "short_term_fx",
                "TOTAL": "short_term_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type", "currency"],
    },

    "loans_medium_long_term": {
        "name": "Medium/Long-term Loans",
        "name_tr": "Orta/Uzun Vadeli Krediler",
        "description": "Loans with maturity 1 year or more",
        "category": "credit",
        "unit": "million_tl",
        "source": {
            "table": "loans",
            "filter": "item_name LIKE '%TOPLAM%' AND table_number = 3",
            "value_columns": {
                "TL": "medium_long_tl",
                "FX": "medium_long_fx",
                "TOTAL": "medium_long_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type", "currency"],
    },

    "npl_amount": {
        "name": "Non-Performing Loans",
        "name_tr": "Takipteki Alacaklar",
        "description": "Non-performing loan amount (Stage 3)",
        "category": "credit",
        "unit": "million_tl",
        "source": {
            "table": "loans",
            "filter": "item_name LIKE '%TOPLAM%' AND table_number = 3",
            "value_columns": {
                "TOTAL": "npl_amount",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    "customer_count": {
        "name": "Loan Customer Count",
        "name_tr": "Kredi Müşteri Sayısı",
        "description": "Number of loan customers",
        "category": "credit",
        "unit": "count",
        "source": {
            "table": "loans",
            "filter": "item_name LIKE '%TOPLAM%' AND table_number = 3",
            "value_columns": {
                "TOTAL": "customer_count",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    # =========================================================================
    # DEPOSIT METRICS
    # =========================================================================
    "total_deposits": {
        "name": "Total Deposits",
        "name_tr": "Toplam Mevduat",
        "description": "Total deposit base",
        "category": "deposits",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Mevduat%' AND item_name NOT LIKE '%Faiz%'",
            "value_columns": {
                "TL": "amount_tl",
                "FX": "amount_fx",
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
            "notes": "Can also use deposits table for detailed breakdown",
        },
        "dimensions": ["time", "bank_type", "currency"],
        "derived_metrics": ["deposit_growth_yoy", "deposit_growth_mom"],
    },

    "demand_deposits": {
        "name": "Demand Deposits",
        "name_tr": "Vadesiz Mevduat",
        "description": "Deposits withdrawable on demand",
        "category": "deposits",
        "unit": "million_tl",
        "source": {
            "table": "deposits",
            "filter": "item_name LIKE '%TOPLAM%'",
            "value_columns": {
                "TOTAL": "demand",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    "time_deposits": {
        "name": "Time Deposits",
        "name_tr": "Vadeli Mevduat",
        "description": "Total time deposits (all maturities)",
        "category": "deposits",
        "unit": "million_tl",
        "source": {
            "table": "deposits",
            "filter": "item_name LIKE '%TOPLAM%'",
            "value_columns": {
                "TOTAL": ["maturity_1m", "maturity_1_3m", "maturity_3_6m", "maturity_6_12m", "maturity_over_12m"],
            },
            "aggregation": "SUM",
            "notes": "Sum of all maturity buckets",
        },
        "dimensions": ["time", "bank_type"],
    },

    # =========================================================================
    # CAPITAL / EQUITY METRICS
    # =========================================================================
    "total_equity": {
        "name": "Total Equity",
        "name_tr": "Toplam Özkaynaklar",
        "description": "Total shareholders' equity",
        "category": "capital",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%TOPLAM ÖZKAYN%'",
            "value_columns": {
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    "paid_in_capital": {
        "name": "Paid-in Capital",
        "name_tr": "Ödenmiş Sermaye",
        "description": "Paid-in share capital",
        "category": "capital",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Ödenmiş Sermaye%'",
            "value_columns": {
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    "retained_earnings": {
        "name": "Retained Earnings",
        "name_tr": "Yedek Akçeler",
        "description": "Accumulated retained earnings",
        "category": "capital",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Yedek%' OR item_name LIKE '%Kar%'",
            "value_columns": {
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    # =========================================================================
    # LIABILITY METRICS
    # =========================================================================
    "total_liabilities": {
        "name": "Total Liabilities",
        "name_tr": "Toplam Yabancı Kaynaklar",
        "description": "Total liabilities (non-equity)",
        "category": "liabilities",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%TOPLAM YABANCI KAYN%'",
            "value_columns": {
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    "borrowings_from_banks": {
        "name": "Borrowings from Banks",
        "name_tr": "Bankalara Borçlar",
        "description": "Interbank borrowings",
        "category": "liabilities",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Bankalara Borç%'",
            "value_columns": {
                "TL": "amount_tl",
                "FX": "amount_fx",
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type", "currency"],
    },

    # =========================================================================
    # OFF-BALANCE SHEET METRICS
    # =========================================================================
    "non_cash_loans": {
        "name": "Non-Cash Loans (Guarantees)",
        "name_tr": "Gayrinakdi Krediler",
        "description": "Letters of guarantee, letters of credit, etc.",
        "category": "off_balance",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Gayrinakdi%'",
            "value_columns": {
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },

    "derivative_instruments": {
        "name": "Derivative Instruments",
        "name_tr": "Türev Finansal Araçlar",
        "description": "Derivative financial instruments (notional)",
        "category": "off_balance",
        "unit": "million_tl",
        "source": {
            "table": "balance_sheet",
            "filter": "item_name LIKE '%Türev%'",
            "value_columns": {
                "TOTAL": "amount_total",
            },
            "aggregation": "SUM",
        },
        "dimensions": ["time", "bank_type"],
    },
}


# =============================================================================
# CALCULATED RATIOS (Derived from base metrics)
# =============================================================================
CALCULATED_RATIOS = {

    "npl_ratio": {
        "name": "NPL Ratio",
        "name_tr": "TGA Oranı",
        "description": "Non-performing loans / Total loans",
        "category": "asset_quality",
        "unit": "percentage",
        "formula": {
            "numerator": "npl_amount",
            "denominator": "total_loans",
            "multiply_by": 100,
        },
        "dimensions": ["time", "bank_type"],
    },

    "loan_to_deposit_ratio": {
        "name": "Loan-to-Deposit Ratio (LDR)",
        "name_tr": "Kredi/Mevduat Oranı",
        "description": "Total loans / Total deposits",
        "category": "liquidity",
        "unit": "percentage",
        "formula": {
            "numerator": "total_loans",
            "denominator": "total_deposits",
            "multiply_by": 100,
        },
        "dimensions": ["time", "bank_type", "currency"],
    },

    "equity_ratio": {
        "name": "Equity Ratio",
        "name_tr": "Özkaynak Oranı",
        "description": "Total equity / Total assets",
        "category": "capital",
        "unit": "percentage",
        "formula": {
            "numerator": "total_equity",
            "denominator": "total_assets",
            "multiply_by": 100,
        },
        "dimensions": ["time", "bank_type"],
    },

    "fx_loan_share": {
        "name": "FX Loan Share",
        "name_tr": "YP Kredi Payı",
        "description": "FX loans / Total loans",
        "category": "currency",
        "unit": "percentage",
        "formula": {
            "numerator": "total_loans[FX]",
            "denominator": "total_loans[TOTAL]",
            "multiply_by": 100,
        },
        "dimensions": ["time", "bank_type"],
    },

    "fx_deposit_share": {
        "name": "FX Deposit Share",
        "name_tr": "YP Mevduat Payı",
        "description": "FX deposits / Total deposits",
        "category": "currency",
        "unit": "percentage",
        "formula": {
            "numerator": "total_deposits[FX]",
            "denominator": "total_deposits[TOTAL]",
            "multiply_by": 100,
        },
        "dimensions": ["time", "bank_type"],
    },

    "demand_deposit_share": {
        "name": "Demand Deposit Share",
        "name_tr": "Vadesiz Mevduat Payı",
        "description": "Demand deposits / Total deposits",
        "category": "deposits",
        "unit": "percentage",
        "formula": {
            "numerator": "demand_deposits",
            "denominator": "total_deposits",
            "multiply_by": 100,
        },
        "dimensions": ["time", "bank_type"],
    },

    "short_term_loan_share": {
        "name": "Short-term Loan Share",
        "name_tr": "Kısa Vadeli Kredi Payı",
        "description": "Short-term loans / Total loans",
        "category": "credit",
        "unit": "percentage",
        "formula": {
            "numerator": "loans_short_term",
            "denominator": "total_loans",
            "multiply_by": 100,
        },
        "dimensions": ["time", "bank_type", "currency"],
    },
}


# =============================================================================
# GROWTH METRICS (Time-based calculations)
# =============================================================================
GROWTH_METRICS = {

    "asset_growth_yoy": {
        "name": "Asset Growth (YoY)",
        "name_tr": "Aktif Büyümesi (YoY)",
        "description": "Year-over-year asset growth",
        "category": "growth",
        "unit": "percentage",
        "base_metric": "total_assets",
        "calculation": "yoy",  # (current - previous_year) / previous_year * 100
        "dimensions": ["time", "bank_type", "currency"],
    },

    "asset_growth_mom": {
        "name": "Asset Growth (MoM)",
        "name_tr": "Aktif Büyümesi (MoM)",
        "description": "Month-over-month asset growth",
        "category": "growth",
        "unit": "percentage",
        "base_metric": "total_assets",
        "calculation": "mom",
        "dimensions": ["time", "bank_type", "currency"],
    },

    "loan_growth_yoy": {
        "name": "Loan Growth (YoY)",
        "name_tr": "Kredi Büyümesi (YoY)",
        "description": "Year-over-year loan growth",
        "category": "growth",
        "unit": "percentage",
        "base_metric": "total_loans",
        "calculation": "yoy",
        "dimensions": ["time", "bank_type", "currency"],
    },

    "loan_growth_mom": {
        "name": "Loan Growth (MoM)",
        "name_tr": "Kredi Büyümesi (MoM)",
        "description": "Month-over-month loan growth",
        "category": "growth",
        "unit": "percentage",
        "base_metric": "total_loans",
        "calculation": "mom",
        "dimensions": ["time", "bank_type", "currency"],
    },

    "deposit_growth_yoy": {
        "name": "Deposit Growth (YoY)",
        "name_tr": "Mevduat Büyümesi (YoY)",
        "description": "Year-over-year deposit growth",
        "category": "growth",
        "unit": "percentage",
        "base_metric": "total_deposits",
        "calculation": "yoy",
        "dimensions": ["time", "bank_type", "currency"],
    },

    "deposit_growth_mom": {
        "name": "Deposit Growth (MoM)",
        "name_tr": "Mevduat Büyümesi (MoM)",
        "description": "Month-over-month deposit growth",
        "category": "growth",
        "unit": "percentage",
        "base_metric": "total_deposits",
        "calculation": "mom",
        "dimensions": ["time", "bank_type", "currency"],
    },

    "npl_growth_yoy": {
        "name": "NPL Growth (YoY)",
        "name_tr": "TGA Büyümesi (YoY)",
        "description": "Year-over-year NPL growth",
        "category": "growth",
        "unit": "percentage",
        "base_metric": "npl_amount",
        "calculation": "yoy",
        "dimensions": ["time", "bank_type"],
    },
}


# =============================================================================
# METRIC CATEGORIES (for dashboard organization)
# =============================================================================
METRIC_CATEGORIES = {
    "assets": {
        "name": "Assets",
        "name_tr": "Aktifler",
        "description": "Asset-side balance sheet items",
        "icon": "building-bank",
    },
    "credit": {
        "name": "Credit",
        "name_tr": "Krediler",
        "description": "Loan portfolio metrics",
        "icon": "credit-card",
    },
    "deposits": {
        "name": "Deposits",
        "name_tr": "Mevduat",
        "description": "Deposit metrics",
        "icon": "piggy-bank",
    },
    "capital": {
        "name": "Capital",
        "name_tr": "Sermaye",
        "description": "Capital and equity metrics",
        "icon": "shield-check",
    },
    "liabilities": {
        "name": "Liabilities",
        "name_tr": "Yükümlülükler",
        "description": "Liability-side metrics",
        "icon": "receipt",
    },
    "asset_quality": {
        "name": "Asset Quality",
        "name_tr": "Aktif Kalitesi",
        "description": "NPL and provision metrics",
        "icon": "alert-triangle",
    },
    "liquidity": {
        "name": "Liquidity",
        "name_tr": "Likidite",
        "description": "Liquidity ratios",
        "icon": "droplet",
    },
    "currency": {
        "name": "Currency",
        "name_tr": "Döviz",
        "description": "Currency composition metrics",
        "icon": "currency-dollar",
    },
    "growth": {
        "name": "Growth",
        "name_tr": "Büyüme",
        "description": "Growth rates",
        "icon": "trending-up",
    },
    "off_balance": {
        "name": "Off-Balance Sheet",
        "name_tr": "Bilanço Dışı",
        "description": "Off-balance sheet items",
        "icon": "file-text",
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_metric(metric_id: str) -> dict:
    """Get metric definition by ID"""
    if metric_id in METRICS_CATALOG:
        return METRICS_CATALOG[metric_id]
    elif metric_id in CALCULATED_RATIOS:
        return CALCULATED_RATIOS[metric_id]
    elif metric_id in GROWTH_METRICS:
        return GROWTH_METRICS[metric_id]
    return None


def get_metrics_by_category(category: str) -> list:
    """Get all metrics in a category"""
    metrics = []
    for metric_id, metric in METRICS_CATALOG.items():
        if metric.get("category") == category:
            metrics.append({"id": metric_id, **metric})
    for metric_id, metric in CALCULATED_RATIOS.items():
        if metric.get("category") == category:
            metrics.append({"id": metric_id, **metric})
    for metric_id, metric in GROWTH_METRICS.items():
        if metric.get("category") == category:
            metrics.append({"id": metric_id, **metric})
    return metrics


def list_all_metrics() -> list:
    """List all available metrics"""
    all_metrics = []
    for metric_id, metric in METRICS_CATALOG.items():
        all_metrics.append({"id": metric_id, "type": "base", **metric})
    for metric_id, metric in CALCULATED_RATIOS.items():
        all_metrics.append({"id": metric_id, "type": "ratio", **metric})
    for metric_id, metric in GROWTH_METRICS.items():
        all_metrics.append({"id": metric_id, "type": "growth", **metric})
    return all_metrics


if __name__ == "__main__":
    # Print summary of metrics catalog
    print("=" * 60)
    print("BDDK METRICS CATALOG SUMMARY")
    print("=" * 60)

    print(f"\nBase Metrics: {len(METRICS_CATALOG)}")
    for metric_id in METRICS_CATALOG:
        print(f"  - {metric_id}: {METRICS_CATALOG[metric_id]['name']}")

    print(f"\nCalculated Ratios: {len(CALCULATED_RATIOS)}")
    for metric_id in CALCULATED_RATIOS:
        print(f"  - {metric_id}: {CALCULATED_RATIOS[metric_id]['name']}")

    print(f"\nGrowth Metrics: {len(GROWTH_METRICS)}")
    for metric_id in GROWTH_METRICS:
        print(f"  - {metric_id}: {GROWTH_METRICS[metric_id]['name']}")

    print(f"\nTotal Metrics: {len(METRICS_CATALOG) + len(CALCULATED_RATIOS) + len(GROWTH_METRICS)}")
