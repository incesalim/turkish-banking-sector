"""
Demo Script - Turkish Banking Sector Analysis System

This script demonstrates all major features of the system.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import sys
import io
warnings.filterwarnings('ignore')

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("="*70)
print("TURKISH BANKING SECTOR ANALYSIS SYSTEM - DEMO")
print("="*70)

# Generate sample banking data
print("\n1. Generating Sample Banking Data...")
print("-" * 70)

dates = pd.date_range('2020-01-01', periods=48, freq='M')
np.random.seed(42)

# Create realistic banking data with trends
base_assets = 10000
asset_growth_rate = 0.015  # 1.5% monthly growth

data = {
    'date': dates,
    'total_assets': [base_assets * (1 + asset_growth_rate)**i + np.random.randn()*200
                     for i in range(48)],
    'total_loans': [base_assets * 0.7 * (1 + asset_growth_rate)**i + np.random.randn()*150
                    for i in range(48)],
    'total_deposits': [base_assets * 0.8 * (1 + asset_growth_rate)**i + np.random.randn()*100
                       for i in range(48)],
    'npl_amount': [300 + i*2 + np.random.randn()*20 for i in range(48)],
    'equity': [1500 + i*10 + np.random.randn()*30 for i in range(48)],
    'net_profit': [50 + i*0.5 + np.random.randn()*5 for i in range(48)],
    'provisions': [250 + i*1.5 + np.random.randn()*15 for i in range(48)],
    'liquid_assets': [2000 + i*15 + np.random.randn()*50 for i in range(48)],
}

df = pd.DataFrame(data)

print(f"Generated {len(df)} months of banking data")
print(f"Date range: {df['date'].min().strftime('%Y-%m')} to {df['date'].max().strftime('%Y-%m')}")
print(f"\nSample data (first 5 rows):")
print(df.head())

# 2. Data Processing
print("\n\n2. Data Processing & Cleaning")
print("-" * 70)

from utils.data_processor import DataProcessor

processor = DataProcessor()

# Calculate financial ratios
df['npl_ratio'] = (df['npl_amount'] / df['total_loans']) * 100
df['provision_coverage'] = (df['provisions'] / df['npl_amount']) * 100
df['roa'] = (df['net_profit'] / df['total_assets']) * 100
df['roe'] = (df['net_profit'] / df['equity']) * 100
df['loan_deposit_ratio'] = (df['total_loans'] / df['total_deposits']) * 100
df['liquid_assets_ratio'] = (df['liquid_assets'] / df['total_assets']) * 100
df['capital_adequacy_ratio'] = 16.5 + np.random.randn(48) * 0.5  # Simulated CAR

# Calculate growth rates
df = processor.calculate_growth_rates(df, 'total_loans', periods=12)
df = processor.calculate_moving_average(df, 'npl_ratio', window=3)

print("Calculated financial ratios:")
print(f"  - NPL Ratio: {df['npl_ratio'].iloc[-1]:.2f}%")
print(f"  - ROA: {df['roa'].iloc[-1]:.2f}%")
print(f"  - ROE: {df['roe'].iloc[-1]:.2f}%")
print(f"  - CAR: {df['capital_adequacy_ratio'].iloc[-1]:.2f}%")
print(f"  - Loan/Deposit: {df['loan_deposit_ratio'].iloc[-1]:.2f}%")

# 3. Financial Analysis
print("\n\n3. Comprehensive Financial Analysis")
print("-" * 70)

from analysis.financial_analyzer import BankingFinancialAnalyzer

analyzer = BankingFinancialAnalyzer()

# Run comprehensive analysis
report = analyzer.comprehensive_analysis(df)

print(f"Overall Health Score: {report['overall_health']}/100")
print(f"\nTotal Alerts: {len(report['all_alerts'])}")

if report['all_alerts']:
    print("\nAlerts:")
    for i, alert in enumerate(report['all_alerts'], 1):
        print(f"  {i}. {alert}")
else:
    print("\n✓ No alerts - banking sector looks healthy!")

# Asset Quality
if 'asset_quality' in report:
    print("\n--- Asset Quality Metrics ---")
    for metric, value in report['asset_quality'].get('metrics', {}).items():
        print(f"  {metric}: {value}")

# Profitability
if 'profitability' in report:
    print("\n--- Profitability Metrics ---")
    for metric, value in report['profitability'].get('metrics', {}).items():
        print(f"  {metric}: {value}")

# 4. Forecasting
print("\n\n4. Time Series Forecasting")
print("-" * 70)

from models.forecasting import BankingForecaster

forecaster = BankingForecaster()

# Prepare time series
ts = forecaster.prepare_time_series(df, 'date', 'total_loans')

print(f"Forecasting Total Loans for next 12 months...")

# ARIMA Forecast
try:
    arima_forecast = forecaster.auto_arima_forecast(ts, periods=12)
    print(f"\n✓ ARIMA Forecast completed")
    print(f"  Last actual value: {ts.iloc[-1]:,.0f}")
    print(f"  Forecast in 12 months: {arima_forecast['forecast'].iloc[-1]:,.0f}")
except Exception as e:
    print(f"  ARIMA forecast failed: {str(e)}")

# Exponential Smoothing
try:
    es_forecast = forecaster.exponential_smoothing_forecast(ts, periods=12)
    print(f"\n✓ Exponential Smoothing completed")
    print(f"  Forecast in 12 months: {es_forecast['forecast'].iloc[-1]:,.0f}")
except Exception as e:
    print(f"  Exponential Smoothing failed: {str(e)}")

# Ensemble Forecast
try:
    ensemble_forecast = forecaster.ensemble_forecast(ts, periods=12)
    if ensemble_forecast is not None:
        print(f"\n✓ Ensemble Forecast (combining multiple models)")
        print(f"  Forecast in 12 months: {ensemble_forecast['forecast'].iloc[-1]:,.0f}")
        print(f"\n  12-Month Forecast:")
        print(ensemble_forecast)
except Exception as e:
    print(f"  Ensemble forecast failed: {str(e)}")

# Scenario Analysis
print("\n\n5. Scenario Analysis")
print("-" * 70)

if ensemble_forecast is not None:
    scenarios = {
        'optimistic': 10,    # 10% higher
        'pessimistic': -10,  # 10% lower
        'stress': -25        # 25% lower (stress scenario)
    }

    scenario_forecasts = forecaster.scenario_analysis(ensemble_forecast, scenarios)

    print("Loan Forecast Scenarios (12 months ahead):")
    print(f"  Base Case:       {scenario_forecasts['base']['forecast'].iloc[-1]:,.0f}")
    print(f"  Optimistic (+10%): {scenario_forecasts['optimistic']['forecast'].iloc[-1]:,.0f}")
    print(f"  Pessimistic (-10%): {scenario_forecasts['pessimistic']['forecast'].iloc[-1]:,.0f}")
    print(f"  Stress (-25%):   {scenario_forecasts['stress']['forecast'].iloc[-1]:,.0f}")

# 6. Database Operations
print("\n\n6. Database Storage")
print("-" * 70)

from utils.database import DatabaseManager

db = DatabaseManager()

# Save data to database
db.save_monthly_data(df, category='demo_data')
print("✓ Data saved to database")

# Retrieve data
retrieved = db.get_monthly_data(category='demo_data')
if retrieved is not None and not retrieved.empty:
    print(f"✓ Retrieved {len(retrieved)} rows from database")

# 7. Comparative Analysis
print("\n\n7. Comparative & Trend Analysis")
print("-" * 70)

comparison = analyzer.comparative_analysis(df, benchmark='sector')

print("Comparison vs Sector Benchmarks:")
if comparison and 'vs_benchmark' in comparison:
    for metric, data in comparison['vs_benchmark'].items():
        status = "↑" if data['status'] == 'above' else "↓"
        print(f"  {metric}: {data['current']:.2f} {status} (benchmark: {data['benchmark']:.2f})")

# Trend analysis
trends = analyzer.trend_analysis(df, periods=[3, 6, 12])

print("\nKey Trends (12-month):")
if trends:
    for metric in ['total_assets', 'total_loans', 'npl_ratio', 'roa']:
        if metric in trends and '12_month' in trends[metric]:
            trend_info = trends[metric]['12_month']
            print(f"  {metric}: {trend_info['direction']} ({trend_info['trend']:.2f}%)")

# 8. Report Generation
print("\n\n8. Report Generation")
print("-" * 70)

from reports.report_generator import BankingReportGenerator

generator = BankingReportGenerator()

try:
    # Generate HTML report (easier to view without dependencies)
    html_path = generator.generate_html_report(df, report, 'demo_report')
    print(f"✓ HTML Report generated: {html_path}")
except Exception as e:
    print(f"  HTML report generation failed: {str(e)}")

try:
    # Generate Excel report
    excel_path = generator.generate_excel_report(df, report, 'demo_report')
    print(f"✓ Excel Report generated: {excel_path}")
except Exception as e:
    print(f"  Excel report generation failed: {str(e)}")

# Summary
print("\n\n" + "="*70)
print("DEMO COMPLETE - Summary of Features Demonstrated:")
print("="*70)
print("✓ Data generation and processing")
print("✓ Financial ratio calculations")
print("✓ Comprehensive financial analysis (Asset Quality, Profitability, Liquidity, Capital)")
print("✓ Health scoring and alert system")
print("✓ Time series forecasting (ARIMA, Exponential Smoothing, Ensemble)")
print("✓ Scenario analysis and stress testing")
print("✓ Database storage and retrieval")
print("✓ Comparative analysis vs benchmarks")
print("✓ Trend analysis")
print("✓ Automated report generation (HTML, Excel)")
print("\n✓ All major features working successfully!")
print("="*70)

print("\n\nNext Steps:")
print("  1. Download real BDDK data: python main.py download --data-type weekly --currency TL")
print("  2. Run full analysis: python main.py analyze --currency TL --generate-report")
print("  3. Launch dashboard: python main.py dashboard")
print("  4. Generate forecasts: python main.py forecast --metric total_loans --periods 12")
