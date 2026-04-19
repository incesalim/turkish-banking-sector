"""
BDDK Metrics Calculation Engine
===============================
This module calculates metrics from raw BDDK data based on the metrics catalog.
It provides time series data for each metric with support for bank_type and currency filters.
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Union
from datetime import datetime

from .metrics_catalog import (
    METRICS_CATALOG,
    CALCULATED_RATIOS,
    GROWTH_METRICS,
    BANK_TYPES,
    CURRENCY_TYPES,
    PRIMARY_BANK_TYPES,
)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "bddk_data.db"


class MetricsEngine:
    """Engine for calculating banking metrics from BDDK raw data"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._cache = {}  # Cache for computed metrics

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def _execute_query(self, query: str, params: tuple = None) -> pd.DataFrame:
        """Execute SQL query and return DataFrame"""
        conn = self._get_connection()
        try:
            if params:
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            return df
        finally:
            conn.close()

    def get_available_periods(self) -> pd.DataFrame:
        """Get all available year-month combinations in the data"""
        query = """
        SELECT DISTINCT year, month
        FROM balance_sheet
        ORDER BY year, month
        """
        df = self._execute_query(query)
        df['period'] = pd.to_datetime(
            df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
        )
        return df

    def get_latest_period(self) -> tuple:
        """Get the latest available period"""
        query = """
        SELECT year, month FROM balance_sheet
        ORDER BY year DESC, month DESC
        LIMIT 1
        """
        df = self._execute_query(query)
        if not df.empty:
            return int(df.iloc[0]['year']), int(df.iloc[0]['month'])
        return None, None

    # =========================================================================
    # BASE METRIC CALCULATIONS
    # =========================================================================

    def calculate_base_metric(
        self,
        metric_id: str,
        bank_types: List[str] = None,
        currency: str = "TOTAL"
    ) -> pd.DataFrame:
        """
        Calculate a base metric from raw data.

        Args:
            metric_id: The metric identifier from METRICS_CATALOG
            bank_types: List of bank type codes to include (default: PRIMARY_BANK_TYPES)
            currency: Currency type - 'TL', 'FX', or 'TOTAL'

        Returns:
            DataFrame with columns: year, month, period, bank_type_code, bank_type, value
        """
        if metric_id not in METRICS_CATALOG:
            raise ValueError(f"Unknown metric: {metric_id}")

        metric = METRICS_CATALOG[metric_id]
        source = metric["source"]
        table = source["table"]
        filter_clause = source["filter"]
        aggregation = source.get("aggregation", "SUM")

        # Determine value column based on currency
        value_columns = source["value_columns"]
        if currency in value_columns:
            if isinstance(value_columns[currency], list):
                # Sum multiple columns
                value_col = " + ".join(value_columns[currency])
            else:
                value_col = value_columns[currency]
        elif "TOTAL" in value_columns:
            value_col = value_columns["TOTAL"]
        else:
            raise ValueError(f"Currency {currency} not available for metric {metric_id}")

        # Default bank types
        if bank_types is None:
            bank_types = PRIMARY_BANK_TYPES

        bank_types_str = ",".join([f"'{bt}'" for bt in bank_types])

        # Build query
        query = f"""
        SELECT
            year,
            month,
            bank_type_code,
            {aggregation}({value_col}) as value
        FROM {table}
        WHERE {filter_clause}
        AND bank_type_code IN ({bank_types_str})
        GROUP BY year, month, bank_type_code
        ORDER BY year, month, bank_type_code
        """

        df = self._execute_query(query)

        if df.empty:
            return df

        # Add period column
        df['period'] = pd.to_datetime(
            df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
        )

        # Add bank type name
        df['bank_type'] = df['bank_type_code'].map(
            lambda x: BANK_TYPES.get(x, {}).get('name', x)
        )

        # Add metadata
        df['metric_id'] = metric_id
        df['metric_name'] = metric['name']
        df['currency'] = currency
        df['unit'] = metric.get('unit', 'value')

        return df

    def calculate_balance_sheet_metric(
        self,
        item_filter: str,
        bank_types: List[str] = None,
        currency: str = "TOTAL"
    ) -> pd.DataFrame:
        """Calculate a metric from balance sheet with custom filter"""
        if bank_types is None:
            bank_types = PRIMARY_BANK_TYPES

        bank_types_str = ",".join([f"'{bt}'" for bt in bank_types])

        # Map currency to column
        col_map = {"TL": "amount_tl", "FX": "amount_fx", "TOTAL": "amount_total"}
        value_col = col_map.get(currency, "amount_total")

        query = f"""
        SELECT
            year,
            month,
            bank_type_code,
            SUM({value_col}) as value
        FROM balance_sheet
        WHERE {item_filter}
        AND bank_type_code IN ({bank_types_str})
        GROUP BY year, month, bank_type_code
        ORDER BY year, month, bank_type_code
        """

        df = self._execute_query(query)

        if not df.empty:
            df['period'] = pd.to_datetime(
                df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
            )
            df['bank_type'] = df['bank_type_code'].map(
                lambda x: BANK_TYPES.get(x, {}).get('name', x)
            )
            df['currency'] = currency

        return df

    def calculate_loans_metric(
        self,
        value_column: str = "total_amount",
        item_filter: str = "item_name LIKE '%TOPLAM%'",
        bank_types: List[str] = None,
        table_number: int = 3
    ) -> pd.DataFrame:
        """Calculate a metric from loans table"""
        if bank_types is None:
            bank_types = PRIMARY_BANK_TYPES

        bank_types_str = ",".join([f"'{bt}'" for bt in bank_types])

        query = f"""
        SELECT
            year,
            month,
            bank_type_code,
            SUM({value_column}) as value
        FROM loans
        WHERE {item_filter}
        AND table_number = {table_number}
        AND bank_type_code IN ({bank_types_str})
        GROUP BY year, month, bank_type_code
        ORDER BY year, month, bank_type_code
        """

        df = self._execute_query(query)

        if not df.empty:
            df['period'] = pd.to_datetime(
                df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
            )
            df['bank_type'] = df['bank_type_code'].map(
                lambda x: BANK_TYPES.get(x, {}).get('name', x)
            )

        return df

    # =========================================================================
    # SPECIFIC METRIC IMPLEMENTATIONS
    # =========================================================================

    def get_total_assets(
        self,
        bank_types: List[str] = None,
        currency: str = "TOTAL"
    ) -> pd.DataFrame:
        """Get total assets time series"""
        return self.calculate_balance_sheet_metric(
            item_filter="item_name LIKE '%TOPLAM AKT%'",
            bank_types=bank_types,
            currency=currency
        )

    def get_total_loans(
        self,
        bank_types: List[str] = None,
        currency: str = "TOTAL"
    ) -> pd.DataFrame:
        """Get total loans time series from balance sheet (Krediler*)"""
        # Use balance sheet for consistent units (millions)
        return self.calculate_balance_sheet_metric(
            item_filter="item_name LIKE 'Krediler%'",
            bank_types=bank_types,
            currency=currency
        )

    def get_npl_amount(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get NPL amount time series from balance sheet (Takipteki Alacaklar)"""
        # Use balance sheet for consistent units (millions)
        return self.calculate_balance_sheet_metric(
            item_filter="item_name LIKE '%Takipteki Alacak%'",
            bank_types=bank_types,
            currency="TOTAL"
        )

    def get_total_deposits(
        self,
        bank_types: List[str] = None,
        currency: str = "TOTAL"
    ) -> pd.DataFrame:
        """Get total deposits from balance sheet"""
        # Use balance sheet Mevduat line
        return self.calculate_balance_sheet_metric(
            item_filter="item_name LIKE '%Mevduat%Fon%' AND item_name NOT LIKE '%Faiz%' AND item_name NOT LIKE '%a)%' AND item_name NOT LIKE '%b)%'",
            bank_types=bank_types,
            currency=currency
        )

    def get_total_equity(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get total equity time series"""
        return self.calculate_balance_sheet_metric(
            item_filter="item_name LIKE '%TOPLAM ÖZKAYN%'",
            bank_types=bank_types,
            currency="TOTAL"
        )

    def get_total_liabilities(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get total liabilities time series"""
        return self.calculate_balance_sheet_metric(
            item_filter="item_name LIKE '%TOPLAM YABANCI KAYN%'",
            bank_types=bank_types,
            currency="TOTAL"
        )

    # =========================================================================
    # CONSUMER LOAN BREAKDOWN (from loans table 4)
    # =========================================================================

    def _get_loans_table4_metric(
        self,
        item_filter: str,
        bank_types: List[str] = None
    ) -> pd.DataFrame:
        """Get metric from loans table 4 (consumer/commercial breakdown)"""
        if bank_types is None:
            bank_types = PRIMARY_BANK_TYPES

        bank_types_str = ",".join([f"'{bt}'" for bt in bank_types])

        query = f"""
        SELECT
            year,
            month,
            bank_type_code,
            SUM(total_amount) as value
        FROM loans
        WHERE {item_filter}
        AND table_number = 4
        AND bank_type_code IN ({bank_types_str})
        GROUP BY year, month, bank_type_code
        ORDER BY year, month, bank_type_code
        """

        df = self._execute_query(query)

        if not df.empty:
            df['period'] = pd.to_datetime(
                df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
            )
            df['bank_type'] = df['bank_type_code'].map(
                lambda x: BANK_TYPES.get(x, {}).get('name', x)
            )

        return df

    def get_consumer_loans(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get total consumer loans (Tüketici Kredileri)"""
        return self._get_loans_table4_metric(
            "item_name LIKE 'Tüketici Kredileri (2+3+4)%'",
            bank_types
        )

    def get_consumer_housing_loans(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get housing loans (Konut Kredileri)"""
        return self._get_loans_table4_metric(
            "item_name LIKE 'Tüketici Kredileri - Konut' AND item_name NOT LIKE '%Döviz%'",
            bank_types
        )

    def get_consumer_auto_loans(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get auto loans (Taşıt Kredileri)"""
        return self._get_loans_table4_metric(
            "item_name LIKE 'Tüketici Kredileri - Taşıt' AND item_name NOT LIKE '%Döviz%'",
            bank_types
        )

    def get_consumer_gpl_loans(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get general purpose loans (İhtiyaç Kredileri)"""
        return self._get_loans_table4_metric(
            "item_name LIKE 'Tüketici Kredileri - İhtiyaç' AND item_name NOT LIKE '%Döviz%'",
            bank_types
        )

    def get_retail_credit_cards(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get retail/individual credit cards (Bireysel Kredi Kartları)"""
        return self._get_loans_table4_metric(
            "item_name LIKE 'Bireysel Kredi Kartları (10+11)%'",
            bank_types
        )

    def get_corporate_credit_cards(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get corporate credit cards (Kurumsal Kredi Kartları)"""
        return self._get_loans_table4_metric(
            "item_name LIKE 'Kurumsal Kredi Kartları (28+29)%'",
            bank_types
        )

    def get_commercial_installment_loans(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get commercial installment loans (Taksitli Ticari Krediler)"""
        return self._get_loans_table4_metric(
            "item_name LIKE 'Taksitli Ticari Krediler (20+21+22)%'",
            bank_types
        )

    # =========================================================================
    # RATIO CALCULATIONS
    # =========================================================================

    def calculate_ratio(
        self,
        ratio_id: str,
        bank_types: List[str] = None
    ) -> pd.DataFrame:
        """
        Calculate a ratio metric.

        Args:
            ratio_id: The ratio identifier from CALCULATED_RATIOS
            bank_types: List of bank type codes

        Returns:
            DataFrame with ratio values
        """
        if ratio_id not in CALCULATED_RATIOS:
            raise ValueError(f"Unknown ratio: {ratio_id}")

        ratio_def = CALCULATED_RATIOS[ratio_id]
        formula = ratio_def["formula"]

        # Get numerator and denominator metrics
        numerator_id = formula["numerator"]
        denominator_id = formula["denominator"]
        multiplier = formula.get("multiply_by", 1)

        # Handle currency-specific metrics (e.g., "total_loans[FX]")
        num_currency = "TOTAL"
        den_currency = "TOTAL"

        if "[" in numerator_id:
            numerator_id, num_currency = numerator_id.replace("]", "").split("[")
        if "[" in denominator_id:
            denominator_id, den_currency = denominator_id.replace("]", "").split("[")

        # Get the data
        numerator_df = self._get_metric_data(numerator_id, bank_types, num_currency)
        denominator_df = self._get_metric_data(denominator_id, bank_types, den_currency)

        if numerator_df.empty or denominator_df.empty:
            return pd.DataFrame()

        # Merge on period and bank_type_code
        merged = pd.merge(
            numerator_df[['period', 'bank_type_code', 'bank_type', 'value']],
            denominator_df[['period', 'bank_type_code', 'value']],
            on=['period', 'bank_type_code'],
            suffixes=('_num', '_den')
        )

        # Calculate ratio
        merged['value'] = (merged['value_num'] / merged['value_den']) * multiplier
        merged['value'] = merged['value'].replace([np.inf, -np.inf], np.nan)

        # Add metadata
        merged['metric_id'] = ratio_id
        merged['metric_name'] = ratio_def['name']
        merged['unit'] = ratio_def.get('unit', 'percentage')
        merged['year'] = merged['period'].dt.year
        merged['month'] = merged['period'].dt.month

        return merged[['year', 'month', 'period', 'bank_type_code', 'bank_type', 'value', 'metric_id', 'metric_name', 'unit']]

    def _get_metric_data(
        self,
        metric_id: str,
        bank_types: List[str] = None,
        currency: str = "TOTAL"
    ) -> pd.DataFrame:
        """Helper to get metric data by ID"""
        # Map metric IDs to getter functions
        metric_getters = {
            "total_assets": lambda: self.get_total_assets(bank_types, currency),
            "total_loans": lambda: self.get_total_loans(bank_types, currency),
            "npl_amount": lambda: self.get_npl_amount(bank_types),
            "total_deposits": lambda: self.get_total_deposits(bank_types, currency),
            "total_equity": lambda: self.get_total_equity(bank_types),
            "total_liabilities": lambda: self.get_total_liabilities(bank_types),
            "loans_short_term": lambda: self.calculate_loans_metric(
                "short_term_total" if currency == "TOTAL" else f"short_term_{currency.lower()}",
                bank_types=bank_types
            ),
            "demand_deposits": lambda: self._get_demand_deposits(bank_types),
        }

        if metric_id in metric_getters:
            return metric_getters[metric_id]()
        elif metric_id in METRICS_CATALOG:
            return self.calculate_base_metric(metric_id, bank_types, currency)
        else:
            return pd.DataFrame()

    def _get_demand_deposits(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get demand deposits from deposits table"""
        if bank_types is None:
            bank_types = PRIMARY_BANK_TYPES

        bank_types_str = ",".join([f"'{bt}'" for bt in bank_types])

        query = f"""
        SELECT
            year,
            month,
            bank_type_code,
            SUM(demand) as value
        FROM deposits
        WHERE item_name LIKE '%TOPLAM%'
        AND bank_type_code IN ({bank_types_str})
        GROUP BY year, month, bank_type_code
        ORDER BY year, month, bank_type_code
        """

        df = self._execute_query(query)

        if not df.empty:
            df['period'] = pd.to_datetime(
                df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
            )
            df['bank_type'] = df['bank_type_code'].map(
                lambda x: BANK_TYPES.get(x, {}).get('name', x)
            )

        return df

    # =========================================================================
    # GROWTH CALCULATIONS
    # =========================================================================

    def calculate_growth(
        self,
        growth_id: str,
        bank_types: List[str] = None
    ) -> pd.DataFrame:
        """
        Calculate a growth metric (YoY or MoM).

        Args:
            growth_id: The growth metric identifier
            bank_types: List of bank type codes

        Returns:
            DataFrame with growth rate values
        """
        if growth_id not in GROWTH_METRICS:
            raise ValueError(f"Unknown growth metric: {growth_id}")

        growth_def = GROWTH_METRICS[growth_id]
        base_metric = growth_def["base_metric"]
        calc_type = growth_def["calculation"]  # 'yoy' or 'mom'

        # Get currency from dimensions if available
        currency = "TOTAL"
        if "currency" in growth_def.get("dimensions", []):
            currency = "TOTAL"  # Default, can be parameterized

        # Get base metric data
        base_df = self._get_metric_data(base_metric, bank_types, currency)

        if base_df.empty:
            return pd.DataFrame()

        # Calculate growth for each bank type
        results = []
        for bank_type_code in base_df['bank_type_code'].unique():
            bank_df = base_df[base_df['bank_type_code'] == bank_type_code].copy()
            bank_df = bank_df.sort_values('period')

            if calc_type == 'yoy':
                # Year-over-year: compare to same month previous year
                bank_df['prev_value'] = bank_df['value'].shift(12)
            elif calc_type == 'mom':
                # Month-over-month: compare to previous month
                bank_df['prev_value'] = bank_df['value'].shift(1)

            bank_df['growth'] = ((bank_df['value'] - bank_df['prev_value']) / bank_df['prev_value']) * 100
            results.append(bank_df)

        if not results:
            return pd.DataFrame()

        df = pd.concat(results, ignore_index=True)
        df['value'] = df['growth']
        df['metric_id'] = growth_id
        df['metric_name'] = growth_def['name']
        df['unit'] = 'percentage'

        return df[['year', 'month', 'period', 'bank_type_code', 'bank_type', 'value', 'metric_id', 'metric_name', 'unit']].dropna()

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_npl_ratio(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get NPL ratio time series"""
        return self.calculate_ratio("npl_ratio", bank_types)

    def get_ldr(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get Loan-to-Deposit ratio time series"""
        return self.calculate_ratio("loan_to_deposit_ratio", bank_types)

    def get_equity_ratio(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get Equity ratio time series"""
        return self.calculate_ratio("equity_ratio", bank_types)

    def get_loan_growth_yoy(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get YoY loan growth"""
        return self.calculate_growth("loan_growth_yoy", bank_types)

    def get_asset_growth_yoy(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get YoY asset growth"""
        return self.calculate_growth("asset_growth_yoy", bank_types)

    def get_deposit_growth_yoy(self, bank_types: List[str] = None) -> pd.DataFrame:
        """Get YoY deposit growth"""
        return self.calculate_growth("deposit_growth_yoy", bank_types)

    # =========================================================================
    # BULK DATA GENERATION
    # =========================================================================

    def generate_all_metrics(self, bank_types: List[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Generate all metrics and return as dictionary of DataFrames.

        Args:
            bank_types: List of bank type codes

        Returns:
            Dictionary with metric_id as key and DataFrame as value
        """
        all_metrics = {}

        # Base metrics
        print("Calculating base metrics...")
        for metric_id in METRICS_CATALOG:
            try:
                df = self.calculate_base_metric(metric_id, bank_types)
                if not df.empty:
                    all_metrics[metric_id] = df
                    print(f"  - {metric_id}: {len(df)} rows")
            except Exception as e:
                print(f"  - {metric_id}: ERROR - {e}")

        # Ratios
        print("\nCalculating ratios...")
        for ratio_id in CALCULATED_RATIOS:
            try:
                df = self.calculate_ratio(ratio_id, bank_types)
                if not df.empty:
                    all_metrics[ratio_id] = df
                    print(f"  - {ratio_id}: {len(df)} rows")
            except Exception as e:
                print(f"  - {ratio_id}: ERROR - {e}")

        # Growth metrics
        print("\nCalculating growth metrics...")
        for growth_id in GROWTH_METRICS:
            try:
                df = self.calculate_growth(growth_id, bank_types)
                if not df.empty:
                    all_metrics[growth_id] = df
                    print(f"  - {growth_id}: {len(df)} rows")
            except Exception as e:
                print(f"  - {growth_id}: ERROR - {e}")

        return all_metrics

    def get_metric_summary(self, metric_id: str, bank_types: List[str] = None) -> dict:
        """
        Get summary statistics for a metric.

        Returns:
            Dictionary with latest value, change, min, max, etc.
        """
        # Determine metric type and get data
        if metric_id in METRICS_CATALOG:
            df = self.calculate_base_metric(metric_id, bank_types)
        elif metric_id in CALCULATED_RATIOS:
            df = self.calculate_ratio(metric_id, bank_types)
        elif metric_id in GROWTH_METRICS:
            df = self.calculate_growth(metric_id, bank_types)
        else:
            return {}

        if df.empty:
            return {}

        # Get latest period for sector (10001)
        sector_df = df[df['bank_type_code'] == '10001'] if '10001' in df['bank_type_code'].values else df

        if sector_df.empty:
            return {}

        latest = sector_df.loc[sector_df['period'].idxmax()]
        previous = sector_df[sector_df['period'] < latest['period']]

        summary = {
            'metric_id': metric_id,
            'latest_period': latest['period'].strftime('%Y-%m'),
            'latest_value': float(latest['value']),
            'min_value': float(sector_df['value'].min()),
            'max_value': float(sector_df['value'].max()),
            'avg_value': float(sector_df['value'].mean()),
        }

        if not previous.empty:
            prev_latest = previous.loc[previous['period'].idxmax()]
            summary['previous_value'] = float(prev_latest['value'])
            summary['change'] = float(latest['value'] - prev_latest['value'])
            summary['change_pct'] = float((latest['value'] - prev_latest['value']) / prev_latest['value'] * 100) if prev_latest['value'] != 0 else 0

        return summary

    # =========================================================================
    # FX-ADJUSTED GROWTH CALCULATIONS
    # =========================================================================

    _usd_try_cache = None  # Class-level cache for exchange rates

    @classmethod
    def _fetch_usd_try_rates(cls) -> dict:
        """Fetch USD/TRY rates from EVDS (TCMB) API"""
        import os
        import requests
        from dotenv import load_dotenv

        if cls._usd_try_cache is not None:
            return cls._usd_try_cache

        load_dotenv()
        evds_key = os.getenv('EVDS_API_KEY')

        if not evds_key:
            print("Warning: EVDS_API_KEY not found in environment")
            return {}

        try:
            # EVDS API - TP.DK.USD.A is USD buying rate from TCMB
            # Note: EVDS uses path-based params, not query params
            url = 'https://evds2.tcmb.gov.tr/service/evds/series=TP.DK.USD.A&startDate=01-01-2023&endDate=31-12-2026&type=json'
            headers = {'key': evds_key}

            resp = requests.get(url, headers=headers, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])

                # Convert to (year, month) -> rate format (use month-end rates)
                monthly_rates = {}
                for item in items:
                    rate_str = item.get('TP_DK_USD_A')
                    if rate_str and rate_str != 'null':
                        date_str = item.get('Tarih')  # Format: "02-01-2024"
                        day, month, year = map(int, date_str.split('-'))
                        key = (year, month)
                        # Keep updating - last date of month will be final value
                        monthly_rates[key] = float(rate_str)

                cls._usd_try_cache = monthly_rates
                return monthly_rates
            else:
                print(f"Warning: EVDS API returned status {resp.status_code}")
        except Exception as e:
            print(f"Warning: Could not fetch exchange rates from EVDS: {e}")

        return {}

    def get_usd_try_rate(self, year: int, month: int) -> Optional[float]:
        """Get USD/TRY rate for a specific month"""
        rates = self._fetch_usd_try_rates()
        return rates.get((year, month))

    def get_loans_with_fx_breakdown(self, bank_types: List[str] = None) -> pd.DataFrame:
        """
        Get loans time series with TL/FX breakdown from balance_sheet.

        Returns:
            DataFrame with loans_tl, loans_fx, loans_total columns
        """
        if bank_types is None:
            bank_types = PRIMARY_BANK_TYPES

        bank_types_str = ",".join([f"'{bt}'" for bt in bank_types])

        query = f"""
        SELECT
            year, month, bank_type_code,
            SUM(amount_tl) as loans_tl,
            SUM(amount_fx) as loans_fx,
            SUM(amount_total) as loans_total
        FROM balance_sheet
        WHERE item_name LIKE '%Krediler%'
        AND bank_type_code IN ({bank_types_str})
        GROUP BY year, month, bank_type_code
        ORDER BY year, month, bank_type_code
        """

        df = self._execute_query(query)

        if not df.empty:
            df['period'] = pd.to_datetime(
                df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
            )
            df['bank_type'] = df['bank_type_code'].map(
                lambda x: BANK_TYPES.get(x, {}).get('name', x)
            )
            # Add USD/TRY rate from API
            df['usd_try'] = df.apply(
                lambda r: self.get_usd_try_rate(int(r['year']), int(r['month'])), axis=1
            )
            # Calculate FX loans in USD
            df['loans_fx_usd'] = df['loans_fx'] / df['usd_try']

        return df

    def calculate_fx_adjusted_growth(
        self,
        bank_types: List[str] = None,
        periods: int = 12,
        annualize: bool = True
    ) -> pd.DataFrame:
        """
        Calculate FX-adjusted credit growth (like BBVA methodology).

        FX-adjusted growth removes exchange rate effects by:
        1. Calculating TL loan growth in TL
        2. Calculating FX loan growth in USD (original currency)
        3. Combining with constant exchange rate

        Args:
            bank_types: Bank types to include
            periods: Number of periods for growth calculation (12 = YoY)
            annualize: Whether to annualize growth for non-12 period calculations

        Returns:
            DataFrame with growth metrics
        """
        df = self.get_loans_with_fx_breakdown(bank_types)

        if df.empty or len(df) < periods + 1:
            return pd.DataFrame()

        results = []
        for bank_type_code in df['bank_type_code'].unique():
            bank_df = df[df['bank_type_code'] == bank_type_code].copy()
            bank_df = bank_df.sort_values('period').reset_index(drop=True)

            # Calculate growth metrics
            bank_df['loans_tl_prev'] = bank_df['loans_tl'].shift(periods)
            bank_df['loans_fx_usd_prev'] = bank_df['loans_fx_usd'].shift(periods)
            bank_df['loans_total_prev'] = bank_df['loans_total'].shift(periods)

            # TL loan growth (in TL)
            bank_df['tl_growth'] = (bank_df['loans_tl'] - bank_df['loans_tl_prev']) / bank_df['loans_tl_prev'] * 100

            # FX loan growth (in USD - removes FX effect)
            bank_df['fx_growth_usd'] = (bank_df['loans_fx_usd'] - bank_df['loans_fx_usd_prev']) / bank_df['loans_fx_usd_prev'] * 100

            # Total nominal growth (includes FX effect)
            bank_df['total_growth_nominal'] = (bank_df['loans_total'] - bank_df['loans_total_prev']) / bank_df['loans_total_prev'] * 100

            # FX-adjusted growth: TL growth + FX growth in USD, weighted
            # Use base period FX rate for conversion to get constant-FX growth
            bank_df['fx_base_rate'] = bank_df['usd_try'].shift(periods)
            bank_df['fx_contribution_adj'] = (bank_df['loans_fx_usd'] - bank_df['loans_fx_usd_prev']) * bank_df['fx_base_rate']
            bank_df['tl_contribution'] = bank_df['loans_tl'] - bank_df['loans_tl_prev']

            # FX-adjusted total growth
            bank_df['total_growth_fx_adj'] = (
                (bank_df['tl_contribution'] + bank_df['fx_contribution_adj']) /
                bank_df['loans_total_prev'] * 100
            )

            # Annualize if needed
            if annualize and periods != 12:
                factor = 12 / periods
                for col in ['tl_growth', 'fx_growth_usd', 'total_growth_nominal', 'total_growth_fx_adj']:
                    bank_df[col] = ((1 + bank_df[col]/100) ** factor - 1) * 100

            results.append(bank_df)

        if not results:
            return pd.DataFrame()

        result_df = pd.concat(results, ignore_index=True)

        # Select relevant columns
        cols = [
            'year', 'month', 'period', 'bank_type_code', 'bank_type',
            'loans_tl', 'loans_fx', 'loans_total', 'loans_fx_usd',
            'tl_growth', 'fx_growth_usd', 'total_growth_nominal', 'total_growth_fx_adj'
        ]

        return result_df[[c for c in cols if c in result_df.columns]].dropna()

    def get_credit_growth_summary(self, bank_type_code: str = '10001') -> dict:
        """
        Get summary of credit growth metrics for dashboard.

        Returns:
            Dictionary with YoY and 3M annualized growth metrics
        """
        df = self.calculate_fx_adjusted_growth([bank_type_code], periods=12)

        if df.empty:
            return {}

        latest = df.iloc[-1]

        # Also calculate 3-month growth
        df_3m = self.calculate_fx_adjusted_growth([bank_type_code], periods=3, annualize=True)
        latest_3m = df_3m.iloc[-1] if not df_3m.empty else None

        return {
            'period': latest['period'].strftime('%Y-%m'),
            'yoy': {
                'total_nominal': round(latest['total_growth_nominal'], 1),
                'total_fx_adj': round(latest['total_growth_fx_adj'], 1),
                'tl_loans': round(latest['tl_growth'], 1),
                'fx_loans_usd': round(latest['fx_growth_usd'], 1),
            },
            '3m_annualized': {
                'total_nominal': round(latest_3m['total_growth_nominal'], 1) if latest_3m is not None else None,
                'total_fx_adj': round(latest_3m['total_growth_fx_adj'], 1) if latest_3m is not None else None,
                'tl_loans': round(latest_3m['tl_growth'], 1) if latest_3m is not None else None,
                'fx_loans_usd': round(latest_3m['fx_growth_usd'], 1) if latest_3m is not None else None,
            } if latest_3m is not None else None
        }

    # =========================================================================
    # WEEKLY DATA METHODS (for 13-week growth)
    # =========================================================================

    def get_weekly_loans(self, weeks: int = 14) -> pd.DataFrame:
        """
        Get weekly loans data from weekly_bulletin table.

        Args:
            weeks: Number of weeks to retrieve

        Returns:
            DataFrame with weekly loan data
        """
        query = """
        SELECT
            period_id,
            period_date,
            item_name,
            tp_value,
            yp_value,
            total_value
        FROM weekly_bulletin
        WHERE category = 'krediler'
        ORDER BY period_date DESC
        LIMIT ?
        """

        df = self._execute_query(query, (weeks * 22,))  # ~22 items per week

        if not df.empty:
            df['period_date'] = pd.to_datetime(df['period_date'])

        return df

    def calculate_13w_annualized_growth(
        self,
        metric_name: str = "Toplam Krediler"
    ) -> dict:
        """
        Calculate 13-week annualized growth for a weekly metric.

        Formula: ((End Value / Start Value) ^ (52/13) - 1) * 100

        Args:
            metric_name: Name pattern to match in item_name

        Returns:
            Dictionary with growth metrics
        """
        df = self.get_weekly_loans(weeks=14)

        if df.empty:
            return {}

        # Filter for the specific metric
        metric_df = df[df['item_name'].str.contains(metric_name, na=False, regex=False)]

        if len(metric_df) < 14:
            return {
                'error': f'Not enough data: {len(metric_df)} weeks (need 14)',
                'available_weeks': len(metric_df)
            }

        # Sort by date
        metric_df = metric_df.sort_values('period_date')

        # Get start and end values
        start_row = metric_df.iloc[0]
        end_row = metric_df.iloc[-1]

        start_value = start_row['total_value']
        end_value = end_row['total_value']
        start_date = start_row['period_date']
        end_date = end_row['period_date']

        # Calculate growth metrics
        simple_13w = (end_value - start_value) / start_value * 100
        annualized_13w = ((end_value / start_value) ** (52/13) - 1) * 100

        return {
            'metric': metric_name,
            'start_date': start_date.strftime('%Y-%m-%d') if pd.notna(start_date) else None,
            'end_date': end_date.strftime('%Y-%m-%d') if pd.notna(end_date) else None,
            'start_value': float(start_value),
            'end_value': float(end_value),
            'growth_13w_simple': round(simple_13w, 2),
            'growth_13w_annualized': round(annualized_13w, 2),
            'weeks': len(metric_df)
        }

    def get_all_13w_growth_metrics(self) -> pd.DataFrame:
        """
        Calculate 13-week annualized growth for all key weekly metrics.

        Returns:
            DataFrame with growth metrics for each loan category
        """
        # Use exact item names from weekly_bulletin table
        metrics = [
            ('total_loans', 'Toplam Krediler (2+10)'),
            ('consumer_total', 'Tüketici Kredileri ve Bireysel Kredi Kartları (3+7)'),
            ('consumer_loans', 'Tüketici Kredileri (4+5+6)'),
            ('retail_credit_cards', 'Bireysel Kredi Kartları (8+9)'),
            ('corporate_loans', 'Ticari ve Diğer Krediler'),
            ('sme_loans', 'KOBİ Kredileri (Bilgi)'),
        ]

        results = []
        for metric_id, metric_name in metrics:
            growth = self.calculate_13w_annualized_growth(metric_name)
            if growth and 'error' not in growth:
                growth['metric_id'] = metric_id
                results.append(growth)

        if results:
            return pd.DataFrame(results)
        return pd.DataFrame()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
engine = MetricsEngine()


# =============================================================================
# TEST / DEMO
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BDDK METRICS ENGINE TEST")
    print("=" * 60)

    # Initialize engine
    engine = MetricsEngine()

    # Get available periods
    periods = engine.get_available_periods()
    print(f"\nData available from {periods['period'].min()} to {periods['period'].max()}")
    print(f"Total periods: {len(periods)}")

    # Test base metrics
    print("\n" + "-" * 40)
    print("TOTAL ASSETS (Sector, Public, Private)")
    print("-" * 40)
    assets = engine.get_total_assets()
    if not assets.empty:
        latest = assets[assets['period'] == assets['period'].max()]
        for _, row in latest.iterrows():
            print(f"  {row['bank_type']}: {row['value']:,.0f} million TL")

    # Test NPL Ratio
    print("\n" + "-" * 40)
    print("NPL RATIO")
    print("-" * 40)
    npl_ratio = engine.get_npl_ratio()
    if not npl_ratio.empty:
        latest = npl_ratio[npl_ratio['period'] == npl_ratio['period'].max()]
        for _, row in latest.iterrows():
            print(f"  {row['bank_type']}: {row['value']:.2f}%")

    # Test Loan Growth YoY
    print("\n" + "-" * 40)
    print("LOAN GROWTH (YoY)")
    print("-" * 40)
    loan_growth = engine.get_loan_growth_yoy()
    if not loan_growth.empty:
        latest = loan_growth[loan_growth['period'] == loan_growth['period'].max()]
        for _, row in latest.iterrows():
            print(f"  {row['bank_type']}: {row['value']:.1f}%")

    # Test metric summary
    print("\n" + "-" * 40)
    print("METRIC SUMMARY: total_loans")
    print("-" * 40)
    summary = engine.get_metric_summary("total_loans")
    for key, value in summary.items():
        print(f"  {key}: {value}")
