"""
BDDK Weekly Bulletin Data Scraper

This scraper downloads weekly banking sector data from BDDK website.
Includes both basic and advanced views.
"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))
from config import *


class BDDKWeeklyScraper:
    """Scraper for BDDK Weekly Banking Sector Data"""

    def __init__(self, headless=True):
        """
        Initialize the scraper

        Args:
            headless: Run browser in headless mode
        """
        self.base_url = BDDK_WEEKLY_URL
        self.advanced_url = f"{BDDK_WEEKLY_URL}/tr/Gelismis"
        self.data_dir = RAW_DATA_DIR / "weekly"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.driver = None

        # Setup logging
        logger.add(
            LOGS_DIR / "weekly_scraper_{time}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO"
        )

    def setup_driver(self):
        """Setup Selenium WebDriver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={SCRAPER_CONFIG['user_agent']}")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("WebDriver initialized successfully")

    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")

    def get_weekly_data(self, date=None, currency="TL", view_type="basic"):
        """
        Download weekly data for a specific date

        Args:
            date: Date string in format 'YYYY-MM-DD' or datetime object (None = latest)
            currency: Currency code (TL or USD)
            view_type: 'basic' or 'advanced'

        Returns:
            DataFrame with the data
        """
        try:
            if not self.driver:
                self.setup_driver()

            url = self.advanced_url if view_type == "advanced" else self.base_url
            logger.info(f"Fetching weekly data - Date: {date}, Currency: {currency}, View: {view_type}")

            self.driver.get(url)
            time.sleep(3)

            # If date is specified, select it
            if date:
                date_input = self.driver.find_element(By.ID, "date_picker")
                date_input.clear()
                date_input.send_keys(date if isinstance(date, str) else date.strftime('%Y-%m-%d'))
                time.sleep(1)

            # Select currency
            try:
                currency_select = self.driver.find_element(By.ID, "currency_select")
                currency_select.send_keys(currency)
                time.sleep(1)
            except:
                logger.warning("Currency selector not found, using default")

            # Wait for data to load
            time.sleep(2)

            # Extract table data
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Find all data tables
            tables = pd.read_html(page_source)

            all_data = []

            for idx, table in enumerate(tables):
                df = table.copy()
                df['date'] = date if date else datetime.now().strftime('%Y-%m-%d')
                df['currency'] = currency
                df['view_type'] = view_type
                df['table_index'] = idx
                df['download_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                all_data.append(df)

            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                logger.info(f"Successfully extracted {len(combined_df)} rows from {len(tables)} tables")
                return combined_df
            else:
                logger.warning("No tables found in the page")
                return None

        except Exception as e:
            logger.error(f"Error fetching weekly data: {str(e)}")
            return None

    def get_latest_data(self, currency="TL"):
        """
        Get the most recent weekly data

        Args:
            currency: Currency code

        Returns:
            DataFrame with latest data
        """
        logger.info("Fetching latest weekly data")

        # Get both basic and advanced views
        basic_data = self.get_weekly_data(currency=currency, view_type="basic")
        advanced_data = self.get_weekly_data(currency=currency, view_type="advanced")

        # Save the data
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if basic_data is not None:
            filename = self.data_dir / f"weekly_basic_{timestamp}_{currency}.csv"
            basic_data.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Saved basic view to {filename}")

        if advanced_data is not None:
            filename = self.data_dir / f"weekly_advanced_{timestamp}_{currency}.csv"
            advanced_data.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Saved advanced view to {filename}")

        return {"basic": basic_data, "advanced": advanced_data}

    def download_historical_weekly(self, start_date, end_date=None, currency="TL"):
        """
        Download historical weekly data for a date range

        Args:
            start_date: Start date (string 'YYYY-MM-DD' or datetime)
            end_date: End date (None = today)
            currency: Currency code

        Returns:
            DataFrame with all data
        """
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')

        if end_date is None:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        logger.info(f"Downloading weekly data from {start_date} to {end_date}")

        all_data = []
        current_date = start_date

        try:
            self.setup_driver()

            # Weekly data is published on Fridays typically
            while current_date <= end_date:
                # Only try Fridays
                if current_date.weekday() == 4:  # Friday
                    logger.info(f"Fetching data for week ending {current_date.strftime('%Y-%m-%d')}")

                    df = self.get_weekly_data(
                        date=current_date.strftime('%Y-%m-%d'),
                        currency=currency,
                        view_type="advanced"
                    )

                    if df is not None:
                        all_data.append(df)

                    time.sleep(SCRAPER_CONFIG['delay_between_requests'])

                current_date += timedelta(days=1)

        finally:
            self.close_driver()

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)

            # Save historical data
            filename = self.data_dir / f"weekly_historical_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{currency}.csv"
            combined_df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Saved historical data to {filename}")

            return combined_df
        else:
            logger.warning("No historical data collected")
            return None

    def extract_key_metrics(self, df):
        """
        Extract key banking metrics from raw data

        Args:
            df: Raw data DataFrame

        Returns:
            DataFrame with key metrics
        """
        if df is None or df.empty:
            return None

        # This will need to be customized based on actual BDDK table structure
        # Placeholder for metric extraction
        metrics = {
            'date': [],
            'total_assets': [],
            'total_loans': [],
            'total_deposits': [],
            'npl_ratio': [],
            'capital_adequacy_ratio': [],
            'liquid_assets': [],
            'equity': []
        }

        # Extract metrics based on table structure
        # This is a template - adjust based on actual data
        try:
            # Example extraction logic
            for date in df['date'].unique():
                date_data = df[df['date'] == date]
                metrics['date'].append(date)

                # Extract specific metrics from the data
                # You'll need to adjust these based on actual column names
                metrics['total_assets'].append(self._extract_value(date_data, 'Toplam Aktifler'))
                metrics['total_loans'].append(self._extract_value(date_data, 'Toplam Krediler'))
                metrics['total_deposits'].append(self._extract_value(date_data, 'Toplam Mevduat'))
                metrics['npl_ratio'].append(self._extract_value(date_data, 'Takipteki Krediler Oranı'))
                metrics['capital_adequacy_ratio'].append(self._extract_value(date_data, 'Sermaye Yeterliliği Rasyosu'))
                metrics['liquid_assets'].append(self._extract_value(date_data, 'Likit Aktifler'))
                metrics['equity'].append(self._extract_value(date_data, 'Özkaynaklar'))

            return pd.DataFrame(metrics)

        except Exception as e:
            logger.error(f"Error extracting metrics: {str(e)}")
            return None

    def _extract_value(self, df, metric_name):
        """Helper to extract specific metric value"""
        try:
            # Look for metric in first column and get value from second
            row = df[df.iloc[:, 0].str.contains(metric_name, na=False, case=False)]
            if not row.empty:
                return row.iloc[0, 1]
        except:
            pass
        return None


def main():
    """Example usage"""
    scraper = BDDKWeeklyScraper(headless=False)

    try:
        # Get latest weekly data
        logger.info("Downloading latest weekly data")
        latest_data = scraper.get_latest_data(currency="TL")

        if latest_data['basic'] is not None:
            print(f"\nBasic view: {len(latest_data['basic'])} rows")
            print(latest_data['basic'].head())

        if latest_data['advanced'] is not None:
            print(f"\nAdvanced view: {len(latest_data['advanced'])} rows")
            print(latest_data['advanced'].head())

    finally:
        scraper.close_driver()


if __name__ == "__main__":
    main()
