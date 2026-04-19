"""
BDDK Banking Analytics Dashboard - Launch Script
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the dashboard
from dashboard.app import app

if __name__ == '__main__':
    print("\n" + "="*80)
    print("BDDK Banking Analytics Dashboard")
    print("="*80)
    print(f"Data: 22 months (Jan 2024 - Oct 2025)")
    print(f"191,170 data points across all tables")
    print("="*80)
    print(f"\nStarting server...")
    print(f"Dashboard URL: http://localhost:8050")
    print(f"\nPress Ctrl+C to stop the server\n")
    print("="*80 + "\n")

    # Run the dashboard
    app.run_server(debug=True, host='0.0.0.0', port=8050)
