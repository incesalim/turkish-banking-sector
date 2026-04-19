"""
Data Processing and Cleaning Module for BDDK Banking Data

Handles data cleaning, transformation, and metric calculation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
from pathlib import Path
import sys
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.config import *


class DataProcessor:
    """Process and clean BDDK banking sector data"""

    def __init__(self):
        """Initialize data processor"""
        logger.add(
            LOGS_DIR / "data_processor_{time}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO"
        )

    def clean_numeric_columns(self, df, columns=None):
        """
        Clean numeric columns by removing formatting and converting to float

        Args:
            df: DataFrame to clean
            columns: List of columns to clean (None = all numeric-looking columns)

        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()

        if columns is None:
            # Auto-detect numeric columns
            columns = df_clean.select_dtypes(include=['object']).columns

        for col in columns:
            if col in df_clean.columns:
                try:
                    # Remove thousand separators and convert decimal comma to dot
                    df_clean[col] = df_clean[col].astype(str)
                    df_clean[col] = df_clean[col].str.replace('.', '', regex=False)  # Remove thousand separator
                    df_clean[col] = df_clean[col].str.replace(',', '.', regex=False)  # Decimal separator
                    df_clean[col] = df_clean[col].str.replace('%', '', regex=False)  # Remove percentage
                    df_clean[col] = df_clean[col].str.strip()

                    # Convert to numeric
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

                except Exception as e:
                    logger.warning(f"Could not clean column {col}: {str(e)}")

        logger.info(f"Cleaned {len(columns)} numeric columns")
        return df_clean

    def standardize_column_names(self, df):
        """
        Standardize column names (lowercase, remove special chars)

        Args:
            df: DataFrame

        Returns:
            DataFrame with standardized column names
        """
        df_clean = df.copy()

        # Turkish character mapping
        tr_char_map = {
            'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
            'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S',
            'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
        }

        new_columns = []
        for col in df_clean.columns:
            # Convert to string
            col_str = str(col)

            # Replace Turkish characters
            for tr_char, en_char in tr_char_map.items():
                col_str = col_str.replace(tr_char, en_char)

            # Lowercase and replace spaces/special chars with underscore
            col_str = col_str.lower()
            col_str = re.sub(r'[^\w\s]', '_', col_str)
            col_str = re.sub(r'\s+', '_', col_str)
            col_str = re.sub(r'_+', '_', col_str)
            col_str = col_str.strip('_')

            new_columns.append(col_str)

        df_clean.columns = new_columns
        logger.info("Standardized column names")
        return df_clean

    def handle_missing_data(self, df, strategy='interpolate', columns=None):
        """
        Handle missing data in DataFrame

        Args:
            df: DataFrame
            strategy: 'interpolate', 'forward_fill', 'backward_fill', 'drop', 'zero'
            columns: Specific columns to process (None = all)

        Returns:
            DataFrame with handled missing data
        """
        df_clean = df.copy()

        if columns is None:
            columns = df_clean.columns

        for col in columns:
            if col in df_clean.columns:
                if strategy == 'interpolate':
                    df_clean[col] = df_clean[col].interpolate(method='linear')
                elif strategy == 'forward_fill':
                    df_clean[col] = df_clean[col].fillna(method='ffill')
                elif strategy == 'backward_fill':
                    df_clean[col] = df_clean[col].fillna(method='bfill')
                elif strategy == 'zero':
                    df_clean[col] = df_clean[col].fillna(0)
                elif strategy == 'drop':
                    df_clean = df_clean.dropna(subset=[col])

        logger.info(f"Handled missing data using strategy: {strategy}")
        return df_clean

    def remove_duplicates(self, df, subset=None, keep='last'):
        """
        Remove duplicate rows

        Args:
            df: DataFrame
            subset: Columns to consider for duplicates
            keep: Which duplicate to keep ('first', 'last', False)

        Returns:
            DataFrame without duplicates
        """
        df_clean = df.copy()
        initial_count = len(df_clean)
        df_clean = df_clean.drop_duplicates(subset=subset, keep=keep)
        removed_count = initial_count - len(df_clean)

        logger.info(f"Removed {removed_count} duplicate rows")
        return df_clean

    def calculate_growth_rates(self, df, value_column, date_column='date', periods=1):
        """
        Calculate period-over-period growth rates

        Args:
            df: DataFrame
            value_column: Column to calculate growth for
            date_column: Date column for sorting
            periods: Number of periods for growth calculation

        Returns:
            DataFrame with growth rate column
        """
        df_calc = df.copy()
        df_calc = df_calc.sort_values(date_column)

        growth_col = f"{value_column}_growth_{periods}p"
        df_calc[growth_col] = df_calc[value_column].pct_change(periods=periods) * 100

        logger.info(f"Calculated growth rates for {value_column}")
        return df_calc

    def calculate_moving_average(self, df, value_column, window=3):
        """
        Calculate moving average

        Args:
            df: DataFrame
            value_column: Column to calculate MA for
            window: Window size

        Returns:
            DataFrame with MA column
        """
        df_calc = df.copy()
        ma_col = f"{value_column}_ma{window}"
        df_calc[ma_col] = df_calc[value_column].rolling(window=window).mean()

        logger.info(f"Calculated {window}-period moving average for {value_column}")
        return df_calc

    def calculate_financial_ratios(self, df):
        """
        Calculate key banking financial ratios

        Args:
            df: DataFrame with raw financial data

        Returns:
            DataFrame with calculated ratios
        """
        df_ratios = df.copy()

        try:
            # Asset Quality Ratios
            if 'npl_amount' in df_ratios.columns and 'total_loans' in df_ratios.columns:
                df_ratios['npl_ratio'] = (df_ratios['npl_amount'] / df_ratios['total_loans']) * 100

            if 'provisions' in df_ratios.columns and 'npl_amount' in df_ratios.columns:
                df_ratios['provision_coverage'] = (df_ratios['provisions'] / df_ratios['npl_amount']) * 100

            # Profitability Ratios
            if 'net_profit' in df_ratios.columns and 'total_assets' in df_ratios.columns:
                df_ratios['roa'] = (df_ratios['net_profit'] / df_ratios['total_assets']) * 100

            if 'net_profit' in df_ratios.columns and 'equity' in df_ratios.columns:
                df_ratios['roe'] = (df_ratios['net_profit'] / df_ratios['equity']) * 100

            if 'net_interest_income' in df_ratios.columns and 'earning_assets' in df_ratios.columns:
                df_ratios['nim'] = (df_ratios['net_interest_income'] / df_ratios['earning_assets']) * 100

            if 'operating_expenses' in df_ratios.columns and 'operating_income' in df_ratios.columns:
                df_ratios['cost_income_ratio'] = (df_ratios['operating_expenses'] / df_ratios['operating_income']) * 100

            # Liquidity Ratios
            if 'total_loans' in df_ratios.columns and 'total_deposits' in df_ratios.columns:
                df_ratios['loan_deposit_ratio'] = (df_ratios['total_loans'] / df_ratios['total_deposits']) * 100

            if 'liquid_assets' in df_ratios.columns and 'total_assets' in df_ratios.columns:
                df_ratios['liquid_assets_ratio'] = (df_ratios['liquid_assets'] / df_ratios['total_assets']) * 100

            # Capital Ratios are typically provided directly by BDDK
            # But we can validate them if components are available

            logger.info("Calculated financial ratios")

        except Exception as e:
            logger.error(f"Error calculating ratios: {str(e)}")

        return df_ratios

    def convert_to_billions(self, df, columns, from_unit='thousands'):
        """
        Convert currency amounts to billions

        Args:
            df: DataFrame
            columns: Columns to convert
            from_unit: Original unit ('thousands', 'millions')

        Returns:
            DataFrame with converted values
        """
        df_conv = df.copy()

        conversion_factors = {
            'thousands': 1_000_000,
            'millions': 1_000
        }

        factor = conversion_factors.get(from_unit, 1)

        for col in columns:
            if col in df_conv.columns:
                df_conv[col] = df_conv[col] / factor

        logger.info(f"Converted {len(columns)} columns to billions")
        return df_conv

    def aggregate_to_monthly(self, df, date_column='date', agg_functions=None):
        """
        Aggregate weekly data to monthly

        Args:
            df: DataFrame with weekly data
            date_column: Date column
            agg_functions: Dictionary of column -> aggregation function

        Returns:
            Monthly aggregated DataFrame
        """
        df_agg = df.copy()
        df_agg[date_column] = pd.to_datetime(df_agg[date_column])
        df_agg['year_month'] = df_agg[date_column].dt.to_period('M')

        if agg_functions is None:
            # Default: use last value of month for most metrics
            agg_functions = {col: 'last' for col in df_agg.select_dtypes(include=[np.number]).columns}

        monthly_df = df_agg.groupby('year_month').agg(agg_functions).reset_index()
        monthly_df['year_month'] = monthly_df['year_month'].dt.to_timestamp()

        logger.info(f"Aggregated to monthly: {len(monthly_df)} months")
        return monthly_df

    def detect_outliers(self, df, column, method='iqr', threshold=1.5):
        """
        Detect outliers in data

        Args:
            df: DataFrame
            column: Column to check
            method: 'iqr' or 'zscore'
            threshold: Threshold for outlier detection

        Returns:
            DataFrame with outlier flag column
        """
        df_out = df.copy()

        if method == 'iqr':
            Q1 = df_out[column].quantile(0.25)
            Q3 = df_out[column].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - threshold * IQR
            upper_bound = Q3 + threshold * IQR
            df_out[f'{column}_outlier'] = ~df_out[column].between(lower_bound, upper_bound)

        elif method == 'zscore':
            z_scores = np.abs((df_out[column] - df_out[column].mean()) / df_out[column].std())
            df_out[f'{column}_outlier'] = z_scores > threshold

        outlier_count = df_out[f'{column}_outlier'].sum()
        logger.info(f"Detected {outlier_count} outliers in {column}")

        return df_out

    def merge_monthly_weekly(self, monthly_df, weekly_df):
        """
        Merge monthly and weekly datasets

        Args:
            monthly_df: Monthly data
            weekly_df: Weekly data

        Returns:
            Merged DataFrame
        """
        monthly_clean = monthly_df.copy()
        weekly_clean = weekly_df.copy()

        # Ensure date columns
        if 'year' in monthly_clean.columns and 'month' in monthly_clean.columns:
            monthly_clean['date'] = pd.to_datetime(
                monthly_clean[['year', 'month']].assign(day=1)
            )

        weekly_clean['date'] = pd.to_datetime(weekly_clean['date'])

        # Merge on nearest date
        merged = pd.merge_asof(
            weekly_clean.sort_values('date'),
            monthly_clean.sort_values('date'),
            on='date',
            direction='backward',
            suffixes=('_weekly', '_monthly')
        )

        logger.info(f"Merged datasets: {len(merged)} rows")
        return merged

    def create_feature_matrix(self, df, target_column, feature_columns=None, lag_periods=[1, 3, 6, 12]):
        """
        Create feature matrix for time series analysis/forecasting

        Args:
            df: DataFrame
            target_column: Target variable
            feature_columns: Feature columns (None = all numeric)
            lag_periods: Lag periods to create

        Returns:
            Feature matrix DataFrame
        """
        df_features = df.copy()

        if feature_columns is None:
            feature_columns = df_features.select_dtypes(include=[np.number]).columns.tolist()
            feature_columns = [col for col in feature_columns if col != target_column]

        # Create lag features
        for col in feature_columns:
            for lag in lag_periods:
                df_features[f'{col}_lag{lag}'] = df_features[col].shift(lag)

        # Create rolling features
        for col in feature_columns:
            df_features[f'{col}_roll3'] = df_features[col].rolling(3).mean()
            df_features[f'{col}_roll6'] = df_features[col].rolling(6).mean()

        # Drop rows with NaN (due to lagging)
        df_features = df_features.dropna()

        logger.info(f"Created feature matrix with {len(df_features.columns)} features")
        return df_features


def main():
    """Example usage"""
    processor = DataProcessor()

    # Example: Create sample data
    sample_data = pd.DataFrame({
        'Toplam Aktifler (Bin TL)': ['1.000.000,50', '1.050.000,75', '1.100.000,00'],
        'Toplam Krediler': ['750.000,25', '780.000,50', '800.000,00'],
        'date': ['2024-01-01', '2024-02-01', '2024-03-01']
    })

    # Clean and process
    cleaned = processor.clean_numeric_columns(sample_data)
    cleaned = processor.standardize_column_names(cleaned)
    print(cleaned)


if __name__ == "__main__":
    main()
