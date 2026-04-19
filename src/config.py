"""
Configuration file for BDDK Banking Sector Analysis Project
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / '.env')

# Project Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# BDDK URLs
BDDK_BASE_URL = "https://www.bddk.org.tr"
BDDK_MONTHLY_URL = f"{BDDK_BASE_URL}/BultenAylik"
BDDK_WEEKLY_URL = f"{BDDK_BASE_URL}/BultenHaftalik"
BDDK_DAILY_URL = f"{BDDK_BASE_URL}/BultenGunluk"
BDDK_FINTURK_URL = f"{BDDK_BASE_URL}/BultenFinTurk"

# Data Collection Settings
START_YEAR = 2004
CURRENCIES = ["TL", "USD"]
DEFAULT_CURRENCY = "TL"

# Monthly Bulletin Categories
MONTHLY_CATEGORIES = {
    "balance_sheet": "Bilanço",
    "profit_loss": "Gelir Gider",
    "loans": "Krediler",
    "deposits": "Mevduat",
    "capital_adequacy": "Sermaye Yeterliliği",
    "liquidity": "Likidite",
    "asset_quality": "Aktif Kalitesi",
    "profitability": "Karlılık",
    "market_risk": "Piyasa Riski",
    "off_balance_sheet": "Bilanço Dışı İşlemler"
}

# Weekly Bulletin Data Points
WEEKLY_METRICS = [
    "total_assets",
    "total_loans",
    "total_deposits",
    "npl_ratio",
    "capital_adequacy_ratio",
    "liquid_assets",
    "profit_loss"
]

# Analysis Parameters
ANALYSIS_METRICS = {
    "asset_quality": [
        "npl_ratio",
        "provision_coverage_ratio",
        "loan_growth_rate",
        "sector_concentration"
    ],
    "profitability": [
        "roa",
        "roe",
        "nim",
        "cost_income_ratio",
        "fee_income_ratio"
    ],
    "liquidity": [
        "loan_deposit_ratio",
        "liquid_assets_ratio",
        "liquidity_coverage_ratio"
    ],
    "capital": [
        "capital_adequacy_ratio",
        "tier1_ratio",
        "leverage_ratio"
    ],
    "growth": [
        "asset_growth",
        "loan_growth",
        "deposit_growth",
        "equity_growth"
    ]
}

# Database Settings (Optional - for storing data)
DATABASE_CONFIG = {
    "type": "sqlite",  # or "postgresql", "mysql"
    "sqlite_path": DATA_DIR / "bddk_data.db",
    "table_prefix": "bddk_"
}

# Scraping Settings
SCRAPER_CONFIG = {
    "timeout": 30,
    "retry_attempts": 3,
    "delay_between_requests": 2,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Visualization Settings
VIZ_CONFIG = {
    "style": "seaborn-v0_8-darkgrid",
    "figure_size": (14, 8),
    "dpi": 100,
    "color_palette": "husl"
}

# Report Settings
REPORT_CONFIG = {
    "output_format": ["pdf", "html", "excel"],
    "include_charts": True,
    "include_statistics": True,
    "language": "tr"  # Turkish
}

# Logging Settings
LOG_CONFIG = {
    "level": "INFO",
    "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    "rotation": "10 MB",
    "retention": "30 days"
}

# EVDS (TCMB Electronic Data Delivery System) Settings
EVDS_API_KEY = os.getenv('EVDS_API_KEY')

# Default Metric Values (fallbacks when data unavailable)
DEFAULT_METRICS = {
    "npl_ratio": 2.0,      # NPL ratio percentage
    "car_ratio": 17.0,     # Capital Adequacy Ratio percentage
    "roa": 1.5,            # Return on Assets percentage
    "roe": 12.0,           # Return on Equity percentage
    "ldr": 95.0,           # Loan-to-Deposit Ratio percentage
}

# Scraper Timing (seconds)
SCRAPER_DELAYS = {
    "page_load": 5,        # Wait for JavaScript to load
    "after_select": 1,     # Wait after dropdown selection
    "after_submit": 3,     # Wait after form submission
    "between_requests": 2, # Delay between API requests
}

# Common EVDS Series Codes
EVDS_SERIES = {
    # Exchange Rates (Note: TP.DK.USD.A is the buying rate without YTL suffix)
    "usd_try": "TP.DK.USD.A",     # USD/TRY buying rate
    "eur_try": "TP.DK.EUR.A",     # EUR/TRY buying rate

    # Interest Rates
    "policy_rate": "TP.APIFON4",  # CBRT Policy Rate
    "consumer_loan_rate": "TP.KTF18",  # Consumer Loan Rate (TL)
    "commercial_loan_rate": "TP.KTF17",  # Commercial Loan Rate (TL)
    "deposit_rate": "TP.TRY.MT01",  # TL Deposit Rate

    # Inflation
    "cpi": "TP.FG.J0",  # Consumer Price Index
    "ppi": "TP.FG.J1",  # Producer Price Index

    # Money Supply
    "m1": "TP.PBD.H01",
    "m2": "TP.PBD.H09",
    "m3": "TP.PBD.H17",

    # CBRT Reserves
    "gross_reserves": "TP.AB.A01",
    "net_reserves": "TP.AB.N01",
}
