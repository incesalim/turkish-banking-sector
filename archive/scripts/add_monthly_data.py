"""
Add Monthly Data Script

Easy script to add new monthly BDDK data to the database.
Handles incremental updates without duplicates.
"""

import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from utils.monthly_data_manager import MonthlyDataManager
from scrapers.bddk_table_parser import BDDKTableParser
from loguru import logger


def add_from_html_file(html_file, year, month, currency='TL', data_type='bilanco'):
    """
    Add monthly data from HTML file

    Args:
        html_file: Path to HTML file containing BDDK table
        year: Year (e.g., 2024)
        month: Month (1-12)
        currency: Currency code
        data_type: Data type

    Returns:
        bool: Success status
    """
    print(f"\n{'='*70}")
    print(f"Adding Monthly Data: {year}-{month:02d}")
    print(f"{'='*70}\n")

    # Initialize parser and manager
    parser = BDDKTableParser()
    manager = MonthlyDataManager()

    # Parse HTML file
    print(f"📄 Parsing HTML file: {html_file}")
    df = parser.parse_from_file(html_file, data_type=data_type)

    if df is None or df.empty:
        print("❌ Error: Could not parse HTML file or no data found")
        return False

    print(f"✓ Parsed {len(df)} rows")

    # Extract key metrics
    print(f"\n📊 Key Metrics Found:")
    metrics = parser.extract_key_metrics(df)
    for key, value in metrics.items():
        print(f"  {key}: {value:,.0f}")

    # Add to database
    print(f"\n💾 Adding to database...")
    success = manager.add_monthly_data(
        df,
        year=year,
        month=month,
        currency=currency,
        data_type=data_type,
        check_duplicates=True
    )

    if success:
        print(f"\n✅ Successfully added data for {year}-{month:02d}")
        print(f"   Currency: {currency}")
        print(f"   Type: {data_type}")
        print(f"   Rows: {len(df)}")
    else:
        print(f"\n❌ Failed to add data")

    return success


def add_from_dataframe(df, year, month, currency='TL', data_type='bilanco'):
    """
    Add monthly data from DataFrame

    Args:
        df: DataFrame with parsed data
        year: Year
        month: Month
        currency: Currency
        data_type: Data type

    Returns:
        bool: Success status
    """
    manager = MonthlyDataManager()

    return manager.add_monthly_data(
        df,
        year=year,
        month=month,
        currency=currency,
        data_type=data_type,
        check_duplicates=True
    )


def show_data_summary():
    """Show summary of existing data"""
    print(f"\n{'='*70}")
    print("DATABASE SUMMARY")
    print(f"{'='*70}\n")

    manager = MonthlyDataManager()

    # TL Summary
    print("📊 Turkish Lira (TL) Data:")
    summary_tl = manager.get_data_summary(currency='TL')

    if summary_tl['total_periods'] > 0:
        print(f"  Total Periods: {summary_tl['total_periods']}")
        if summary_tl['date_range']:
            print(f"  Date Range: {summary_tl['date_range']['from']} to {summary_tl['date_range']['to']}")

        print(f"\n  Data Types:")
        for dtype, info in summary_tl['data_types'].items():
            print(f"    {dtype}:")
            print(f"      Periods: {info['count']}")
            print(f"      Latest: {info['latest'][0]}-{info['latest'][1]:02d}")
            if 'total_rows' in info:
                print(f"      Total Rows: {info['total_rows']:,}")
    else:
        print("  No data available")

    # USD Summary
    print(f"\n💵 US Dollar (USD) Data:")
    summary_usd = manager.get_data_summary(currency='USD')

    if summary_usd['total_periods'] > 0:
        print(f"  Total Periods: {summary_usd['total_periods']}")
        if summary_usd['date_range']:
            print(f"  Date Range: {summary_usd['date_range']['from']} to {summary_usd['date_range']['to']}")
    else:
        print("  No data available")

    print(f"\n{'='*70}\n")


def check_missing_periods(start_year, end_year, currency='TL', data_type='bilanco'):
    """Check for missing data periods"""
    print(f"\n{'='*70}")
    print(f"MISSING PERIODS CHECK: {start_year}-{end_year}")
    print(f"{'='*70}\n")

    manager = MonthlyDataManager()
    missing = manager.get_missing_periods(start_year, end_year, currency, data_type)

    if not missing:
        print("✅ No missing periods - data is complete!")
    else:
        print(f"⚠️  Found {len(missing)} missing periods:\n")

        for year, month in missing[:20]:  # Show first 20
            print(f"  {year}-{month:02d} - {datetime(year, month, 1).strftime('%B %Y')}")

        if len(missing) > 20:
            print(f"\n  ... and {len(missing) - 20} more")

    print(f"\n{'='*70}\n")


def interactive_add():
    """Interactive mode to add data"""
    print(f"\n{'='*70}")
    print("INTERACTIVE DATA ENTRY")
    print(f"{'='*70}\n")

    # Get HTML file
    html_file = input("Enter path to HTML file: ").strip()

    if not Path(html_file).exists():
        print("❌ File not found!")
        return

    # Get year/month
    try:
        year = int(input("Enter year (e.g., 2024): ").strip())
        month = int(input("Enter month (1-12): ").strip())

        if not (1 <= month <= 12):
            print("❌ Invalid month!")
            return

    except ValueError:
        print("❌ Invalid input!")
        return

    # Get currency
    currency = input("Enter currency (TL/USD) [TL]: ").strip().upper() or 'TL'

    # Get data type
    print("\nData types:")
    print("  1. bilanco (Balance Sheet)")
    print("  2. gelir_gider (Income Statement)")
    print("  3. krediler (Loans)")
    print("  4. mevduat (Deposits)")

    dtype_choice = input("Select data type (1-4) [1]: ").strip() or '1'

    data_type_map = {
        '1': 'bilanco',
        '2': 'gelir_gider',
        '3': 'krediler',
        '4': 'mevduat'
    }

    data_type = data_type_map.get(dtype_choice, 'bilanco')

    # Confirm
    print(f"\n📋 Summary:")
    print(f"  File: {html_file}")
    print(f"  Period: {year}-{month:02d}")
    print(f"  Currency: {currency}")
    print(f"  Type: {data_type}")

    confirm = input("\nProceed? (y/n): ").strip().lower()

    if confirm == 'y':
        add_from_html_file(html_file, year, month, currency, data_type)
    else:
        print("❌ Cancelled")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Add Monthly BDDK Data")

    parser.add_argument('--file', help='HTML file to parse')
    parser.add_argument('--year', type=int, help='Year')
    parser.add_argument('--month', type=int, help='Month')
    parser.add_argument('--currency', default='TL', help='Currency (TL/USD)')
    parser.add_argument('--type', default='bilanco', help='Data type')
    parser.add_argument('--summary', action='store_true', help='Show data summary')
    parser.add_argument('--check-missing', action='store_true', help='Check missing periods')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')

    args = parser.parse_args()

    if args.summary:
        show_data_summary()

    elif args.check_missing:
        start = args.year or 2020
        end = args.year or datetime.now().year
        check_missing_periods(start, end, args.currency, args.type)

    elif args.interactive or (not args.file and not args.year):
        interactive_add()

    elif args.file and args.year and args.month:
        add_from_html_file(
            args.file,
            args.year,
            args.month,
            args.currency,
            args.type
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
