"""
BDDK Analysis - Simple Entry Point

Provides easy access to:
1. Download monthly BDDK data
2. Run the dashboard
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    print("\n" + "=" * 60)
    print("BDDK Banking Analytics System")
    print("=" * 60)
    print("\nWhat would you like to do?")
    print("\n1. Download Monthly Data")
    print("2. Run Dashboard")
    print("3. Exit")
    print("\n" + "=" * 60)

    choice = input("\nEnter your choice (1-3): ").strip()

    if choice == "1":
        print("\n📥 Launching monthly data downloader...")
        from src.scrapers.monthly_scraper import BDDKMonthlyScraper
        from src.config import START_YEAR, CURRENCIES
        from datetime import datetime

        # Ask for parameters
        print("\nDownload Options:")
        print("1. Download all available data")
        print("2. Download specific year")

        option = input("\nChoose option (1-2): ").strip()

        scraper = BDDKMonthlyScraper(headless=True)
        try:
            if option == "2":
                year = input("Enter year (e.g., 2024): ").strip()
                currency = input("Enter currency (TL/USD, default TL): ").strip() or "TL"
                print(f"\n⏳ Downloading data for {year} in {currency}...")
                scraper.download_year_data(int(year), currency=currency)
            else:
                print(f"\n⏳ Downloading all monthly data from {START_YEAR} to {datetime.now().year}...")
                scraper.download_all_data(
                    start_year=START_YEAR,
                    end_year=datetime.now().year,
                    currencies=CURRENCIES
                )
            print("\n✅ Download completed!")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            scraper.close_driver()

    elif choice == "2":
        print("\n🚀 Launching dashboard...")
        print("\nDashboard will open at: http://localhost:8050")
        print("Press Ctrl+C to stop the server\n")

        from src.dashboard.app import app
        app.run_server(debug=True, host='0.0.0.0', port=8050)

    elif choice == "3":
        print("\n👋 Goodbye!\n")
        sys.exit(0)

    else:
        print("\n❌ Invalid choice. Please run again and select 1, 2, or 3.\n")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
