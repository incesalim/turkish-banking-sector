"""
BDDK Metrics Data Store
=======================
Pre-computed metrics storage for fast dashboard access.
Generates all metrics on initialization and provides simple getters.
"""

import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path

from .metrics_engine import MetricsEngine
from .metrics_catalog import BANK_TYPES, PRIMARY_BANK_TYPES


class MetricsDataStore:
    """
    Pre-computed metrics store for dashboard consumption.
    Generates all metrics once and provides fast access.
    """

    def __init__(self, engine: MetricsEngine = None):
        self.engine = engine or MetricsEngine()
        self._data: Dict[str, pd.DataFrame] = {}
        self._latest_period = None
        self._initialized = False

    def initialize(self, bank_types: List[str] = None):
        """
        Generate all metrics and store in memory.

        Args:
            bank_types: Bank types to include (default: PRIMARY_BANK_TYPES)
        """
        if bank_types is None:
            bank_types = PRIMARY_BANK_TYPES

        print("Initializing metrics data store...")

        # Get latest period
        year, month = self.engine.get_latest_period()
        self._latest_period = (year, month)
        print(f"  Latest period: {year}-{month:02d}")

        # Generate base metrics
        print("  Generating base metrics...")
        self._data['total_assets'] = self.engine.get_total_assets(bank_types)
        self._data['total_assets_tl'] = self.engine.get_total_assets(bank_types, 'TL')
        self._data['total_assets_fx'] = self.engine.get_total_assets(bank_types, 'FX')
        self._data['total_loans'] = self.engine.get_total_loans(bank_types)
        self._data['total_loans_tl'] = self.engine.get_total_loans(bank_types, 'TL')
        self._data['total_loans_fx'] = self.engine.get_total_loans(bank_types, 'FX')
        self._data['npl_amount'] = self.engine.get_npl_amount(bank_types)
        self._data['total_deposits'] = self.engine.get_total_deposits(bank_types)
        self._data['total_deposits_tl'] = self.engine.get_total_deposits(bank_types, 'TL')
        self._data['total_deposits_fx'] = self.engine.get_total_deposits(bank_types, 'FX')
        self._data['total_equity'] = self.engine.get_total_equity(bank_types)
        self._data['total_liabilities'] = self.engine.get_total_liabilities(bank_types)

        # Generate consumer loan breakdown
        print("  Generating consumer loan breakdown...")
        self._data['consumer_loans'] = self.engine.get_consumer_loans(bank_types)
        self._data['consumer_housing'] = self.engine.get_consumer_housing_loans(bank_types)
        self._data['consumer_auto'] = self.engine.get_consumer_auto_loans(bank_types)
        self._data['consumer_gpl'] = self.engine.get_consumer_gpl_loans(bank_types)
        self._data['retail_credit_cards'] = self.engine.get_retail_credit_cards(bank_types)
        self._data['corporate_credit_cards'] = self.engine.get_corporate_credit_cards(bank_types)
        self._data['commercial_installment'] = self.engine.get_commercial_installment_loans(bank_types)

        # Generate ratios
        print("  Generating ratios...")
        self._data['npl_ratio'] = self.engine.get_npl_ratio(bank_types)
        self._data['ldr'] = self.engine.get_ldr(bank_types)
        self._data['equity_ratio'] = self.engine.get_equity_ratio(bank_types)

        # Generate growth metrics
        print("  Generating growth metrics...")
        self._data['loan_growth_yoy'] = self.engine.get_loan_growth_yoy(bank_types)
        self._data['asset_growth_yoy'] = self.engine.get_asset_growth_yoy(bank_types)
        self._data['deposit_growth_yoy'] = self.engine.get_deposit_growth_yoy(bank_types)

        # Calculate additional derived metrics
        print("  Calculating derived metrics...")
        self._calculate_fx_shares(bank_types)
        self._calculate_market_shares(bank_types)

        self._initialized = True
        print(f"  Data store initialized with {len(self._data)} metrics")

    def _calculate_fx_shares(self, bank_types: List[str]):
        """Calculate FX share metrics"""
        # FX Loan Share
        if 'total_loans' in self._data and 'total_loans_fx' in self._data:
            total = self._data['total_loans'].copy()
            fx = self._data['total_loans_fx'].copy()
            merged = pd.merge(
                total[['period', 'bank_type_code', 'bank_type', 'value']],
                fx[['period', 'bank_type_code', 'value']],
                on=['period', 'bank_type_code'],
                suffixes=('_total', '_fx')
            )
            merged['value'] = (merged['value_fx'] / merged['value_total'] * 100).round(2)
            merged['year'] = merged['period'].dt.year
            merged['month'] = merged['period'].dt.month
            self._data['fx_loan_share'] = merged[['year', 'month', 'period', 'bank_type_code', 'bank_type', 'value']]

        # FX Deposit Share
        if 'total_deposits' in self._data and 'total_deposits_fx' in self._data:
            total = self._data['total_deposits'].copy()
            fx = self._data['total_deposits_fx'].copy()
            merged = pd.merge(
                total[['period', 'bank_type_code', 'bank_type', 'value']],
                fx[['period', 'bank_type_code', 'value']],
                on=['period', 'bank_type_code'],
                suffixes=('_total', '_fx')
            )
            merged['value'] = (merged['value_fx'] / merged['value_total'] * 100).round(2)
            merged['year'] = merged['period'].dt.year
            merged['month'] = merged['period'].dt.month
            self._data['fx_deposit_share'] = merged[['year', 'month', 'period', 'bank_type_code', 'bank_type', 'value']]

    def _calculate_market_shares(self, bank_types: List[str]):
        """Calculate market share by bank type"""
        if 'total_assets' not in self._data:
            return

        assets = self._data['total_assets'].copy()

        # Get sector total for each period
        sector = assets[assets['bank_type_code'] == '10001'][['period', 'value']].rename(columns={'value': 'sector_total'})

        merged = pd.merge(assets, sector, on='period')
        merged['market_share'] = (merged['value'] / merged['sector_total'] * 100).round(2)
        merged['year'] = merged['period'].dt.year
        merged['month'] = merged['period'].dt.month

        self._data['market_share'] = merged[['year', 'month', 'period', 'bank_type_code', 'bank_type', 'market_share']].rename(columns={'market_share': 'value'})

    # =========================================================================
    # GETTERS
    # =========================================================================

    def get(self, metric_id: str) -> pd.DataFrame:
        """Get a metric DataFrame by ID"""
        if not self._initialized:
            self.initialize()
        return self._data.get(metric_id, pd.DataFrame())

    def get_latest(self, metric_id: str, bank_type_code: str = None) -> pd.DataFrame:
        """Get latest values for a metric"""
        df = self.get(metric_id)
        if df.empty:
            return df

        latest = df[df['period'] == df['period'].max()]
        if bank_type_code:
            latest = latest[latest['bank_type_code'] == bank_type_code]
        return latest

    def get_latest_value(self, metric_id: str, bank_type_code: str = '10001') -> float:
        """Get single latest value for a metric"""
        df = self.get_latest(metric_id, bank_type_code)
        if df.empty:
            return None
        return float(df['value'].iloc[0])

    def get_time_series(self, metric_id: str, bank_type_code: str = None) -> pd.DataFrame:
        """Get time series for a metric, optionally filtered by bank type"""
        df = self.get(metric_id)
        if df.empty:
            return df
        if bank_type_code:
            df = df[df['bank_type_code'] == bank_type_code]
        return df.sort_values('period')

    def get_comparison(self, metric_id: str) -> pd.DataFrame:
        """Get latest values for all bank types (for comparison charts)"""
        return self.get_latest(metric_id)

    def get_period_range(self) -> tuple:
        """Get min and max periods in the data"""
        if 'total_assets' in self._data:
            df = self._data['total_assets']
            return df['period'].min(), df['period'].max()
        return None, None

    def get_latest_period(self) -> tuple:
        """Get latest year and month"""
        return self._latest_period

    # =========================================================================
    # SUMMARY METHODS
    # =========================================================================

    def get_kpi_summary(self, bank_type_code: str = '10001') -> dict:
        """
        Get KPI summary for dashboard cards.

        Returns dict with latest values and changes.
        """
        summary = {}

        metrics = [
            ('total_assets', 'Total Assets', 'T TL', 1e6),
            ('total_loans', 'Total Loans', 'T TL', 1e6),
            ('total_deposits', 'Total Deposits', 'T TL', 1e6),
            ('total_equity', 'Total Equity', 'T TL', 1e6),
            ('npl_ratio', 'NPL Ratio', '%', 1),
            ('ldr', 'LDR', '%', 1),
            ('equity_ratio', 'Equity Ratio', '%', 1),
            ('loan_growth_yoy', 'Loan Growth YoY', '%', 1),
        ]

        for metric_id, name, unit, divisor in metrics:
            df = self.get(metric_id)
            if df.empty:
                continue

            bank_df = df[df['bank_type_code'] == bank_type_code].sort_values('period')
            if bank_df.empty:
                continue

            latest = bank_df.iloc[-1]
            latest_value = float(latest['value']) / divisor if divisor > 1 else float(latest['value'])

            # Calculate change from previous period
            change = None
            change_pct = None
            if len(bank_df) > 1:
                prev = bank_df.iloc[-2]
                prev_value = float(prev['value']) / divisor if divisor > 1 else float(prev['value'])
                change = latest_value - prev_value
                if prev_value != 0:
                    change_pct = (change / abs(prev_value)) * 100

            summary[metric_id] = {
                'name': name,
                'value': latest_value,
                'unit': unit,
                'change': change,
                'change_pct': change_pct,
                'period': latest['period'].strftime('%Y-%m'),
            }

        return summary

    def get_bank_comparison_summary(self) -> pd.DataFrame:
        """Get summary comparison across bank types"""
        metrics = ['total_assets', 'total_loans', 'npl_ratio', 'ldr', 'equity_ratio']

        rows = []
        for metric_id in metrics:
            latest = self.get_latest(metric_id)
            if latest.empty:
                continue
            for _, row in latest.iterrows():
                rows.append({
                    'metric': metric_id,
                    'bank_type': row['bank_type'],
                    'bank_type_code': row['bank_type_code'],
                    'value': row['value'],
                })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        return df.pivot(index='bank_type', columns='metric', values='value').reset_index()

    def list_available_metrics(self) -> List[str]:
        """List all available metric IDs"""
        return list(self._data.keys())


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
data_store = MetricsDataStore()


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("METRICS DATA STORE TEST")
    print("=" * 60)

    store = MetricsDataStore()
    store.initialize()

    print("\n" + "=" * 60)
    print("AVAILABLE METRICS:")
    print("=" * 60)
    for metric in store.list_available_metrics():
        df = store.get(metric)
        print(f"  {metric}: {len(df)} rows")

    print("\n" + "=" * 60)
    print("KPI SUMMARY (Sector):")
    print("=" * 60)
    kpis = store.get_kpi_summary('10001')
    for metric_id, data in kpis.items():
        change_str = f" ({data['change_pct']:+.1f}%)" if data['change_pct'] else ""
        print(f"  {data['name']}: {data['value']:.2f} {data['unit']}{change_str}")

    print("\n" + "=" * 60)
    print("BANK COMPARISON:")
    print("=" * 60)
    comparison = store.get_bank_comparison_summary()
    print(comparison.to_string(index=False))
