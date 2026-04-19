"""
Test dashboard data queries to identify issues
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dashboard.data.queries import (
    get_latest_month,
    get_kpi_data,
    get_assets_trend,
    get_bank_type_comparison
)

print("="*80)
print("Testing Dashboard Data Queries")
print("="*80)

# Test 1: Get latest month
print("\n1. Testing get_latest_month():")
try:
    latest_year, latest_month = get_latest_month()
    print(f"   [OK] Latest month: {latest_year}-{latest_month}")
except Exception as e:
    print(f"   [ERROR] Error: {e}")

# Test 2: Get KPI data
print("\n2. Testing get_kpi_data():")
try:
    kpi_data = get_kpi_data(2025, 10, '10001')
    print(f"   Total Assets: {kpi_data['total_assets']:,.0f}")
    print(f"   Total Loans: {kpi_data['total_loans']:,.0f}")
    print(f"   NPL Ratio: {kpi_data['npl_ratio']}%")
    print(f"   CAR Ratio: {kpi_data['car_ratio']}%")
except Exception as e:
    print(f"   [ERROR] Error: {e}")

# Test 3: Get previous month KPI data
print("\n3. Testing get_kpi_data() for previous month:")
try:
    prev_kpi = get_kpi_data(2025, 9, '10001')
    print(f"   Total Assets (Sep 2025): {prev_kpi['total_assets']:,.0f}")
except Exception as e:
    print(f"   [ERROR] Error: {e}")

# Test 4: Get assets trend
print("\n4. Testing get_assets_trend():")
try:
    df = get_assets_trend('10001')
    print(f"   [OK] Retrieved {len(df)} months of data")
    if len(df) > 0:
        print(f"   First month: {df.iloc[0]['year']}-{df.iloc[0]['month']}")
        print(f"   Last month: {df.iloc[-1]['year']}-{df.iloc[-1]['month']}")
        print(f"   First 3 rows:")
        print(df.head(3))
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Get bank type comparison
print("\n5. Testing get_bank_type_comparison():")
try:
    df = get_bank_type_comparison(2025, 10)
    print(f"   [OK] Retrieved {len(df)} bank types")
    if len(df) > 0:
        print(f"   Bank types found:")
        print(df)
    else:
        print(f"   [ERROR] No data returned!")
except Exception as e:
    print(f"   [ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
