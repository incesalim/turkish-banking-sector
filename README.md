# BDDK Banking Analytics

A streamlined system for collecting and visualizing Turkish Banking Regulation and Supervision Agency (BDDK) monthly data.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the system:**
   ```bash
   python run.py
   ```

   This will present you with options to:
   - Download monthly BDDK data
   - Run the interactive dashboard

## Features

- **Monthly Data Collection**: Automated scraping of BDDK monthly banking sector data
- **Database Storage**: SQLite database for efficient data management
- **Interactive Dashboard**: Real-time visualization of banking sector metrics

## Project Structure

```
bddk_analysis/
│
├── src/                      # Source code
│   ├── config.py            # Configuration settings
│   ├── scrapers/            # Data collection modules
│   │   ├── monthly_scraper.py
│   │   └── bddk_table_parser.py
│   ├── database/            # Database management
│   │   └── db_manager.py
│   ├── analytics/           # Analytics engines
│   │   ├── fci_engine.py    # Financial Conditions Index
│   │   └── metrics_engine.py
│   ├── utils/               # Utility functions
│   │   ├── data_processor.py
│   │   └── monthly_data_manager.py
│   └── dashboard/           # Interactive dashboard
│       ├── app.py
│       ├── fci_tab.py       # FCI visualization tab
│       ├── components/
│       ├── data/
│       └── utils/
│
├── data/                    # Data storage
│   ├── raw/                # Downloaded raw data
│   ├── processed/          # Cleaned data
│   └── bddk_data.db       # SQLite database
│
├── archive/                # Legacy code (preserved)
├── docs/                   # Documentation
├── logs/                   # Application logs
│
├── run.py                  # Main entry point
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Dashboard

The dashboard provides:
- Real-time KPIs (Total Assets, NPL Ratio, CAR Ratio, ROA/ROE)
- Asset growth trends
- Bank type market share comparison
- Interactive filters and visualizations
- **Financial Conditions Index (FCI)**: BBVA-style composite indicator of monetary conditions

Access the dashboard at: `http://localhost:8050`

## Data Source

All data is collected from the official BDDK (Bankacılık Düzenleme ve Denetleme Kurumu) website.

## Database

The system uses SQLite for data storage with the following key tables:
- `balance_sheet`: Monthly balance sheet data
- `loans`: Loan portfolio data
- `deposits`: Deposit data
- `ratios`: Financial ratios and metrics

Database location: `data/bddk_data.db`

## Advanced Usage

### Direct Dashboard Launch
```bash
python src/dashboard/app.py
```

### Custom Data Download
```python
from src.scrapers.monthly_scraper import BDDKMonthlyScraper

scraper = BDDKMonthlyScraper(headless=True)
scraper.download_year_data(2024, currency='TL')
scraper.close_driver()
```

## Documentation

Additional documentation is available in the `docs/` directory:
- `METRICS.md` - Full metrics documentation with data sources and formulas
- `USAGE_GUIDE.md` - Detailed usage instructions
- `DASHBOARD_DESIGN.md` - Dashboard architecture
- `PROJECT_SUMMARY.md` - Complete project overview

## Requirements

- Python 3.8+
- Chrome/Chromium (for web scraping)
- See `requirements.txt` for full dependency list

## License

This project is for educational and analytical purposes only. Please respect BDDK's terms of service when using this tool.

## Notes

- The database (`data/bddk_data.db`) contains all historical monthly data
- Legacy code and unused features are preserved in the `archive/` directory
- Logs are automatically rotated and retained for 30 days
