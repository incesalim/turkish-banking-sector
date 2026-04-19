"""
BDDK Monthly Bulletin Data Scraper

This scraper downloads monthly banking sector data from BDDK website.
Supports multiple years, currencies, and data categories.
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
from datetime import datetime
from pathlib import Path
import sys
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.config import *


class BDDKMonthlyScraper:
    """Scraper for BDDK Monthly Banking Sector Data"""

    def __init__(self, headless=True):
        """
        Initialize the scraper

        Args:
            headless: Run browser in headless mode
        """
        self.base_url = BDDK_MONTHLY_URL
        self.data_dir = RAW_DATA_DIR / "monthly"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.driver = None

        # Setup logging
        logger.add(
            LOGS_DIR / "monthly_scraper_{time}.log",
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

    def get_monthly_data(self, year, month, currency="TL", category="balance_sheet"):
        """
        Download monthly data for specific parameters

        Args:
            year: Year (2004-2025)
            month: Month (1-12)
            currency: Currency code (TL or USD)
            category: Data category

        Returns:
            DataFrame with the data
        """
        try:
            if not self.driver:
                self.setup_driver()

            logger.info(f"Fetching data for {year}-{month:02d}, Currency: {currency}, Category: {category}")

            self.driver.get(self.base_url)
            time.sleep(2)

            # Select year
            year_select = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "select_year"))
            )
            year_select.send_keys(str(year))
            time.sleep(1)

            # Select month
            month_select = self.driver.find_element(By.ID, "select_month")
            month_select.send_keys(str(month))
            time.sleep(1)

            # Select currency
            currency_select = self.driver.find_element(By.ID, "select_currency")
            currency_select.send_keys(currency)
            time.sleep(1)

            # Click generate report button
            generate_btn = self.driver.find_element(By.ID, "generate_report")
            generate_btn.click()

            # Wait for data to load
            time.sleep(3)

            # Extract table data
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Find data tables
            tables = pd.read_html(page_source)

            if tables:
                df = tables[0]  # Main data table
                df['year'] = year
                df['month'] = month
                df['currency'] = currency
                df['category'] = category
                df['download_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                logger.info(f"Successfully extracted {len(df)} rows")
                return df
            else:
                logger.warning("No tables found in the page")
                return None

        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            return None

    def download_year_data(self, year, currency="TL", categories=None):
        """
        Download all monthly data for a specific year

        Args:
            year: Year to download
            currency: Currency code
            categories: List of categories (None = all)

        Returns:
            Dictionary of DataFrames by category
        """
        if categories is None:
            categories = list(MONTHLY_CATEGORIES.keys())

        all_data = {}

        for category in categories:
            category_data = []

            for month in range(1, 13):
                logger.info(f"Processing {year}-{month:02d} - {category}")

                df = self.get_monthly_data(year, month, currency, category)

                if df is not None:
                    category_data.append(df)

                time.sleep(SCRAPER_CONFIG['delay_between_requests'])

            if category_data:
                all_data[category] = pd.concat(category_data, ignore_index=True)

                # Save to file
                filename = self.data_dir / f"{category}_{year}_{currency}.csv"
                all_data[category].to_csv(filename, index=False, encoding='utf-8-sig')
                logger.info(f"Saved data to {filename}")

        return all_data

    def download_all_data(self, start_year=None, end_year=None, currencies=None):
        """
        Download all available data

        Args:
            start_year: Starting year (default: 2004)
            end_year: Ending year (default: current year)
            currencies: List of currencies (default: ["TL", "USD"])
        """
        if start_year is None:
            start_year = START_YEAR
        if end_year is None:
            end_year = datetime.now().year
        if currencies is None:
            currencies = CURRENCIES

        logger.info(f"Starting full data download: {start_year}-{end_year}")

        try:
            self.setup_driver()

            for year in range(start_year, end_year + 1):
                for currency in currencies:
                    logger.info(f"Downloading {year} data in {currency}")
                    self.download_year_data(year, currency)

        finally:
            self.close_driver()

        logger.info("Data download completed")

    def get_available_periods(self):
        """
        Get list of available data periods from the website

        Returns:
            List of (year, month) tuples
        """
        try:
            if not self.driver:
                self.setup_driver()

            self.driver.get(self.base_url)
            time.sleep(2)

            # Extract available years and months
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # This would need to be adjusted based on actual HTML structure
            # Placeholder logic
            periods = []
            current_year = datetime.now().year

            for year in range(2004, current_year + 1):
                max_month = 12 if year < current_year else datetime.now().month
                for month in range(1, max_month + 1):
                    periods.append((year, month))

            return periods

        except Exception as e:
            logger.error(f"Error getting available periods: {str(e)}")
            return []


def main():
    """Example usage"""
    scraper = BDDKMonthlyScraper(headless=False)

    try:
        # Download latest month data
        current_year = datetime.now().year
        current_month = datetime.now().month - 1  # Previous month

        if current_month == 0:
            current_month = 12
            current_year -= 1

        logger.info(f"Downloading latest data: {current_year}-{current_month:02d}")

        df = scraper.get_monthly_data(current_year, current_month, "TL")

        if df is not None:
            print(f"\nDownloaded {len(df)} rows")
            print(df.head())

    finally:
        scraper.close_driver()


if __name__ == "__main__":
    main()
