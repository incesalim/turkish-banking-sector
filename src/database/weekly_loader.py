"""
Weekly Data Loader
==================
Loads scraped weekly bulletin data into the database.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional
import re

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.config import DATABASE_CONFIG, RAW_DATA_DIR


# Turkish month names for date parsing
TURKISH_MONTHS = {
    'Ocak': 1, 'Şubat': 2, 'Mart': 3, 'Nisan': 4,
    'Mayıs': 5, 'Haziran': 6, 'Temmuz': 7, 'Ağustos': 8,
    'Eylül': 9, 'Ekim': 10, 'Kasım': 11, 'Aralık': 12
}


def parse_turkish_date(date_str: str) -> Optional[datetime]:
    """
    Parse Turkish date string like "16 Ocak 2026 Cuma" to datetime.

    Args:
        date_str: Date string in Turkish format

    Returns:
        datetime object or None
    """
    if not date_str:
        return None

    try:
        # Pattern: "16 Ocak 2026" or "17 Ekim 2025 Cuma"
        match = re.search(r'(\d+)\s+(\w+)\s+(\d{4})', date_str)
        if match:
            day, month_name, year = match.groups()
            month = TURKISH_MONTHS.get(month_name)
            if month:
                return datetime(int(year), month, int(day))
    except Exception:
        pass

    return None


def create_weekly_tables(db_path: Path = None):
    """
    Create weekly data tables in the database.

    Args:
        db_path: Path to SQLite database
    """
    if db_path is None:
        db_path = DATABASE_CONFIG['sqlite_path']

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop existing weekly_bulletin table if it exists
    cursor.execute('DROP TABLE IF EXISTS weekly_bulletin')

    # Create weekly_bulletin table for detailed data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weekly_bulletin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id VARCHAR(10),
            period_date DATE,
            week_number INTEGER,
            year INTEGER,
            category VARCHAR(50),
            item_id INTEGER,
            item_name VARCHAR(200),
            tp_value FLOAT,
            yp_value FLOAT,
            total_value FLOAT,
            bank_type_code VARCHAR(10) DEFAULT '10001',
            currency VARCHAR(10) DEFAULT 'TL',
            download_date DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_weekly_bulletin_period
        ON weekly_bulletin(period_id, category)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_weekly_bulletin_date
        ON weekly_bulletin(period_date, item_name)
    ''')

    conn.commit()
    conn.close()
    print("Weekly tables created successfully")


def load_weekly_csv(csv_path: Path, db_path: Path = None) -> int:
    """
    Load a weekly CSV file into the database.

    Args:
        csv_path: Path to CSV file from scraper
        db_path: Path to SQLite database

    Returns:
        Number of rows inserted
    """
    if db_path is None:
        db_path = DATABASE_CONFIG['sqlite_path']

    # Read CSV
    df = pd.read_csv(csv_path)

    if df.empty:
        return 0

    # Extract category from filename
    category = csv_path.stem.split('_')[0]  # e.g., 'krediler' from 'krediler_20260124_222732.csv'

    # Parse date from date_str column if available
    if 'date_str' in df.columns:
        df['period_date'] = df['date_str'].apply(parse_turkish_date)
        df['year'] = df['period_date'].apply(lambda x: x.year if x else None)
        df['week_number'] = df['period_date'].apply(
            lambda x: x.isocalendar()[1] if x else None
        )
    else:
        df['period_date'] = None
        df['year'] = None
        df['week_number'] = None

    # Rename columns to match database schema
    df = df.rename(columns={
        'row_id': 'item_id',
    })

    # Add metadata
    df['category'] = category
    df['bank_type_code'] = '10001'  # Sector default
    df['currency'] = 'TL'
    df['download_date'] = datetime.now()

    # Select columns for database
    columns = [
        'period_id', 'period_date', 'week_number', 'year', 'category',
        'item_id', 'item_name', 'tp_value', 'yp_value', 'total_value',
        'bank_type_code', 'currency', 'download_date'
    ]

    df_insert = df[[c for c in columns if c in df.columns]]

    # Insert into database
    conn = sqlite3.connect(db_path)

    # Check for existing data to avoid duplicates
    existing = pd.read_sql(
        'SELECT DISTINCT period_id FROM weekly_bulletin WHERE category = ?',
        conn, params=(category,)
    )
    existing_periods = set(existing['period_id'].tolist())

    # Filter out existing periods
    new_data = df_insert[~df_insert['period_id'].isin(existing_periods)]

    if new_data.empty:
        print(f"No new data to insert (all periods already exist)")
        conn.close()
        return 0

    # Insert new data
    new_data.to_sql('weekly_bulletin', conn, if_exists='append', index=False)
    rows_inserted = len(new_data)

    conn.close()
    print(f"Inserted {rows_inserted} rows from {csv_path.name}")

    return rows_inserted


def load_all_weekly_csvs(data_dir: Path = None, db_path: Path = None) -> int:
    """
    Load all weekly CSV files from the raw data directory.

    Args:
        data_dir: Directory containing CSV files
        db_path: Path to SQLite database

    Returns:
        Total number of rows inserted
    """
    if data_dir is None:
        data_dir = RAW_DATA_DIR / "weekly"

    csv_files = list(data_dir.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files")

    total_rows = 0
    for csv_file in csv_files:
        rows = load_weekly_csv(csv_file, db_path)
        total_rows += rows

    return total_rows


def get_weekly_loans_data(db_path: Path = None, weeks: int = 13) -> pd.DataFrame:
    """
    Get weekly loans data from database.

    Args:
        db_path: Path to SQLite database
        weeks: Number of weeks to retrieve

    Returns:
        DataFrame with weekly loans data
    """
    if db_path is None:
        db_path = DATABASE_CONFIG['sqlite_path']

    query = '''
        SELECT
            period_id,
            period_date,
            week_number,
            year,
            item_name,
            tp_value,
            yp_value,
            total_value
        FROM weekly_bulletin
        WHERE category = 'krediler'
        ORDER BY period_date DESC
        LIMIT ?
    '''

    conn = sqlite3.connect(db_path)
    df = pd.read_sql(query, conn, params=(weeks * 22,))  # 22 items per week
    conn.close()

    # Parse date
    df['period_date'] = pd.to_datetime(df['period_date'])

    return df


def calculate_13w_annualized_growth(db_path: Path = None) -> pd.DataFrame:
    """
    Calculate 13-week annualized growth for key metrics.

    Formula: ((End Value / Start Value) ^ (52/13) - 1) * 100

    Args:
        db_path: Path to SQLite database

    Returns:
        DataFrame with growth metrics
    """
    df = get_weekly_loans_data(db_path, weeks=14)

    if df.empty:
        return pd.DataFrame()

    # Get key metrics (Total Loans row)
    total_loans = df[df['item_name'].str.contains('Toplam Krediler', na=False)]

    if len(total_loans) < 14:
        print(f"Not enough data points: {len(total_loans)} (need 14)")
        return pd.DataFrame()

    # Sort by date
    total_loans = total_loans.sort_values('period_date')

    # Calculate growth
    latest = total_loans.iloc[-1]
    week_13_ago = total_loans.iloc[-14]

    start_value = week_13_ago['total_value']
    end_value = latest['total_value']

    # 13-week growth annualized
    growth_13w = (end_value / start_value) ** (52/13) - 1
    growth_13w_pct = growth_13w * 100

    # Simple 13-week growth (not annualized)
    simple_13w = (end_value - start_value) / start_value * 100

    result = {
        'metric': 'Total Loans',
        'start_date': week_13_ago['period_date'],
        'end_date': latest['period_date'],
        'start_value': start_value,
        'end_value': end_value,
        'growth_13w_simple_pct': simple_13w,
        'growth_13w_annualized_pct': growth_13w_pct,
    }

    return pd.DataFrame([result])


if __name__ == "__main__":
    # Create tables
    create_weekly_tables()

    # Load all weekly CSVs
    total = load_all_weekly_csvs()
    print(f"\nTotal rows inserted: {total}")

    # Test query
    df = get_weekly_loans_data(weeks=3)
    if not df.empty:
        print(f"\nLoaded {len(df)} rows")
        print(df[df['item_name'].str.contains('Toplam Krediler', na=False)][['period_date', 'total_value']])
