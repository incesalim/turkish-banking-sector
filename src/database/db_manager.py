"""
Database Manager for BDDK Banking Data

Handles storage and retrieval of banking sector data using SQLite/PostgreSQL.
"""

import pandas as pd
import sqlite3
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path
import sys
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.config import *

Base = declarative_base()


class MonthlyData(Base):
    """Monthly banking sector data model"""
    __tablename__ = 'monthly_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False)
    category = Column(String(100), nullable=False)
    metric_name = Column(String(200))
    metric_value = Column(Float)
    metric_unit = Column(String(50))
    bank_type = Column(String(100))
    data_json = Column(Text)
    download_date = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


class WeeklyData(Base):
    """Weekly banking sector data model"""
    __tablename__ = 'weekly_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    currency = Column(String(10), nullable=False)
    view_type = Column(String(20))
    metric_name = Column(String(200))
    metric_value = Column(Float)
    metric_unit = Column(String(50))
    bank_type = Column(String(100))
    data_json = Column(Text)
    download_date = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


class BankMetrics(Base):
    """Calculated banking metrics and ratios"""
    __tablename__ = 'bank_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_date = Column(Date, nullable=False)
    period_type = Column(String(20))  # 'weekly' or 'monthly'

    # Asset Quality
    total_assets = Column(Float)
    total_loans = Column(Float)
    npl_amount = Column(Float)
    npl_ratio = Column(Float)
    provision_coverage_ratio = Column(Float)

    # Profitability
    net_profit = Column(Float)
    roa = Column(Float)  # Return on Assets
    roe = Column(Float)  # Return on Equity
    nim = Column(Float)  # Net Interest Margin
    cost_income_ratio = Column(Float)

    # Liquidity
    total_deposits = Column(Float)
    liquid_assets = Column(Float)
    loan_deposit_ratio = Column(Float)
    liquidity_coverage_ratio = Column(Float)

    # Capital
    equity = Column(Float)
    capital_adequacy_ratio = Column(Float)
    tier1_ratio = Column(Float)
    leverage_ratio = Column(Float)

    # Growth Rates (YoY)
    asset_growth_rate = Column(Float)
    loan_growth_rate = Column(Float)
    deposit_growth_rate = Column(Float)

    currency = Column(String(10))
    created_at = Column(DateTime, default=datetime.now)


