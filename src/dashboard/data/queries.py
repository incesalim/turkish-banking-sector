"""
SQL queries for BDDK Banking Analytics Dashboard
"""

import pandas as pd
from typing import Optional, List
from .db_manager import db_manager

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from src.config import DEFAULT_METRICS


def get_latest_month() -> tuple:
    """Get the most recent year and month in the database

    Returns:
        Tuple of (year, month)
    """
    query = """
    SELECT year, month
    FROM balance_sheet
    ORDER BY year DESC, month DESC
    LIMIT 1
    """
    result = db_manager.execute_query(query)
    if not result.empty:
        return result.iloc[0]['year'], result.iloc[0]['month']
    return 2025, 12  # Default


def get_kpi_data(year: int, month: int, bank_type_code: str = '10001') -> dict:
    """Get KPI data for a specific month

    Args:
        year: Year
        month: Month (1-12)
        bank_type_code: Bank type code (default: '10001' for Sector)

    Returns:
        Dictionary with KPI values
    """
    # Get total assets
    assets_query = """
    SELECT SUM(amount_total) as total_assets
    FROM balance_sheet
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND item_name LIKE '%TOPLAM AKT%'
    """
    assets = db_manager.execute_query(assets_query, (year, month, bank_type_code))

    # Get total loans
    loans_query = """
    SELECT SUM(total_amount) as total_loans
    FROM loans
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND item_name LIKE '%TOPLAM%'
    """
    loans = db_manager.execute_query(loans_query, (year, month, bank_type_code))

    # Get NPL (Non-Performing Loans) amount
    npl_query = """
    SELECT SUM(npl_amount) as npl_total
    FROM loans
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND item_name LIKE '%TOPLAM%'
    """
    npl_data = db_manager.execute_query(npl_query, (year, month, bank_type_code))

    # Calculate NPL ratio
    total_loans_val = loans['total_loans'].iloc[0] if not loans.empty and not pd.isna(loans['total_loans'].iloc[0]) else 0
    npl_amount = npl_data['npl_total'].iloc[0] if not npl_data.empty and not pd.isna(npl_data['npl_total'].iloc[0]) else 0

    if total_loans_val > 0 and npl_amount > 0:
        npl_ratio = (npl_amount / total_loans_val) * 100
    else:
        npl_ratio = DEFAULT_METRICS['npl_ratio']

    # Get equity capital for CAR calculation
    equity_query = """
    SELECT SUM(amount_total) as equity
    FROM balance_sheet
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND (item_name LIKE '%ÖZKAYN%' OR item_name LIKE '%SERMAYE%')
    AND item_name LIKE '%TOPLAM%'
    """
    equity = db_manager.execute_query(equity_query, (year, month, bank_type_code))

    # Calculate CAR ratio (simplified - equity / risk-weighted assets)
    # Using total assets as approximation for risk-weighted assets
    total_assets_val = assets['total_assets'].iloc[0] if not assets.empty and not pd.isna(assets['total_assets'].iloc[0]) else 0
    equity_val = equity['equity'].iloc[0] if not equity.empty and not pd.isna(equity['equity'].iloc[0]) else 0

    if total_assets_val > 0 and equity_val > 0:
        car_ratio = (equity_val / total_assets_val) * 100
    else:
        car_ratio = DEFAULT_METRICS['car_ratio']

    return {
        'total_assets': total_assets_val,
        'total_loans': total_loans_val,
        'npl_ratio': npl_ratio,
        'car_ratio': car_ratio,
        'npl_amount': npl_amount,
        'equity': equity_val,
    }


def get_time_series_data(
    table: str = 'balance_sheet',
    metric_column: str = 'amount_total',
    bank_type_code: str = '10001',
    start_year: int = 2024,
    end_year: int = 2025
) -> pd.DataFrame:
    """Get time series data for charting

    Args:
        table: Table name (balance_sheet, loans, deposits, etc.)
        metric_column: Column to aggregate
        bank_type_code: Bank type code filter
        start_year: Start year
        end_year: End year

    Returns:
        DataFrame with year, month, value columns
    """
    query = f"""
    SELECT year, month, SUM({metric_column}) as value
    FROM {table}
    WHERE bank_type_code = ?
    AND year BETWEEN ? AND ?
    GROUP BY year, month
    ORDER BY year, month
    """
    return db_manager.execute_query(query, (bank_type_code, start_year, end_year))


