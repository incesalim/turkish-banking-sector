"""
BDDK Table Parser - Extract data from BDDK HTML tables

Handles the hierarchical structure of BDDK data tables with proper
categorization and parent-child relationships.
"""

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re
from datetime import datetime
from pathlib import Path
import sys
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.config import *


class BDDKTableParser:
    """Parse BDDK bilanco tables with hierarchical structure"""

    def __init__(self):
        """Initialize parser"""
        logger.add(
            LOGS_DIR / "bddk_parser_{time}.log",
            rotation="1 day",
            level="INFO"
        )

        # Category patterns (detect parent categories)
        self.category_patterns = [
            r'^\d+\s+[A-Z]',  # Starts with number + uppercase
            r'^[IVX]+\.',     # Roman numerals
            r'TOPLAM',        # Totals
            r'^\s*[a-z]\)',   # Lowercase letter with parenthesis
        ]

    def clean_number(self, value):
        """
        Clean Turkish number format to float

        Args:
            value: String value to clean

        Returns:
            Float value or None
        """
        if pd.isna(value) or value == '' or value == '-':
            return None

        try:
            # Remove spaces and convert
            value_str = str(value).strip()

            # Remove thousand separators (.)
            value_str = value_str.replace('.', '')

            # Replace decimal comma with dot
            value_str = value_str.replace(',', '.')

            # Remove any remaining non-numeric characters except minus and dot
            value_str = re.sub(r'[^\d.-]', '', value_str)

            return float(value_str) if value_str else None

        except Exception as e:
            logger.warning(f"Could not parse number: {value} - {e}")
            return None

    def detect_category_level(self, row_text):
        """
        Detect the hierarchy level of a row

        Args:
            row_text: Text of the row

        Returns:
            int: Level (0 = main category, 1 = subcategory, etc.)
        """
        if not row_text:
            return 0

        # Check indentation or markers
        if row_text.startswith('  ') or row_text.startswith('\t'):
            return 2  # Sub-item
        elif re.match(r'^[a-z]\)', row_text):
            return 2  # Letter items (a), b), c))
        elif re.match(r'^\d+\s+', row_text):
            return 1  # Numbered items
        elif 'TOPLAM' in row_text.upper():
            return 0  # Total
        else:
            return 1  # Default

    def parse_bddk_table(self, html_content, data_type='bilanco'):
        """
        Parse BDDK HTML table

        Args:
            html_content: HTML string or BeautifulSoup object
            data_type: Type of data ('bilanco', 'gelir_gider', etc.)

        Returns:
            DataFrame with parsed data
        """
        if isinstance(html_content, str):
            soup = BeautifulSoup(html_content, 'html.parser')
        else:
            soup = html_content

        # Find the main data table
        table = soup.find('table')

        if not table:
            logger.error("No table found in HTML")
            return None

        rows = []
        headers = []

        # Extract headers
        header_row = table.find('tr')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

        # Process data rows
        for tr in table.find_all('tr')[1:]:  # Skip header
            cells = tr.find_all(['td', 'th'])

            if len(cells) < 2:
                continue

            row_data = [cell.get_text(strip=True) for cell in cells]

            # Skip empty rows
            if not any(row_data):
                continue

            rows.append(row_data)

        if not rows:
            logger.warning("No data rows found")
            return None

        # Create DataFrame
        df = pd.DataFrame(rows)

        # Set column names
        if headers and len(headers) == len(df.columns):
            df.columns = headers
        else:
            # Default columns based on BDDK structure
            if len(df.columns) >= 4:
                df.columns = ['sira', 'kalem', 'tp', 'yp'] + [f'col_{i}' for i in range(4, len(df.columns))]
            else:
                df.columns = [f'col_{i}' for i in range(len(df.columns))]

        # Standardize column names
        df.columns = [self._standardize_column_name(col) for col in df.columns]

        # Parse the structured data
        parsed_df = self._parse_hierarchical_structure(df, data_type)

        logger.info(f"Parsed {len(parsed_df)} rows from BDDK table")

        return parsed_df

    def _standardize_column_name(self, col_name):
        """Standardize column names"""
        # Turkish to English mapping
        mappings = {
            'TP': 'tp',
            'YP': 'yp',
            'Toplam': 'toplam',
            'Sıra': 'sira',
            'Kalem': 'kalem',
        }

        return mappings.get(col_name, col_name.lower().strip())

    def _parse_hierarchical_structure(self, df, data_type):
        """
        Parse hierarchical structure and create proper relationships

        Args:
            df: Raw DataFrame
            data_type: Data type

        Returns:
            Structured DataFrame with categories
        """
        result = []
        current_category = None
        current_subcategory = None

        for idx, row in df.iterrows():
            # Get the item description (usually second column)
            if 'kalem' in df.columns:
                item = row['kalem']
            else:
                item = row.iloc[1] if len(row) > 1 else ''

            # Skip empty items
            if not item or item.strip() == '':
                continue

            # Detect level
            level = self.detect_category_level(item)

            # Get numeric values
            tp_value = self.clean_number(row.get('tp', None))
            yp_value = self.clean_number(row.get('yp', None))

            # Calculate total
            if tp_value is not None and yp_value is not None:
                total_value = tp_value + yp_value
            elif tp_value is not None:
                total_value = tp_value
            elif yp_value is not None:
                total_value = yp_value
            else:
                total_value = self.clean_number(row.get('toplam', None))

            # Build structured row
            parsed_row = {
                'item_name': item.strip(),
                'level': level,
                'category': current_category,
                'subcategory': current_subcategory,
                'tp': tp_value,
                'yp': yp_value,
                'total': total_value,
                'data_type': data_type,
                'row_number': idx
            }

            # Update current category/subcategory
            if level == 0:
                current_category = item.strip()
                current_subcategory = None
            elif level == 1:
                if current_category is None:
                    current_category = item.strip()
                else:
                    current_subcategory = item.strip()

            result.append(parsed_row)

        result_df = pd.DataFrame(result)

        # Clean item names
        result_df['item_name_clean'] = result_df['item_name'].apply(self._clean_item_name)

        return result_df

    def _clean_item_name(self, item_name):
        """Clean item name by removing numbering and markers"""
        # Remove leading numbers and dots
        cleaned = re.sub(r'^\d+\.?\s*', '', item_name)

        # Remove letter markers like a), b), c)
        cleaned = re.sub(r'^[a-z]\)\s*', '', cleaned)

        # Remove (*) and other markers
        cleaned = re.sub(r'\(\*+\)', '', cleaned)

        return cleaned.strip()

    def extract_key_metrics(self, df):
        """
        Extract key banking metrics from parsed data

        Args:
            df: Parsed DataFrame

        Returns:
            Dictionary of key metrics
        """
        metrics = {}

        # Define metric patterns to search for
        metric_patterns = {
            'total_assets': [r'Toplam Aktif', r'TOPLAM AKTİF', r'AKTİFLER'],
            'total_loans': [r'Krediler', r'TOPLAM KREDİLER', r'Krediler\*'],
            'total_deposits': [r'Mevduat', r'TOPLAM MEVDUAT'],
            'equity': [r'Özkaynaklar', r'ÖZKAYNAK'],
            'npl': [r'Takipteki', r'Donuk Alacaklar'],
            'liquid_assets': [r'Nakit Değerler', r'PARA VE NAKIT'],
        }

        for metric_key, patterns in metric_patterns.items():
            for pattern in patterns:
                matches = df[df['item_name'].str.contains(pattern, case=False, na=False, regex=True)]

                if not matches.empty:
                    # Get the total value
                    value = matches.iloc[0]['total']
                    if value is not None:
                        metrics[metric_key] = value
                        break

        logger.info(f"Extracted {len(metrics)} key metrics")

        return metrics

    def parse_from_file(self, file_path, data_type='bilanco'):
        """
        Parse BDDK table from HTML file

        Args:
            file_path: Path to HTML file
            data_type: Type of data

        Returns:
            Parsed DataFrame
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            return self.parse_bddk_table(html_content, data_type)

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None

    def save_parsed_data(self, df, output_path, period_date=None):
        """
        Save parsed data with metadata

        Args:
            df: Parsed DataFrame
            output_path: Output file path
            period_date: Date of the data period
        """
        if df is None or df.empty:
            logger.warning("No data to save")
            return False

        # Add metadata
        df_to_save = df.copy()
        df_to_save['period_date'] = period_date or datetime.now().strftime('%Y-%m-%d')
        df_to_save['parsed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Save to CSV
        df_to_save.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"Saved parsed data to {output_path}")

        return True


def main():
    """Example usage"""
    parser = BDDKTableParser()

    # Example: Parse a sample HTML structure
    sample_html = """
    <table>
        <tr><th>Sıra</th><th>Kalem</th><th>TP</th><th>YP</th><th>Toplam</th></tr>
        <tr><td>1</td><td>Nakit Değerler</td><td>76.980</td><td>335.646</td><td>412.626</td></tr>
        <tr><td>2</td><td>T.C. Merkez Bankasından Alacaklar</td><td>2.006.184</td><td>1.604.220</td><td>3.610.404</td></tr>
        <tr><td>3</td><td>Para Piyasalarından Alacaklar</td><td>264.634</td><td>5.549</td><td>270.182</td></tr>
        <tr><td>4</td><td>Bankalardan Alacaklar</td><td>425.535</td><td>1.249.573</td><td>1.675.109</td></tr>
    </table>
    """

    df = parser.parse_bddk_table(sample_html, data_type='bilanco')

    if df is not None:
        print("Parsed Data:")
        print(df[['item_name_clean', 'tp', 'yp', 'total']].head(10))

        # Extract key metrics
        metrics = parser.extract_key_metrics(df)
        print("\nKey Metrics:")
        for key, value in metrics.items():
            print(f"  {key}: {value:,.0f}")


if __name__ == "__main__":
    main()
