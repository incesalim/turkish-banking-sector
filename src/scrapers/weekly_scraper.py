"""
BDDK Weekly Bulletin Data Scraper
=================================
Scrapes weekly banking sector data from BDDK website.
Supports historical data from 2014 onwards.
"""

import re
import time
import json
import pandas as pd
from io import StringIO
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.config import BDDK_WEEKLY_URL, RAW_DATA_DIR, LOGS_DIR, SCRAPER_CONFIG, SCRAPER_DELAYS


# Weekly data categories and their menu items
WEEKLY_CATEGORIES = {
    'krediler': 'Krediler',
    'takipteki_alacaklar': 'Takipteki Alacaklar',
    'mevduat': 'Mevduat',
    'menkul_degerler': 'Menkul Değerler',
    'diger_bilanco': 'Diğer Bilanço Kalemleri',
    'bilanco_disi': 'Bilanço Dışı İşlemler',
    'yabanci_para_pozisyonu': 'Yabancı Para Pozisyonu',
}

# Bank type selectors
BANK_TYPES = {
    'sektor': 'Sektör',
    'mevduat': 'Mevduat',
    'kalkinma_yatirim': 'Kalkınma ve Yatırım',
    'katilim': 'Katılım',
    'kamu': 'Kamu',
    'yabanci': 'Yabancı',
    'yerli_ozel': 'Yerli Özel',
}


