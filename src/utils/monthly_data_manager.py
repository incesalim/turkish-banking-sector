"""
Monthly Data Manager - Handle incremental monthly data updates

This manager ensures we can add new monthly data without duplicates
and maintain historical data integrity.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
from loguru import logger
from sqlalchemy import and_, or_

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.config import *
from src.database.db_manager import DatabaseManager


class MonthlyDataManager:
    """Manage monthly banking data with incremental updates"""

    def __init__(self):
        """Initialize manager"""
        self.db = DatabaseManager()

        logger.add(
            LOGS_DIR / "monthly_data_manager_{time}.log",
            rotation="1 day",
            level="INFO"
        )

    def add_monthly_data(self, df, year, month, currency='TL', data_type='bilanco',
                        check_duplicates=True):
        """
        Add new monthly data to database

        Args:
            df: DataFrame with new data
            year: Year (e.g., 2024)
            month: Month (1-12)
            currency: Currency code
            data_type: Type of data
            check_duplicates: Check for existing data

        Returns:
            bool: Success status
        """
        period_key = f"{year}-{month:02d}"

        logger.info(f"Adding monthly data for {period_key}, Currency: {currency}, Type: {data_type}")

        # Check if data already exists
        if check_duplicates:
            existing = self.check_existing_data(year, month, currency, data_type)

            if existing:
                logger.warning(f"Data for {period_key} already exists")

                response = input(f"Data for {period_key} exists. Overwrite? (y/n): ")

                if response.lower() != 'y':
                    logger.info("Skipping duplicate data")
                    return False
                else:
                    # Delete existing data
                    self.delete_monthly_data(year, month, currency, data_type)

        # Add metadata to DataFrame
        df_to_save = df.copy()
        df_to_save['year'] = year
        df_to_save['month'] = month
        df_to_save['currency'] = currency
        df_to_save['data_type'] = data_type
        df_to_save['period_date'] = f"{year}-{month:02d}-01"
        df_to_save['added_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Save to database
        success = self.db.save_monthly_data(df_to_save, category=data_type)

        if success:
            logger.info(f"Successfully added {len(df_to_save)} rows for {period_key}")

            # Also save to CSV backup
            self._save_csv_backup(df_to_save, year, month, currency, data_type)

        return success

    def check_existing_data(self, year, month, currency, data_type):
        """
        Check if data already exists for the period

        Args:
            year: Year
            month: Month
            currency: Currency
            data_type: Data type

        Returns:
            bool: True if exists
        """
        existing = self.db.get_monthly_data(
            year=year,
            month=month,
            currency=currency,
            category=data_type
        )

        return existing is not None and not existing.empty

    def delete_monthly_data(self, year, month, currency, data_type):
        """
        Delete existing monthly data

        Args:
            year: Year
            month: Month
            currency: Currency
            data_type: Data type

        Returns:
            bool: Success status
        """
        # Delete from database
        table_name = f"{DATABASE_CONFIG['table_prefix']}monthly_{data_type}"

        try:
            query = f"""
                DELETE FROM {table_name}
                WHERE year = {year} AND month = {month}
                AND currency = '{currency}'
            """

            with self.db.engine.connect() as conn:
                conn.execute(query)

            logger.info(f"Deleted data for {year}-{month:02d}")
            return True

        except Exception as e:
            logger.error(f"Error deleting data: {e}")
            return False

    def get_available_periods(self, currency='TL', data_type='bilanco'):
        """
        Get list of available data periods

        Args:
            currency: Currency filter
            data_type: Data type filter

        Returns:
            List of (year, month) tuples
        """
        table_name = f"{DATABASE_CONFIG['table_prefix']}monthly_{data_type}"

        try:
            query = f"""
                SELECT DISTINCT year, month
                FROM {table_name}
                WHERE currency = '{currency}'
                ORDER BY year DESC, month DESC
            """

            with self.db.engine.connect() as conn:
                result = conn.execute(query)
                periods = [(row[0], row[1]) for row in result]

            logger.info(f"Found {len(periods)} available periods")
            return periods

        except Exception as e:
            logger.error(f"Error getting periods: {e}")
            return []

    def get_latest_period(self, currency='TL', data_type='bilanco'):
        """
        Get the most recent data period

        Args:
            currency: Currency
            data_type: Data type

        Returns:
            Tuple of (year, month) or None
        """
        periods = self.get_available_periods(currency, data_type)

        if periods:
            return periods[0]  # Already sorted DESC
        return None

    def get_missing_periods(self, start_year, end_year, currency='TL', data_type='bilanco'):
        """
        Identify missing periods in the date range

        Args:
            start_year: Start year
            end_year: End year
            currency: Currency
            data_type: Data type

        Returns:
            List of missing (year, month) tuples
        """
        # Get available periods
        available = set(self.get_available_periods(currency, data_type))

        # Generate all periods in range
        all_periods = []
        for year in range(start_year, end_year + 1):
            max_month = 12 if year < datetime.now().year else datetime.now().month
            for month in range(1, max_month + 1):
                all_periods.append((year, month))

        # Find missing
        missing = [p for p in all_periods if p not in available]

        logger.info(f"Found {len(missing)} missing periods out of {len(all_periods)}")

        return sorted(missing)

    def update_incremental(self, new_df, currency='TL', data_type='bilanco'):
        """
        Add new monthly data incrementally

        Args:
            new_df: New data with 'year' and 'month' columns
            currency: Currency
            data_type: Data type

        Returns:
            Dictionary with update results
        """
        if 'year' not in new_df.columns or 'month' not in new_df.columns:
            logger.error("DataFrame must have 'year' and 'month' columns")
            return {'success': False, 'error': 'Missing required columns'}

        # Group by year/month
        grouped = new_df.groupby(['year', 'month'])

        results = {
            'total_periods': 0,
            'added': 0,
            'skipped': 0,
            'failed': 0,
            'periods_added': []
        }

        for (year, month), group_df in grouped:
            results['total_periods'] += 1

            success = self.add_monthly_data(
                group_df,
                year=int(year),
                month=int(month),
                currency=currency,
                data_type=data_type,
                check_duplicates=True
            )

            if success:
                results['added'] += 1
                results['periods_added'].append((int(year), int(month)))
            else:
                results['skipped'] += 1

        results['success'] = True

        logger.info(f"Incremental update complete: {results['added']} added, {results['skipped']} skipped")

        return results

    def get_data_summary(self, currency='TL'):
        """
        Get summary of available data

        Args:
            currency: Currency

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            'currency': currency,
            'data_types': {},
            'total_periods': 0,
            'date_range': None
        }

        # Check each data type
        for data_type in ['bilanco', 'gelir_gider', 'krediler', 'mevduat']:
            periods = self.get_available_periods(currency, data_type)

            if periods:
                summary['data_types'][data_type] = {
                    'count': len(periods),
                    'latest': periods[0],
                    'oldest': periods[-1]
                }

                # Get row count
                table_name = f"{DATABASE_CONFIG['table_prefix']}monthly_{data_type}"
                try:
                    query = f"SELECT COUNT(*) FROM {table_name} WHERE currency = '{currency}'"
                    with self.db.engine.connect() as conn:
                        result = conn.execute(query)
                        row_count = result.fetchone()[0]

                    summary['data_types'][data_type]['total_rows'] = row_count

                except:
                    pass

        # Get overall stats
        all_periods = []
        for dtype, info in summary['data_types'].items():
            all_periods.extend(self.get_available_periods(currency, dtype))

        if all_periods:
            all_periods = sorted(set(all_periods), reverse=True)
            summary['total_periods'] = len(all_periods)
            summary['date_range'] = {
                'from': f"{all_periods[-1][0]}-{all_periods[-1][1]:02d}",
                'to': f"{all_periods[0][0]}-{all_periods[0][1]:02d}"
            }

        return summary

    def export_period_data(self, year, month, currency='TL', output_dir=None):
        """
        Export all data for a specific period

        Args:
            year: Year
            month: Month
            currency: Currency
            output_dir: Output directory

        Returns:
            Dictionary of file paths
        """
        if output_dir is None:
            output_dir = PROCESSED_DATA_DIR / f"{year}_{month:02d}"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported_files = {}

        for data_type in ['bilanco', 'gelir_gider', 'krediler', 'mevduat']:
            df = self.db.get_monthly_data(year, month, data_type, currency)

            if df is not None and not df.empty:
                file_path = output_dir / f"{data_type}_{year}_{month:02d}_{currency}.csv"
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                exported_files[data_type] = str(file_path)

                logger.info(f"Exported {data_type} to {file_path}")

        return exported_files

    def _save_csv_backup(self, df, year, month, currency, data_type):
        """Save CSV backup of monthly data"""
        backup_dir = PROCESSED_DATA_DIR / 'monthly_backups' / f"{year}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{data_type}_{year}_{month:02d}_{currency}.csv"
        file_path = backup_dir / filename

        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        logger.info(f"Saved CSV backup to {file_path}")

    def consolidate_data(self, start_year, end_year, currency='TL', data_type='bilanco'):
        """
        Consolidate all monthly data into a single DataFrame

        Args:
            start_year: Start year
            end_year: End year
            currency: Currency
            data_type: Data type

        Returns:
            Consolidated DataFrame
        """
        all_data = []

        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                df = self.db.get_monthly_data(year, month, data_type, currency)

                if df is not None and not df.empty:
                    all_data.append(df)

        if all_data:
            consolidated = pd.concat(all_data, ignore_index=True)
            logger.info(f"Consolidated {len(all_data)} periods into {len(consolidated)} rows")
            return consolidated
        else:
            logger.warning("No data found for consolidation")
            return pd.DataFrame()


def main():
    """Example usage"""
    manager = MonthlyDataManager()

    # Get data summary
    print("Data Summary:")
    summary = manager.get_data_summary(currency='TL')
    print(f"  Total periods: {summary['total_periods']}")
    print(f"  Date range: {summary.get('date_range')}")

    # Get available periods
    periods = manager.get_available_periods(currency='TL', data_type='demo_data')
    print(f"\nAvailable periods: {len(periods)}")

    # Get missing periods
    missing = manager.get_missing_periods(2020, 2024, currency='TL')
    print(f"\nMissing periods: {len(missing)}")
    if missing[:5]:
        print(f"  First 5: {missing[:5]}")


if __name__ == "__main__":
    main()
