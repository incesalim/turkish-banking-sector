import sqlite3

conn = sqlite3.connect('data/bddk_data.db')
cursor = conn.cursor()

print("=" * 80)
print("BDDK DATABASE - DATA VERIFICATION")
print("=" * 80)

# Count total rows in each table
print("\nROW COUNTS BY TABLE:")
print("-" * 80)

tables = [
    'raw_api_responses',
    'balance_sheet',
    'income_statement',
    'loans',
    'deposits',
    'financial_ratios',
    'other_data'
]

total_rows = 0
for table in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    total_rows += count
    print(f'{table:25s}: {count:>10,} rows')

print(f'\n{"TOTAL DATA ROWS":25s}: {total_rows:>10,} rows')

# Get months downloaded
print("\n" + "=" * 80)
print("MONTHS DOWNLOADED (from balance_sheet table):")
print("-" * 80)

cursor.execute('''
    SELECT DISTINCT year, month
    FROM balance_sheet
    ORDER BY year, month
''')

months = cursor.fetchall()
print(f'\nTotal unique months: {len(months)}\n')

# Group by year
from collections import defaultdict
by_year = defaultdict(list)
for year, month in months:
    by_year[year].append(month)

for year in sorted(by_year.keys()):
    months_list = sorted(by_year[year])
    months_str = ', '.join([f'{m:02d}' for m in months_list])
    print(f'{year}: {months_str} ({len(months_list)} months)')

# Download statistics
print("\n" + "=" * 80)
print("DOWNLOAD STATISTICS:")
print("-" * 80)

cursor.execute('SELECT COUNT(*) FROM raw_api_responses')
api_calls = cursor.fetchone()[0]
print(f'\nTotal API calls made: {api_calls:,}')

cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM download_log
    GROUP BY status
    ORDER BY count DESC
''')

print('\nDownload status:')
for row in cursor.fetchall():
    print(f'  {row[0]:10s}: {row[1]:>6,} downloads')

# Sample data check - most recent download
print("\n" + "=" * 80)
print("MOST RECENT DOWNLOADS:")
print("-" * 80)

cursor.execute('''
    SELECT year, month, table_number, bank_type_code, rows_downloaded
    FROM download_log
    ORDER BY completed_at DESC
    LIMIT 5
''')

print()
for row in cursor.fetchall():
    print(f'  {row[0]}-{row[1]:02d} Table {row[2]:02d} ({row[3]}) - {row[4]} rows')

# Data integrity check
print("\n" + "=" * 80)
print("DATA INTEGRITY CHECK:")
print("-" * 80)

# Check if we have data for each month across different tables
cursor.execute('''
    SELECT year, month, COUNT(DISTINCT id) as row_count
    FROM balance_sheet
    GROUP BY year, month
    ORDER BY year, month
''')

print('\nBalance sheet rows per month:')
for row in cursor.fetchall():
    print(f'  {row[0]}-{row[1]:02d}: {row[2]:>4} rows')

print("\n" + "=" * 80)
print("DATABASE VERIFICATION COMPLETE")
print("=" * 80)

conn.close()