def get_assets_trend(bank_type_code: str = '10001') -> pd.DataFrame:
    """Get total assets trend over time

    Args:
        bank_type_code: Bank type code filter

    Returns:
        DataFrame with date and total_assets columns
    """
    query = """
    SELECT
        year,
        month,
        SUM(amount_total) / 1000000 as total_assets_millions
    FROM balance_sheet
    WHERE bank_type_code = ?
    AND item_name LIKE '%TOPLAM AKT%'
    GROUP BY year, month
    ORDER BY year, month
    """
    df = db_manager.execute_query(query, (bank_type_code,))

    # Create date column for better plotting
    df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01')

    return df


def get_bank_types() -> List[dict]:
    """Get list of available bank types

    Bank type hierarchy:
        SECTOR (10001) = 10003 + 10004 + 10005 + 10006 + 10007
        Deposit Banks (10002) = 10003 + 10004 + 10005

    Returns:
        List of dictionaries with code and name
    """
    return [
        # Sector total
        {'code': '10001', 'name': 'Sector (All Banks)'},
        # By business model
        {'code': '10002', 'name': 'Deposit Banks (All)'},
        {'code': '10006', 'name': 'Participation Banks'},
        {'code': '10007', 'name': 'Dev & Investment Banks'},
        # Deposit banks by ownership
        {'code': '10003', 'name': 'Private Deposit Banks'},
        {'code': '10004', 'name': 'State Deposit Banks'},
        {'code': '10005', 'name': 'Foreign Deposit Banks'},
        # Cross-cutting by ownership (across all business models)
        {'code': '10008', 'name': 'All Domestic Private'},
        {'code': '10009', 'name': 'All Public/State'},
        {'code': '10010', 'name': 'All Foreign-owned'},
    ]


def get_bank_type_comparison(year: int, month: int) -> pd.DataFrame:
    """Get comparison metrics across different bank types

    Args:
        year: Year
        month: Month

    Returns:
        DataFrame with bank types and their metrics
    """
    query = """
    SELECT
        bank_type_code,
        MAX(amount_total) / 1000000 as total_assets_millions
    FROM balance_sheet
    WHERE year = ? AND month = ?
    AND item_name LIKE '%TOPLAM AKT%'
    AND bank_type_code != '10001'
    GROUP BY bank_type_code
    ORDER BY total_assets_millions DESC
    """
    df = db_manager.execute_query(query, (year, month))

    # Add names for better display
    # Bank hierarchy: 10001 = 10003+10004+10005+10006+10007
    bank_types = {
        '10002': 'Deposit Banks',
        '10003': 'Private Deposit',
        '10004': 'State Deposit',
        '10005': 'Foreign Deposit',
        '10006': 'Participation',
        '10007': 'Dev & Investment',
        '10008': 'All Private',
        '10009': 'All Public',
        '10010': 'All Foreign',
    }
    df['bank_type_name'] = df['bank_type_code'].map(bank_types)

    return df


def get_available_date_range() -> dict:
    """Get min and max dates available in database

    Returns:
        Dictionary with min_year, min_month, max_year, max_month
    """
    query = """
    SELECT
        MIN(year) as min_year,
        MIN(month) as min_month,
        MAX(year) as max_year,
        MAX(month) as max_month
    FROM balance_sheet
    """
    result = db_manager.execute_query(query)

    if not result.empty:
        return {
            'min_year': int(result.iloc[0]['min_year']),
            'min_month': int(result.iloc[0]['min_month']),
            'max_year': int(result.iloc[0]['max_year']),
            'max_month': int(result.iloc[0]['max_month']),
        }
    return {'min_year': 2024, 'min_month': 1, 'max_year': 2025, 'max_month': 12}


def get_loan_portfolio_mix(year: int, month: int, bank_type_code: str = '10001') -> pd.DataFrame:
    """Get loan portfolio composition

    Args:
        year: Year
        month: Month
        bank_type_code: Bank type code

    Returns:
        DataFrame with loan types and amounts
    """
    query = """
    SELECT
        item_name as loan_type,
        total_amount / 1000000 as amount_millions
    FROM loans
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND item_name NOT LIKE '%TOPLAM%'
    ORDER BY total_amount DESC
    LIMIT 10
    """
    return db_manager.execute_query(query, (year, month, bank_type_code))


