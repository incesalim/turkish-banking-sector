"""
Complete October 2025 data download
"""

import sys
from pathlib import Path
from datetime import datetime

# Add scrapers to path
sys.path.append(str(Path(__file__).parent / "scrapers"))

from bddk_api_scraper import BDDKAPIScraper

def download_october_2025():
    """Download complete October 2025 data"""

    scraper = BDDKAPIScraper()

    try:
        scraper.connect_db()

        print("\n" + "="*80)
        print("BDDK DATA DOWNLOAD - OCTOBER 2025")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Downloading: October 2025 (1 month)")
        print(f"Tables: 1-17")
        print(f"Bank types: 10")
        print(f"Currency: TL")
        print("="*80 + "\n")

        # Download October (month 10)
        print("\n" + "="*80)
        print("DOWNLOADING OCTOBER 2025")
        print("="*80)
        rows = scraper.download_year(2025, months=[10])

        print("\n" + "="*80)
        print("DOWNLOAD COMPLETE")
        print("="*80)
        print(f"Total rows downloaded: {rows:,}")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        # Print summary
        cursor = scraper.cursor

        print("\n=== OCTOBER 2025 DATA ===\n")
        cursor.execute('''
            SELECT COUNT(*)
            FROM balance_sheet
            WHERE year = 2025 AND month = 10
        ''')
        count = cursor.fetchone()[0]
        print(f'October 2025 rows: {count}')

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
    download_october_2025()
