# BDDK Banking Analysis - Usage Guide

Complete guide for using the Turkish Banking Sector Analysis System.

## Table of Contents
1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Command Line Interface](#command-line-interface)
4. [Python API](#python-api)
5. [Dashboard Usage](#dashboard-usage)
6. [Advanced Features](#advanced-features)
7. [Tips & Best Practices](#tips--best-practices)

## Installation

### Step 1: Install Python
Make sure you have Python 3.8+ installed:
```bash
python --version
```

### Step 2: Install Dependencies
```bash
cd bddk_analysis
pip install -r requirements.txt
```

### Step 3: Verify Installation
```bash
python main.py --help
```

## Quick Start

### Option 1: Using Command Line

**Download latest data:**
```bash
python main.py download --data-type all --currency TL --headless
```

**Process the data:**
```bash
python main.py process --currency TL
```

**Run analysis:**
```bash
python main.py analyze --currency TL --generate-report
```

**Launch dashboard:**
```bash
python main.py dashboard
```

### Option 2: Using Python Scripts

**Complete workflow:**
```python
# 1. Download data
from scrapers.weekly_scraper import BDDKWeeklyScraper

scraper = BDDKWeeklyScraper(headless=True)
data = scraper.get_latest_data(currency='TL')
scraper.close_driver()

# 2. Process data
from utils.data_processor import DataProcessor

processor = DataProcessor()
cleaned_data = processor.clean_numeric_columns(data['basic'])

# 3. Analyze
from analysis.financial_analyzer import BankingFinancialAnalyzer

analyzer = BankingFinancialAnalyzer()
report = analyzer.comprehensive_analysis(cleaned_data)

# 4. Generate report
from reports.report_generator import BankingReportGenerator

generator = BankingReportGenerator()
pdf_path = generator.generate_pdf_report(cleaned_data, report, 'analysis_report')

print(f"Report saved to: {pdf_path}")
```

## Command Line Interface

### Download Data

**Download all monthly data for 2024:**
```bash
python main.py download --data-type monthly --year 2024 --currency TL --headless
```

**Download historical data (2020-2024):**
```bash
python main.py download --data-type all --start-year 2020 --end-year 2024 --currency TL
```

**Download latest weekly data:**
```bash
python main.py download --data-type weekly --currency TL
```

**Download in both currencies:**
```bash
python main.py download --data-type all --currency TL
python main.py download --data-type all --currency USD
```

### Process Data

**Process all downloaded data:**
```bash
python main.py process
```

This will:
- Clean numeric columns
- Standardize column names
- Handle missing data
- Calculate financial ratios
- Save to database

### Analyze Data

**Basic analysis:**
```bash
python main.py analyze --currency TL
```

**Analysis with PDF report:**
```bash
python main.py analyze --currency TL --generate-report --report-format pdf
```

**Analysis with HTML report:**
```bash
python main.py analyze --currency TL --generate-report --report-format html
```

**Analysis with Excel report:**
```bash
python main.py analyze --currency TL --generate-report --report-format excel
```

### Forecast

**Forecast total loans for 12 months:**
```bash
python main.py forecast --metric total_loans --periods 12 --method ensemble
```

**Forecast using specific method:**
```bash
python main.py forecast --metric npl_ratio --periods 6 --method auto_arima
```

**Try all forecasting methods:**
```bash
python main.py forecast --metric total_assets --periods 12 --method all
```

### Dashboard

**Launch dashboard on default port (8050):**
```bash
python main.py dashboard
```

**Launch on custom port:**
```bash
python main.py dashboard --port 8080
```

**Launch in debug mode:**
```bash
python main.py dashboard --debug
```

### Generate Reports

**PDF report:**
```bash
python main.py report --currency TL --format pdf
```

**HTML report:**
```bash
python main.py report --currency TL --format html
```

**Excel report:**
```bash
python main.py report --currency TL --format excel
```

## Python API

### Data Download

```python
from scrapers.monthly_scraper import BDDKMonthlyScraper

# Initialize scraper
scraper = BDDKMonthlyScraper(headless=True)

# Download specific month
df = scraper.get_monthly_data(
    year=2024,
    month=11,
    currency='TL',
    category='balance_sheet'
)

# Download full year
all_data = scraper.download_year_data(2024, currency='TL')

# Always close driver
scraper.close_driver()
```

### Data Processing

```python
from utils.data_processor import DataProcessor
import pandas as pd

processor = DataProcessor()

# Load data
df = pd.read_csv('data/raw/monthly/data.csv')

# Clean
df = processor.clean_numeric_columns(df)
df = processor.standardize_column_names(df)
df = processor.handle_missing_data(df, strategy='interpolate')

# Calculate metrics
df = processor.calculate_financial_ratios(df)
df = processor.calculate_growth_rates(df, 'total_loans', periods=12)

# Detect outliers
df = processor.detect_outliers(df, 'npl_ratio', method='iqr')
```

### Financial Analysis

```python
from analysis.financial_analyzer import BankingFinancialAnalyzer

analyzer = BankingFinancialAnalyzer()

# Run specific analyses
asset_quality = analyzer.asset_quality_analysis(df)
profitability = analyzer.profitability_analysis(df)
liquidity = analyzer.liquidity_analysis(df)
capital = analyzer.capital_analysis(df)

# Comprehensive analysis
full_report = analyzer.comprehensive_analysis(df)

# Access results
print(f"Health Score: {full_report['overall_health']}")
print(f"Alerts: {full_report['all_alerts']}")

# Comparative analysis
comparison = analyzer.comparative_analysis(df, benchmark='sector')

# Trend analysis
trends = analyzer.trend_analysis(df, periods=[3, 6, 12])
```

### Forecasting

```python
from models.forecasting import BankingForecaster

forecaster = BankingForecaster()

# Prepare time series
ts = forecaster.prepare_time_series(df, 'date', 'total_loans')

# Auto ARIMA
arima_forecast = forecaster.auto_arima_forecast(ts, periods=12)

# Exponential Smoothing
es_forecast = forecaster.exponential_smoothing_forecast(ts, periods=12)

# Prophet
prophet_forecast = forecaster.prophet_forecast(df, 'date', 'total_loans', periods=12)

# Ensemble (combines multiple methods)
ensemble = forecaster.ensemble_forecast(ts, periods=12)

# Scenario analysis
scenarios = {
    'optimistic': 10,    # 10% higher
    'pessimistic': -10,  # 10% lower
    'stress': -25        # 25% lower
}
scenario_forecasts = forecaster.scenario_analysis(ensemble, scenarios)

# Backtesting
backtest_results = forecaster.backtesting(
    ts,
    forecaster.auto_arima_forecast,
    train_size=0.8
)
```

### Database Operations

```python
from utils.database import DatabaseManager

db = DatabaseManager(db_type='sqlite')

# Save data
db.save_monthly_data(df, category='balance_sheet')
db.save_weekly_data(weekly_df)

# Retrieve data
monthly = db.get_monthly_data(year=2024, month=11, currency='TL')
weekly = db.get_weekly_data(start_date='2024-01-01', currency='TL')

# Get time series
ts = db.get_metrics_timeseries(
    metric_name='npl_ratio',
    start_date='2020-01-01',
    period_type='monthly'
)

# Export to Excel
db.export_to_excel('banking_data.xlsx', tables=['monthly_data', 'weekly_data'])
```

### Report Generation

```python
from reports.report_generator import BankingReportGenerator

generator = BankingReportGenerator()

# PDF report
pdf_path = generator.generate_pdf_report(
    data=df,
    analysis_results=report,
    report_name='monthly_report'
)

# HTML report
html_path = generator.generate_html_report(
    data=df,
    analysis_results=report,
    report_name='monthly_report'
)

# Excel report
excel_path = generator.generate_excel_report(
    data=df,
    analysis_results=report,
    report_name='monthly_report'
)

# Comprehensive (all formats)
all_paths = generator.generate_comprehensive_report(
    data=df,
    analysis_results=report,
    format='pdf'  # or 'html', 'excel'
)
```

## Dashboard Usage

### Launching the Dashboard

```bash
python main.py dashboard --port 8050
```

Then open http://localhost:8050 in your browser.

### Dashboard Features

**Filters:**
- Currency: Switch between TL and USD
- Time Period: Select analysis window (3, 6, 12, 24 months)
- View Type: Choose analysis focus area
- Refresh: Update data

**Tabs:**
- **Key Metrics**: Overview of current banking sector status
- **Trends**: Time series analysis and trend visualization
- **Comparative**: Benchmark against sector averages
- **Analytics**: Advanced statistical analysis

**Views:**
- **Overview**: High-level sector summary
- **Asset Quality**: NPL analysis, provision coverage
- **Profitability**: ROA, ROE, NIM analysis
- **Liquidity**: L/D ratio, liquid assets
- **Capital**: CAR, tier ratios

### Customizing the Dashboard

```python
from visualizations.dashboard import BankingDashboard
from utils.database import DatabaseManager

# Load your data
db = DatabaseManager()
data = db.get_monthly_data(currency='TL')

# Create dashboard with data
dashboard = BankingDashboard(data_source=data)

# Run on custom port
dashboard.run(debug=True, port=9000)
```

## Advanced Features

### Automated Scheduling

Create a scheduled task to download and analyze data daily:

```python
import schedule
import time
from scrapers.weekly_scraper import BDDKWeeklyScraper
from analysis.financial_analyzer import BankingFinancialAnalyzer

def daily_update():
    # Download latest data
    scraper = BDDKWeeklyScraper(headless=True)
    data = scraper.get_latest_data(currency='TL')
    scraper.close_driver()

    # Analyze
    analyzer = BankingFinancialAnalyzer()
    report = analyzer.comprehensive_analysis(data['basic'])

    # Check for alerts
    if report['all_alerts']:
        print(f"ALERTS: {report['all_alerts']}")
        # Send email notification, etc.

# Schedule daily at 9 AM
schedule.every().day.at("09:00").do(daily_update)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Custom Metrics

Add custom analysis metrics:

```python
from analysis.financial_analyzer import BankingFinancialAnalyzer

class CustomBankingAnalyzer(BankingFinancialAnalyzer):
    def custom_ratio_analysis(self, df):
        """Calculate custom ratios"""
        analysis = {}

        # Custom ratio: Fee income to total income
        if 'fee_income' in df.columns and 'total_income' in df.columns:
            df['fee_income_ratio'] = (df['fee_income'] / df['total_income']) * 100
            analysis['avg_fee_ratio'] = df['fee_income_ratio'].mean()

        return analysis

# Use custom analyzer
analyzer = CustomBankingAnalyzer()
custom_analysis = analyzer.custom_ratio_analysis(df)
```

### Batch Processing

Process multiple files:

```python
from pathlib import Path
from utils.data_processor import DataProcessor

processor = DataProcessor()
data_dir = Path('data/raw/monthly')

for file_path in data_dir.glob('*.csv'):
    print(f"Processing {file_path.name}")

    df = pd.read_csv(file_path)
    df = processor.clean_numeric_columns(df)
    df = processor.calculate_financial_ratios(df)

    # Save processed
    output_path = Path('data/processed') / file_path.name
    df.to_csv(output_path, index=False)
```

## Tips & Best Practices

### Data Download
- Use `headless=True` for faster, automated downloads
- Download data during off-peak hours
- Save raw data before processing
- Implement retry logic for network failures

### Data Processing
- Always backup raw data
- Validate data after cleaning
- Check for Turkish character encoding issues
- Use `encoding='utf-8-sig'` when saving CSVs

### Analysis
- Ensure sufficient historical data (minimum 12 months)
- Compare multiple periods for trend analysis
- Use sector benchmarks for context
- Document custom metrics and calculations

### Forecasting
- Validate forecasts with backtesting
- Use ensemble methods for robust predictions
- Consider multiple scenarios
- Update models regularly with new data

### Performance
- Use database for large datasets
- Cache processed data
- Run intensive operations in background
- Use parallel processing when possible

### Error Handling

```python
from loguru import logger

try:
    scraper = BDDKMonthlyScraper()
    data = scraper.get_monthly_data(2024, 11, 'TL')
except Exception as e:
    logger.error(f"Download failed: {e}")
    # Fallback or retry logic
finally:
    scraper.close_driver()
```

## Troubleshooting

**Problem: Web scraping fails**
- Check internet connection
- Verify BDDK website is accessible
- Update ChromeDriver: `pip install --upgrade webdriver-manager`
- Try without headless mode to see errors

**Problem: Data processing errors**
- Check input file encoding
- Verify column names
- Look for unexpected data formats
- Check logs in `logs/` directory

**Problem: Dashboard won't start**
- Check if port is already in use
- Try different port: `--port 8080`
- Check Python version (requires 3.8+)
- Reinstall dash: `pip install --upgrade dash`

**Problem: Forecasting fails**
- Ensure minimum 12-24 data points
- Check for missing values
- Verify data is sorted by date
- Try different forecasting method

## Getting Help

- Check logs in `logs/` directory
- Review error messages carefully
- Consult README.md for overview
- Check config.py for settings

## Next Steps

1. Download your first dataset
2. Process and analyze the data
3. Generate your first report
4. Explore the dashboard
5. Experiment with forecasting
6. Customize for your needs

Happy analyzing!