class BDDKWeeklyScraper:
    """Scraper for BDDK Weekly Banking Sector Data"""

    def __init__(self, headless: bool = False):
        """
        Initialize the scraper.

        Args:
            headless: Run browser in headless mode (may be blocked by site)
        """
        self.base_url = BDDK_WEEKLY_URL
        self.data_dir = RAW_DATA_DIR / "weekly"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.driver = None
        self.periods_cache = None

        # Setup logging
        logger.add(
            LOGS_DIR / "weekly_scraper_{time}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO"
        )

    def setup_driver(self):
        """Setup Selenium WebDriver with anti-detection settings"""
        options = Options()

        if self.headless:
            options.add_argument('--headless')
        else:
            options.add_argument('--start-minimized')

        # Anti-detection settings
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(f"user-agent={SCRAPER_CONFIG['user_agent']}")

        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )
        logger.info("WebDriver initialized successfully")

    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("WebDriver closed")

    def load_page(self):
        """Load the weekly bulletin page"""
        if not self.driver:
            self.setup_driver()

        self.driver.get(self.base_url)
        time.sleep(SCRAPER_DELAYS['page_load'])  # Wait for JavaScript to load

        # Check if page loaded successfully
        if 'blocked' in self.driver.title.lower():
            logger.error("Page blocked - try running with headless=False")
            return False

        logger.info(f"Page loaded: {self.driver.title}")
        return True

    def get_available_periods(self) -> List[Tuple[str, str]]:
        """
        Get all available periods from the dropdown.

        Returns:
            List of (period_id, period_label) tuples
        """
        if self.periods_cache is not None:
            return self.periods_cache

        if not self.load_page():
            return []

        try:
            wait = WebDriverWait(self.driver, 10)
            donem_element = wait.until(EC.presence_of_element_located((By.ID, 'Donem')))
            donem_select = Select(donem_element)

            periods = []
            for option in donem_select.options:
                period_id = option.get_attribute('value')
                period_label = option.text.strip()
                if period_id and period_label:
                    periods.append((period_id, period_label))

            self.periods_cache = periods
            logger.info(f"Found {len(periods)} available periods")
            return periods

        except Exception as e:
            logger.error(f"Error getting periods: {e}")
            return []

    def parse_period_label(self, label: str) -> Optional[datetime]:
        """
        Parse period label to date.

        Args:
            label: Period label like "Ocak/16 (3. Hafta)"

        Returns:
            datetime object or None
        """
        # Turkish month names
        month_map = {
            'Ocak': 1, 'Şubat': 2, 'Mart': 3, 'Nisan': 4,
            'Mayıs': 5, 'Haziran': 6, 'Temmuz': 7, 'Ağustos': 8,
            'Eylül': 9, 'Ekim': 10, 'Kasım': 11, 'Aralık': 12
        }

        # Also handle HTML entities
        label = label.replace('&#252;', 'ü')

        try:
            # Pattern: "Ocak/16 (3. Hafta)" or "Aralık/26 (52. Hafta)"
            match = re.match(r'(\w+)/(\d+)\s*\((\d+)\.\s*Hafta\)', label)
            if match:
                month_name, day, week = match.groups()
                month = month_map.get(month_name)
                if month:
                    # Determine year from week number
                    # This is approximate - weeks near year-end may need adjustment
                    year = datetime.now().year
                    if int(week) > 40 and month <= 2:
                        year -= 1  # Previous year
                    return datetime(year, month, int(day))
        except Exception as e:
            logger.warning(f"Could not parse period label '{label}': {e}")

        return None

    def select_period(self, period_id: str) -> bool:
        """
        Select a specific period and fetch data.

        Args:
            period_id: Period ID from dropdown

        Returns:
            True if successful
        """
        try:
            wait = WebDriverWait(self.driver, 10)

            # Select the period
            donem_element = wait.until(EC.presence_of_element_located((By.ID, 'Donem')))
            donem_select = Select(donem_element)
            donem_select.select_by_value(period_id)
            time.sleep(SCRAPER_DELAYS['after_select'])

            # Click the "Getir" button
            buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button, input[type="submit"]')
            for btn in buttons:
                text = btn.text or btn.get_attribute('value') or ''
                if 'getir' in text.lower():
                    btn.click()
                    time.sleep(SCRAPER_DELAYS['after_submit'])
                    return True

            # Fallback: try form submit
            form = self.driver.find_element(By.CSS_SELECTOR, 'form[action*="DonemDegistir"]')
            form.submit()
            time.sleep(SCRAPER_DELAYS['after_submit'])
            return True

        except Exception as e:
            logger.error(f"Error selecting period {period_id}: {e}")
            return False

    def select_category(self, category_name: str) -> bool:
        """
        Select a data category (e.g., Krediler, Mevduat).

        Args:
            category_name: Category name in Turkish

        Returns:
            True if successful
        """
        try:
            # Find and click the category menu item
            menu_items = self.driver.find_elements(By.CSS_SELECTOR, 'a.nav-link, a.dropdown-item, li a')
            for item in menu_items:
                if category_name in item.text:
                    item.click()
                    time.sleep(SCRAPER_DELAYS['after_submit'])
                    return True

            logger.warning(f"Category '{category_name}' not found")
            return False

        except Exception as e:
            logger.error(f"Error selecting category: {e}")
            return False

    def parse_turkish_number(self, value: str) -> Optional[float]:
        """
        Parse Turkish formatted number (1.234.567,89) to float.

        Args:
            value: String number in Turkish format

        Returns:
            Float value or None
        """
        if not value or pd.isna(value):
            return None

        try:
            # Remove thousands separator (.) and convert decimal separator (,) to (.)
            value = str(value).strip()
            value = value.replace('.', '').replace(',', '.')
            return float(value)
        except:
            return None

    def extract_table_data(self) -> Dict[str, pd.DataFrame]:
        """
        Extract all data tables from current page.

        Returns:
            Dictionary of DataFrames by table type
        """
        try:
            html = self.driver.page_source
            dfs = pd.read_html(StringIO(html), flavor='html5lib')

            result = {}
            for i, df in enumerate(dfs):
                if len(df.columns) >= 4 and len(df) > 10:
                    # Get table type from header
                    header = str(df.columns[1]) if len(df.columns) > 1 else ''

                    # Extract date from header
                    date_match = re.search(r'(\d+)\s+(\w+)\s+(\d{4})', header)
                    if date_match:
                        result[f'table_{i}'] = {
                            'header': header,
                            'date_str': date_match.group(0),
                            'data': df
                        }

            return result

        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            return {}

    def get_loans_data(self, period_id: str) -> Optional[pd.DataFrame]:
        """
        Get loans (Krediler) data for a specific period.

        Args:
            period_id: Period ID

        Returns:
            DataFrame with loans data
        """
        if not self.select_period(period_id):
            return None

        try:
            html = self.driver.page_source
            dfs = pd.read_html(StringIO(html), flavor='html5lib')

            # Find the best table with date in header
            date_str = None
            best_df = None

            for df in dfs:
                if len(df.columns) >= 4 and len(df) >= 20:
                    header = str(df.columns[1]) if len(df.columns) > 1 else ''

                    # Check for date pattern in header
                    date_match = re.search(r'(\d+)\s+([A-Za-zÇçĞğİıÖöŞşÜü]+)\s+(\d{4})', header)

                    if date_match:
                        date_str = date_match.group(0)

                    # Keep first suitable table as backup
                    if ('Krediler' in header or 'Sektör' in header) and best_df is None:
                        best_df = df

            if best_df is None:
                logger.warning(f"No loans table found for period {period_id}")
                return None

            # Clean up the dataframe
            df = best_df.copy()
            df.columns = ['row_id', 'item_name', 'tp_value', 'yp_value', 'total_value']

            # Parse numbers
            for col in ['tp_value', 'yp_value', 'total_value']:
                df[col] = df[col].apply(self.parse_turkish_number)

            # Add date from best matching table
            df['date_str'] = date_str
            if not date_str:
                logger.debug(f"No date found for period {period_id}")

            df['period_id'] = period_id

            return df

        except Exception as e:
            logger.error(f"Error getting loans data: {e}")
            return None

    def scrape_multiple_periods(
        self,
        period_ids: List[str] = None,
        num_weeks: int = 13,
        category: str = 'krediler'
    ) -> pd.DataFrame:
        """
        Scrape data for multiple periods.

        Args:
            period_ids: List of period IDs to scrape (None = latest N weeks)
            num_weeks: Number of weeks to scrape if period_ids is None
            category: Data category to scrape

        Returns:
            DataFrame with combined data
        """
        if not self.load_page():
            return pd.DataFrame()

        # Get available periods
        periods = self.get_available_periods()
        if not periods:
            return pd.DataFrame()

        # Select periods to scrape
        if period_ids is None:
            # Get latest N periods
            period_ids = [p[0] for p in periods[:num_weeks]]

        all_data = []

        for i, period_id in enumerate(period_ids):
            logger.info(f"Scraping period {period_id} ({i+1}/{len(period_ids)})")

            df = self.get_loans_data(period_id)
            if df is not None:
                all_data.append(df)

            # Delay between requests
            if i < len(period_ids) - 1:
                time.sleep(SCRAPER_CONFIG['delay_between_requests'])

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)

            # Save to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = self.data_dir / f"{category}_{timestamp}.csv"
            combined.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Saved {len(combined)} rows to {filename}")

            return combined

        return pd.DataFrame()

    def scrape_last_13_weeks(self) -> pd.DataFrame:
        """
        Scrape the last 13 weeks of loans data for 13-week growth calculation.

        Returns:
            DataFrame with 13 weeks of data
        """
        return self.scrape_multiple_periods(num_weeks=14)  # 14 to have some buffer

    def scrape_full_year(self, year: int) -> pd.DataFrame:
        """
        Scrape all weeks for a specific year.

        Args:
            year: Year to scrape

        Returns:
            DataFrame with full year data
        """
        if not self.load_page():
            return pd.DataFrame()

        periods = self.get_available_periods()
        year_periods = []

        for period_id, label in periods:
            # Check if period is in the target year
            match = re.search(r'\d{4}', label)
            if match and int(match.group()) == year:
                year_periods.append(period_id)
            elif str(year) in label:
                year_periods.append(period_id)

        logger.info(f"Found {len(year_periods)} periods for year {year}")
        return self.scrape_multiple_periods(period_ids=year_periods)


def main():
    """Example usage"""
    scraper = BDDKWeeklyScraper(headless=False)

    try:
        # Get available periods
        periods = scraper.get_available_periods()
        print(f"\nAvailable periods: {len(periods)}")
        print(f"Latest: {periods[0]}")
        print(f"Oldest: {periods[-1]}")

        # Scrape last 13 weeks
        df = scraper.scrape_last_13_weeks()

        if not df.empty:
            print(f"\nScraped {len(df)} rows")
            print(f"Periods: {df['period_id'].nunique()}")

            # Show summary
            total_loans = df[df['item_name'].str.contains('Toplam Krediler', na=False)]
            if not total_loans.empty:
                print("\nTotal Loans by Period:")
                for _, row in total_loans.head(5).iterrows():
                    print(f"  {row.get('date_str', row['period_id'])}: {row['total_value']:,.0f} M TL")

    finally:
        scraper.close_driver()


if __name__ == "__main__":
    main()
