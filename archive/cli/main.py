"""
Main Entry Point for BDDK Banking Sector Analysis System

This script provides a command-line interface to run all analysis components.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# Import modules
from scrapers.monthly_scraper import BDDKMonthlyScraper
from scrapers.weekly_scraper import BDDKWeeklyScraper
from utils.database import DatabaseManager
from utils.data_processor import DataProcessor
from analysis.financial_analyzer import BankingFinancialAnalyzer
from models.forecasting import BankingForecaster
from reports.report_generator import BankingReportGenerator
from visualizations.dashboard import BankingDashboard
from config import *


def setup_logging():
    """Setup logging configuration"""
    logger.add(
        LOGS_DIR / "main_{time}.log",
        rotation="1 day",
        retention="30 days",
        level="INFO"
    )
    logger.info("BDDK Banking Analysis System started")


def download_data(args):
    """Download data from BDDK"""
    logger.info("Starting data download...")

    if args.data_type == 'monthly' or args.data_type == 'all':
        logger.info("Downloading monthly data...")
        scraper = BDDKMonthlyScraper(headless=args.headless)
        try:
            if args.year:
                scraper.download_year_data(args.year, currency=args.currency)
            else:
                scraper.download_all_data(
                    start_year=args.start_year or START_YEAR,
                    end_year=args.end_year or datetime.now().year,
                    currencies=[args.currency] if args.currency else CURRENCIES
                )
        finally:
            scraper.close_driver()

    if args.data_type == 'weekly' or args.data_type == 'all':
        logger.info("Downloading weekly data...")
        scraper = BDDKWeeklyScraper(headless=args.headless)
        try:
            scraper.get_latest_data(currency=args.currency)
        finally:
            scraper.close_driver()

    logger.info("Data download completed")


def process_data(args):
    """Process and clean downloaded data"""
    logger.info("Processing data...")

    processor = DataProcessor()
    db = DatabaseManager()

    # Process monthly data
    monthly_files = list((RAW_DATA_DIR / "monthly").glob("*.csv"))
    logger.info(f"Found {len(monthly_files)} monthly data files")

    for file_path in monthly_files:
        logger.info(f"Processing {file_path.name}")

        import pandas as pd
        df = pd.read_csv(file_path, encoding='utf-8-sig')

        # Clean data
        df = processor.clean_numeric_columns(df)
        df = processor.standardize_column_names(df)
        df = processor.handle_missing_data(df, strategy='interpolate')
        df = processor.remove_duplicates(df)

        # Calculate ratios
        df = processor.calculate_financial_ratios(df)

        # Save to database
        category = file_path.stem.split('_')[0]
        db.save_monthly_data(df, category)

        # Save processed file
        processed_path = PROCESSED_DATA_DIR / file_path.name
        df.to_csv(processed_path, index=False, encoding='utf-8-sig')

    # Process weekly data
    weekly_files = list((RAW_DATA_DIR / "weekly").glob("*.csv"))
    logger.info(f"Found {len(weekly_files)} weekly data files")

    for file_path in weekly_files:
        logger.info(f"Processing {file_path.name}")

        import pandas as pd
        df = pd.read_csv(file_path, encoding='utf-8-sig')

        df = processor.clean_numeric_columns(df)
        df = processor.standardize_column_names(df)

        db.save_weekly_data(df)

        processed_path = PROCESSED_DATA_DIR / file_path.name
        df.to_csv(processed_path, index=False, encoding='utf-8-sig')

    logger.info("Data processing completed")


def analyze_data(args):
    """Perform financial analysis"""
    logger.info("Starting financial analysis...")

    # Load data
    db = DatabaseManager()
    data = db.get_monthly_data(currency=args.currency)

    if data is None or data.empty:
        logger.error("No data available for analysis")
        return

    # Run analysis
    analyzer = BankingFinancialAnalyzer()
    report = analyzer.comprehensive_analysis(data)

    # Display results
    print("\n" + "="*60)
    print("TURKISH BANKING SECTOR ANALYSIS REPORT")
    print("="*60)
    print(f"\nOverall Health Score: {report['overall_health']}/100")
    print(f"Total Alerts: {len(report['all_alerts'])}")

    if report['all_alerts']:
        print("\nAlerts:")
        for alert in report['all_alerts']:
            print(f"  - {alert}")

    # Asset Quality
    if 'asset_quality' in report:
        print("\n" + "-"*60)
        print("ASSET QUALITY")
        print("-"*60)
        aq = report['asset_quality'].get('metrics', {})
        for metric, value in aq.items():
            print(f"  {metric}: {value}")

    # Profitability
    if 'profitability' in report:
        print("\n" + "-"*60)
        print("PROFITABILITY")
        print("-"*60)
        prof = report['profitability'].get('metrics', {})
        for metric, value in prof.items():
            print(f"  {metric}: {value}")

    # Generate report if requested
    if args.generate_report:
        generator = BankingReportGenerator()
        report_path = generator.generate_comprehensive_report(
            data=data,
            analysis_results=report,
            format=args.report_format
        )
        print(f"\nReport saved to: {report_path}")

    logger.info("Analysis completed")


def forecast_data(args):
    """Generate forecasts"""
    logger.info("Starting forecasting...")

    # Load data
    db = DatabaseManager()
    data = db.get_monthly_data(currency=args.currency)

    if data is None or data.empty:
        logger.error("No data available for forecasting")
        return

    forecaster = BankingForecaster()

    # Select metric to forecast
    metric = args.metric or 'total_loans'

    if metric not in data.columns:
        logger.error(f"Metric {metric} not found in data")
        return

    # Prepare time series
    ts = forecaster.prepare_time_series(
        data,
        date_column='date',
        value_column=metric
    )

    # Generate forecasts
    print(f"\nForecasting {metric} for {args.periods} periods...")

    if args.method == 'auto_arima' or args.method == 'all':
        forecast = forecaster.auto_arima_forecast(ts, periods=args.periods)
        print("\nAuto ARIMA Forecast:")
        print(forecast)

    if args.method == 'exponential_smoothing' or args.method == 'all':
        forecast = forecaster.exponential_smoothing_forecast(ts, periods=args.periods)
        print("\nExponential Smoothing Forecast:")
        print(forecast)

    if args.method == 'ensemble' or args.method == 'all':
        forecast = forecaster.ensemble_forecast(ts, periods=args.periods)
        print("\nEnsemble Forecast:")
        print(forecast)

    logger.info("Forecasting completed")


def run_dashboard(args):
    """Launch interactive dashboard"""
    logger.info("Starting dashboard...")

    dashboard = BankingDashboard()
    print(f"\nDashboard running at http://localhost:{args.port}")
    print("Press Ctrl+C to stop\n")

    dashboard.run(debug=args.debug, port=args.port)


def generate_report(args):
    """Generate reports"""
    logger.info("Generating report...")

    # Load data
    db = DatabaseManager()
    data = db.get_monthly_data(currency=args.currency)

    if data is None or data.empty:
        logger.error("No data available")
        return

    # Run analysis
    analyzer = BankingFinancialAnalyzer()
    analysis_results = analyzer.comprehensive_analysis(data)

    # Generate report
    generator = BankingReportGenerator()
    report_path = generator.generate_comprehensive_report(
        data=data,
        analysis_results=analysis_results,
        format=args.format
    )

    print(f"\nReport generated: {report_path}")
    logger.info(f"Report saved to {report_path}")


def main():
    """Main entry point"""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="BDDK Banking Sector Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Download command
    download_parser = subparsers.add_parser('download', help='Download data from BDDK')
    download_parser.add_argument('--data-type', choices=['monthly', 'weekly', 'all'],
                                 default='all', help='Type of data to download')
    download_parser.add_argument('--currency', choices=['TL', 'USD'],
                                 default='TL', help='Currency')
    download_parser.add_argument('--year', type=int, help='Specific year to download')
    download_parser.add_argument('--start-year', type=int, help='Start year')
    download_parser.add_argument('--end-year', type=int, help='End year')
    download_parser.add_argument('--headless', action='store_true',
                                 help='Run browser in headless mode')

    # Process command
    process_parser = subparsers.add_parser('process', help='Process downloaded data')
    process_parser.add_argument('--currency', choices=['TL', 'USD'],
                               default='TL', help='Currency')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze banking data')
    analyze_parser.add_argument('--currency', choices=['TL', 'USD'],
                               default='TL', help='Currency')
    analyze_parser.add_argument('--generate-report', action='store_true',
                               help='Generate analysis report')
    analyze_parser.add_argument('--report-format', choices=['pdf', 'html', 'excel'],
                               default='pdf', help='Report format')

    # Forecast command
    forecast_parser = subparsers.add_parser('forecast', help='Generate forecasts')
    forecast_parser.add_argument('--currency', choices=['TL', 'USD'],
                                default='TL', help='Currency')
    forecast_parser.add_argument('--metric', help='Metric to forecast')
    forecast_parser.add_argument('--periods', type=int, default=12,
                                help='Number of periods to forecast')
    forecast_parser.add_argument('--method',
                                choices=['auto_arima', 'exponential_smoothing', 'ensemble', 'all'],
                                default='ensemble', help='Forecasting method')

    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Launch interactive dashboard')
    dashboard_parser.add_argument('--port', type=int, default=8050, help='Port number')
    dashboard_parser.add_argument('--debug', action='store_true', help='Debug mode')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate comprehensive report')
    report_parser.add_argument('--currency', choices=['TL', 'USD'],
                              default='TL', help='Currency')
    report_parser.add_argument('--format', choices=['pdf', 'html', 'excel'],
                              default='pdf', help='Report format')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        if args.command == 'download':
            download_data(args)
        elif args.command == 'process':
            process_data(args)
        elif args.command == 'analyze':
            analyze_data(args)
        elif args.command == 'forecast':
            forecast_data(args)
        elif args.command == 'dashboard':
            run_dashboard(args)
        elif args.command == 'report':
            generate_report(args)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