def get_profitability_ratios(year: int, month: int, bank_type_code: str = '10001') -> dict:
    """Get profitability ratios (ROA, ROE) from financial ratios or calculate from income statement

    Args:
        year: Year
        month: Month
        bank_type_code: Bank type code

    Returns:
        Dictionary with ROA and ROE values
    """
    # Try to get from financial_ratios table
    # ROA typically contains "AKT" (assets) and "GET" (return)
    # ROE typically contains "ÖZKAYN" (equity) and "GET" (return)

    roa_query = """
    SELECT ratio_value as roa
    FROM financial_ratios
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND (item_name LIKE '%AKT%GET%' OR item_name LIKE '%ROA%')
    LIMIT 1
    """
    roa_result = db_manager.execute_query(roa_query, (year, month, bank_type_code))

    roe_query = """
    SELECT ratio_value as roe
    FROM financial_ratios
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND (item_name LIKE '%ÖZKAYN%GET%' OR item_name LIKE '%ROE%')
    LIMIT 1
    """
    roe_result = db_manager.execute_query(roe_query, (year, month, bank_type_code))

    # If not found in financial_ratios, calculate from income statement
    if roa_result.empty or roe_result.empty:
        # Get net income from income statement
        income_query = """
        SELECT SUM(amount_total) as net_income
        FROM income_statement
        WHERE year = ? AND month = ? AND bank_type_code = ?
        AND (item_name LIKE '%NET KAR%' OR item_name LIKE '%NET D%NEM%')
        """
        income = db_manager.execute_query(income_query, (year, month, bank_type_code))

        # Get total assets and equity
        kpi_data = get_kpi_data(year, month, bank_type_code)

        net_income_val = income['net_income'].iloc[0] if not income.empty and not pd.isna(income['net_income'].iloc[0]) else 0

        if net_income_val > 0:
            roa = (net_income_val / kpi_data['total_assets']) * 100 if kpi_data['total_assets'] > 0 else DEFAULT_METRICS['roa']
            roe = (net_income_val / kpi_data['equity']) * 100 if kpi_data['equity'] > 0 else DEFAULT_METRICS['roe']
        else:
            roa = DEFAULT_METRICS['roa']
            roe = DEFAULT_METRICS['roe']
    else:
        roa = roa_result['roa'].iloc[0] if not roa_result.empty else DEFAULT_METRICS['roa']
        roe = roe_result['roe'].iloc[0] if not roe_result.empty else DEFAULT_METRICS['roe']

    return {
        'roa': roa,
        'roe': roe
    }


def get_npl_trend(bank_type_code: str = '10001') -> pd.DataFrame:
    """Get NPL ratio trend over time

    Args:
        bank_type_code: Bank type code filter

    Returns:
        DataFrame with date and npl_ratio columns
    """
    query = """
    SELECT
        year,
        month,
        SUM(npl_amount) as npl_total,
        SUM(total_amount) as loans_total
    FROM loans
    WHERE bank_type_code = ?
    AND item_name LIKE '%TOPLAM%'
    GROUP BY year, month
    ORDER BY year, month
    """
    df = db_manager.execute_query(query, (bank_type_code,))

    # Calculate NPL ratio
    df['npl_ratio'] = (df['npl_total'] / df['loans_total'] * 100).round(2)

    # Create date column
    df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01')

    return df[['date', 'npl_ratio']]


def get_deposit_mix(year: int, month: int, bank_type_code: str = '10001') -> pd.DataFrame:
    """Get deposit composition

    Args:
        year: Year
        month: Month
        bank_type_code: Bank type code

    Returns:
        DataFrame with deposit types and amounts
    """
    query = """
    SELECT
        item_name as deposit_type,
        total_amount / 1000000 as amount_millions
    FROM deposits
    WHERE year = ? AND month = ? AND bank_type_code = ?
    AND item_name NOT LIKE '%TOPLAM%'
    ORDER BY total_amount DESC
    LIMIT 10
    """
    return db_manager.execute_query(query, (year, month, bank_type_code))
