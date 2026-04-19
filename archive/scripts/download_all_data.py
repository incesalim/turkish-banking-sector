"""
Download BDDK data for 2024-2025
This script downloads all tables for all months in the specified years
"""

import sys
from pathlib import Path
from datetime import datetime

# Add scrapers to path
sys.path.append(str(Path(__file__).parent / "scrapers"))

from bddk_api_scraper import BDDKAPIScraper, BANK_TYPES


def download_data():
    """Download data for 2024-2025"""

    scraper = BDDKAPIScraper()

    try:
        scraper.connect_db()

        print("\n" + "="*80)
        print("BDDK DATA DOWNLOAD - 2024-2025")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Tables: 1-17")
        print(f"Bank types: {len(BANK_TYPES)}")
        print(f"Currency: TL")
        print("="*80 + "\n")

        total_rows = 0

        # 2024 - Full year
        print("\n" + "="*80)
        print("YEAR 2024")
        print("="*80)
        rows_2024 = scraper.download_year(2024, months=list(range(1, 13)))
        total_rows += rows_2024

        # 2025 - January to October (latest available)
        print("\n" + "="*80)
        print("YEAR 2025")
        print("="*80)
        rows_2025 = scraper.download_year(2025, months=list(range(1, 11)))
        total_rows += rows_2025

        print("\n" + "="*80)
        print("DOWNLOAD COMPLETE")
        print("="*80)
        print(f"Total rows downloaded: {total_rows:,}")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        # Print summary
        cursor = scraper.cursor

        print("\n=== DATABASE SUMMARY ===\n")

        tables = ['raw_api_responses', 'balance_sheet', 'income_statement',
                 'loans', 'deposits', 'financial_ratios', 'other_data']

        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            print(f'{table:25s}: {count:>10,} rows')

        print("\n=== DOWNLOAD SUCCESS RATE ===\n")
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM download_log
            GROUP BY status
        ''')
        for row in cursor.fetchall():
            print(f'{row[0]:10s}: {row[1]:>6,} attempts')

    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user!")
        print("Data up to this point has been saved.")

    except Exception as e:
        print(f"\n\nError during download: {e}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close_db()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    download_data()