class DatabaseManager:
    """Manager for database operations"""

    def __init__(self, db_type="sqlite", db_path=None):
        """
        Initialize database manager

        Args:
            db_type: Database type ('sqlite', 'postgresql', 'mysql')
            db_path: Database file path (for SQLite)
        """
        self.db_type = db_type

        if db_type == "sqlite":
            self.db_path = db_path or DATABASE_CONFIG['sqlite_path']
            self.engine = create_engine(f'sqlite:///{self.db_path}')
        else:
            # Add PostgreSQL/MySQL connection strings here
            raise NotImplementedError(f"Database type {db_type} not implemented yet")

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        logger.info(f"Database initialized: {self.db_type}")

    def save_monthly_data(self, df, category):
        """
        Save monthly data to database

        Args:
            df: DataFrame with monthly data
            category: Data category
        """
        try:
            table_name = f"{DATABASE_CONFIG['table_prefix']}monthly_{category}"
            df.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"Saved {len(df)} rows to {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error saving monthly data: {str(e)}")
            return False

    def save_weekly_data(self, df):
        """
        Save weekly data to database

        Args:
            df: DataFrame with weekly data
        """
        try:
            table_name = f"{DATABASE_CONFIG['table_prefix']}weekly"
            df.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"Saved {len(df)} rows to {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error saving weekly data: {str(e)}")
            return False

    def save_metrics(self, df):
        """
        Save calculated metrics to database

        Args:
            df: DataFrame with metrics
        """
        try:
            table_name = f"{DATABASE_CONFIG['table_prefix']}metrics"
            df.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info(f"Saved {len(df)} metric rows")
            return True
        except Exception as e:
            logger.error(f"Error saving metrics: {str(e)}")
            return False

    def get_monthly_data(self, year=None, month=None, category=None, currency="TL"):
        """
        Retrieve monthly data from database

        Args:
            year: Filter by year
            month: Filter by month
            category: Filter by category
            currency: Filter by currency

        Returns:
            DataFrame with filtered data
        """
        query = "SELECT * FROM monthly_data WHERE 1=1"
        params = {}

        if year:
            query += " AND year = :year"
            params['year'] = year
        if month:
            query += " AND month = :month"
            params['month'] = month
        if category:
            query += " AND category = :category"
            params['category'] = category
        if currency:
            query += " AND currency = :currency"
            params['currency'] = currency

        try:
            df = pd.read_sql(query, self.engine, params=params)
            logger.info(f"Retrieved {len(df)} monthly data rows")
            return df
        except Exception as e:
            logger.error(f"Error retrieving monthly data: {str(e)}")
            return None

    def get_weekly_data(self, start_date=None, end_date=None, currency="TL"):
        """
        Retrieve weekly data from database

        Args:
            start_date: Start date filter
            end_date: End date filter
            currency: Currency filter

        Returns:
            DataFrame with filtered data
        """
        query = "SELECT * FROM weekly_data WHERE currency = :currency"
        params = {'currency': currency}

        if start_date:
            query += " AND date >= :start_date"
            params['start_date'] = start_date
        if end_date:
            query += " AND date <= :end_date"
            params['end_date'] = end_date

        query += " ORDER BY date DESC"

        try:
            df = pd.read_sql(query, self.engine, params=params)
            logger.info(f"Retrieved {len(df)} weekly data rows")
            return df
        except Exception as e:
            logger.error(f"Error retrieving weekly data: {str(e)}")
            return None

    def get_metrics_timeseries(self, metric_name, start_date=None, end_date=None,
                                period_type='monthly', currency="TL"):
        """
        Get time series for a specific metric

        Args:
            metric_name: Name of the metric column
            start_date: Start date
            end_date: End date
            period_type: 'monthly' or 'weekly'
            currency: Currency

        Returns:
            DataFrame with time series
        """
        query = f"""
            SELECT period_date, {metric_name}, currency, period_type
            FROM bank_metrics
            WHERE period_type = :period_type AND currency = :currency
        """
        params = {'period_type': period_type, 'currency': currency}

        if start_date:
            query += " AND period_date >= :start_date"
            params['start_date'] = start_date
        if end_date:
            query += " AND period_date <= :end_date"
            params['end_date'] = end_date

        query += " ORDER BY period_date"

        try:
            df = pd.read_sql(query, self.engine, params=params)
            logger.info(f"Retrieved {len(df)} rows for metric {metric_name}")
            return df
        except Exception as e:
            logger.error(f"Error retrieving metric time series: {str(e)}")
            return None

    def get_latest_metrics(self, period_type='monthly', currency="TL"):
        """
        Get the most recent metrics

        Args:
            period_type: 'monthly' or 'weekly'
            currency: Currency

        Returns:
            DataFrame with latest metrics
        """
        query = """
            SELECT *
            FROM bank_metrics
            WHERE period_type = :period_type AND currency = :currency
            ORDER BY period_date DESC
            LIMIT 1
        """
        params = {'period_type': period_type, 'currency': currency}

        try:
            df = pd.read_sql(query, self.engine, params=params)
            logger.info("Retrieved latest metrics")
            return df
        except Exception as e:
            logger.error(f"Error retrieving latest metrics: {str(e)}")
            return None

    def export_to_excel(self, output_path, tables=None):
        """
        Export database tables to Excel file

        Args:
            output_path: Output file path
            tables: List of table names (None = all tables)
        """
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                if tables is None:
                    tables = ['monthly_data', 'weekly_data', 'bank_metrics']

                for table in tables:
                    df = pd.read_sql(f"SELECT * FROM {table}", self.engine)
                    df.to_excel(writer, sheet_name=table, index=False)

            logger.info(f"Exported database to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting to Excel: {str(e)}")
            return False

    def clear_table(self, table_name):
        """Clear all data from a table"""
        try:
            with self.engine.connect() as conn:
                conn.execute(f"DELETE FROM {table_name}")
            logger.info(f"Cleared table {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error clearing table: {str(e)}")
            return False


def main():
    """Example usage"""
    db = DatabaseManager()

    # Example: Save some data
    sample_df = pd.DataFrame({
        'year': [2024],
        'month': [11],
        'currency': ['TL'],
        'category': ['balance_sheet'],
        'metric_name': ['Total Assets'],
        'metric_value': [1000000]
    })

    db.save_monthly_data(sample_df, 'balance_sheet')

    # Retrieve data
    data = db.get_monthly_data(year=2024, currency='TL')
    print(data)


if __name__ == "__main__":
    main()
