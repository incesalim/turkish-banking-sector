## 🎯 NEW PROFESSIONAL SYSTEM - Complete Guide

# Enterprise-Grade BDDK Banking Analysis System

## What's New?

### ✨ **Major Upgrades**

1. **📊 Professional Dashboard**
   - Enterprise-grade UI with Bootstrap
   - Interactive drill-down capabilities
   - Real-time data filtering
   - Export to Excel functionality
   - Comparative period analysis
   - Beautiful charts and KPI cards

2. **🗄️ Smart Monthly Data Management**
   - Incremental monthly updates
   - No duplicate data
   - Automatic version control
   - Missing period detection
   - Easy data consolidation

3. **📄 BDDK Table Parser**
   - Parses real BDDK HTML tables
   - Handles hierarchical structure
   - Turkish number format support
   - Category detection
   - Key metrics extraction

---

## 🚀 How to Use the New System

### **1. Adding Monthly Data**

#### **Method A: From HTML File**

Save the BDDK table page as HTML, then:

```bash
# Interactive mode (easiest)
python add_monthly_data.py --interactive

# Command line mode
python add_monthly_data.py --file bddk_table.html --year 2024 --month 10 --currency TL --type bilanco
```

#### **Method B: From Web Scraper**

```python
from scrapers.weekly_scraper import BDDKWeeklyScraper
from scrapers.bddk_table_parser import BDDKTableParser
from utils.monthly_data_manager import MonthlyDataManager

# Download data
scraper = BDDKWeeklyScraper()
html_content = scraper.get_latest_data()  # Gets HTML

# Parse
parser = BDDKTableParser()
df = parser.parse_bddk_table(html_content, data_type='bilanco')

# Add to database
manager = MonthlyDataManager()
manager.add_monthly_data(df, year=2024, month=10, currency='TL')
```

---

### **2. Viewing Data Summary**

```bash
# See what data you have
python add_monthly_data.py --summary
```

**Output:**
```
📊 Turkish Lira (TL) Data:
  Total Periods: 48
  Date Range: 2020-01 to 2023-12

  Data Types:
    bilanco:
      Periods: 48
      Latest: 2023-12
      Total Rows: 2,340
```

---

### **3. Checking Missing Periods**

```bash
# Find gaps in your data
python add_monthly_data.py --check-missing --year 2024 --currency TL
```

**Output:**
```
⚠️  Found 3 missing periods:
  2024-01 - January 2024
  2024-02 - February 2024
  2024-03 - March 2024
```

---

### **4. Launch Professional Dashboard**

```bash
# Start the new dashboard
python -c "from visualizations.professional_dashboard import ProfessionalBankingDashboard; dashboard = ProfessionalBankingDashboard(); dashboard.run()"
```

**Or create a shortcut:**
```bash
# Save as run_dashboard.py
from visualizations.professional_dashboard import ProfessionalBankingDashboard

dashboard = ProfessionalBankingDashboard()
dashboard.run(debug=True, port=8050)
```

Then: `python run_dashboard.py`

Open: **http://localhost:8050**

---

## 📊 Dashboard Features

### **Navigation**
- 🏠 **Overview**: Top categories, distribution charts
- 📈 **Trends**: Historical trend analysis
- 🔍 **Deep Dive**: Category breakdowns
- ⚖️ **Comparative**: Period-to-period comparison
- 📑 **Data Table**: Interactive filterable table

### **Controls**
- **Period Selector**: Choose which month to view
- **Currency**: Switch between TL and USD
- **Compare With**: Select another period for comparison
- **Data Type**: Balance Sheet, Income Statement, Loans, Deposits
- **View**: Toggle between table and charts

### **KPI Cards**
- Total Items
- Total (TP) - Turkish Lira portion
- Total (YP) - Foreign Currency portion
- Grand Total with % change

### **Export**
- Export tables to Excel
- Download charts as PNG
- Print-ready reports

---

## 🗂️ File Organization

### **New Files Added:**

```
bddk_analysis/
├── scrapers/
│   └── bddk_table_parser.py         ← NEW: Parse BDDK HTML tables
│
├── utils/
│   └── monthly_data_manager.py      ← NEW: Handle monthly data updates
│
├── visualizations/
│   └── professional_dashboard.py    ← NEW: Enterprise dashboard
│
└── add_monthly_data.py               ← NEW: Easy data entry script
```

### **Database Structure:**

The system now stores data in **structured tables**:

- `bddk_monthly_bilanco` - Balance sheet data
- `bddk_monthly_gelir_gider` - Income statement
- `bddk_monthly_krediler` - Loans
- `bddk_monthly_mevduat` - Deposits

**Columns:**
- `item_name` - Full item name
- `item_name_clean` - Cleaned name (no numbers)
- `level` - Hierarchy level (0=main, 1=sub, 2=detail)
- `category` - Parent category
- `subcategory` - Parent subcategory
- `tp` - Turkish Lira value
- `yp` - Foreign Currency value
- `total` - Combined total
- `year`, `month`, `currency`, `data_type` - Metadata
- `period_date`, `added_date` - Timestamps

---

## 💡 Common Workflows

### **Monthly Update Workflow**

```bash
# 1. Download BDDK data (save as HTML from browser)
#    https://www.bddk.org.tr/BultenAylik

# 2. Add to database
python add_monthly_data.py --interactive

# 3. Check it was added
python add_monthly_data.py --summary

# 4. View in dashboard
python run_dashboard.py
```

### **Bulk Historical Data**

```python
from utils.monthly_data_manager import MonthlyDataManager
from scrapers.bddk_table_parser import BDDKTableParser

manager = MonthlyDataManager()
parser = BDDKTableParser()

# Loop through your HTML files
for year in range(2020, 2025):
    for month in range(1, 13):
        html_file = f"data/html/bilanco_{year}_{month:02d}.html"

        if Path(html_file).exists():
            df = parser.parse_from_file(html_file)
            manager.add_monthly_data(df, year, month, 'TL', 'bilanco')
```

### **Compare Two Periods**

```python
from utils.database import DatabaseManager

db = DatabaseManager()

# Get two periods
oct_2024 = db.get_monthly_data(2024, 10, 'bilanco', 'TL')
sep_2024 = db.get_monthly_data(2024, 9, 'bilanco', 'TL')

# Compare totals
oct_total = oct_2024['total'].sum()
sep_total = sep_2024['total'].sum()

change_pct = ((oct_total - sep_total) / sep_total) * 100

print(f"Month-over-month change: {change_pct:.2f}%")
```

---

## 🎨 Dashboard Customization

### **Change Colors**

Edit `professional_dashboard.py`:

```python
COLORS = {
    'primary': '#YOUR_COLOR',      # Main color
    'secondary': '#YOUR_COLOR',    # Secondary
    'success': '#10B981',          # Green
    'warning': '#F59E0B',          # Amber
    'danger': '#EF4444',           # Red
}
```

### **Add Custom KPIs**

In `_calculate_kpis()` method:

```python
def _calculate_kpis(self, df, compare_data=None):
    kpis = {
        'total_items': len(df),
        # Add your custom KPI
        'custom_metric': df['your_column'].sum(),
    }
    return kpis
```

### **Add Custom Charts**

In `_create_overview_tab()`:

```python
# Your custom chart
fig_custom = go.Figure()
fig_custom.add_trace(go.Scatter(
    x=df['date'],
    y=df['value'],
    mode='lines'
))
```

---

## 🔧 Advanced Features

### **1. Consolidate Historical Data**

```python
from utils.monthly_data_manager import MonthlyDataManager

manager = MonthlyDataManager()

# Get all data from 2020-2024
consolidated = manager.consolidate_data(
    start_year=2020,
    end_year=2024,
    currency='TL',
    data_type='bilanco'
)

# Now you have a single DataFrame with all periods
print(f"Total rows: {len(consolidated)}")

# Use for analysis
from analysis.financial_analyzer import BankingFinancialAnalyzer
analyzer = BankingFinancialAnalyzer()
report = analyzer.comprehensive_analysis(consolidated)
```

### **2. Export Period Data**

```python
manager = MonthlyDataManager()

# Export October 2024 data
files = manager.export_period_data(
    year=2024,
    month=10,
    currency='TL',
    output_dir='exports/2024_10'
)

# files will be:
# {
#     'bilanco': 'exports/2024_10/bilanco_2024_10_TL.csv',
#     'krediler': 'exports/2024_10/krediler_2024_10_TL.csv',
#     ...
# }
```

### **3. Extract Key Metrics**

```python
from scrapers.bddk_table_parser import BDDKTableParser

parser = BDDKTableParser()
df = parser.parse_from_file('bilanco.html')

# Auto-extract key banking metrics
metrics = parser.extract_key_metrics(df)

# metrics will contain:
# {
#     'total_assets': 12500000,
#     'total_loans': 8200000,
#     'total_deposits': 9000000,
#     'equity': 1500000,
#     'npl': 300000,
#     'liquid_assets': 2000000
# }
```

---

## 📈 Dashboard Screenshots

### **Overview Tab**
- Top 10 categories horizontal bar chart
- TP vs YP distribution pie chart
- KPI cards showing key metrics

### **Data Table Tab**
- Filterable columns
- Sortable headers
- Export to Excel button
- Pagination
- Search functionality

### **Comparative Tab**
- Side-by-side period comparison
- Change indicators (↑↓)
- Percentage changes
- Waterfall charts

---

## 🎯 Best Practices

### **Data Management**

1. **Always check for duplicates**
   ```bash
   python add_monthly_data.py --summary
   ```

2. **Keep CSV backups**
   - Automatically saved to `data/processed/monthly_backups/`

3. **Use interactive mode for safety**
   ```bash
   python add_monthly_data.py --interactive
   ```

### **Dashboard Performance**

1. **Filter data for better performance**
   - Load specific periods instead of all data
   - Use the period selector

2. **Cache heavy calculations**
   - Dashboard uses dcc.Store for caching

3. **Export large datasets**
   - Use data table export instead of viewing all rows

---

## 🐛 Troubleshooting

### **Problem: HTML parsing fails**

```python
# Debug parsing
from scrapers.bddk_table_parser import BDDKTableParser

parser = BDDKTableParser()
df = parser.parse_from_file('your_file.html', data_type='bilanco')

if df is None:
    print("Parsing failed - check HTML structure")
else:
    print(f"Parsed {len(df)} rows")
    print(df.head())
```

### **Problem: Dashboard shows no data**

```bash
# Check database
python add_monthly_data.py --summary

# If empty, add sample data
python demo.py  # Adds sample data to database
```

### **Problem: Duplicate data error**

```python
from utils.monthly_data_manager import MonthlyDataManager

manager = MonthlyDataManager()

# Delete specific period
manager.delete_monthly_data(year=2024, month=10, currency='TL', data_type='bilanco')

# Then add again
```

---

## 🚀 Next Steps

1. **Add Your Real Data**
   ```bash
   python add_monthly_data.py --interactive
   ```

2. **Launch Dashboard**
   ```bash
   python run_dashboard.py
   ```

3. **Explore the Features**
   - Try different periods
   - Compare months
   - Export data
   - Analyze trends

4. **Customize**
   - Modify colors
   - Add custom KPIs
   - Create new visualizations

---

## 📞 Quick Reference

| Task | Command |
|------|---------|
| Add data (interactive) | `python add_monthly_data.py --interactive` |
| Show summary | `python add_monthly_data.py --summary` |
| Check missing | `python add_monthly_data.py --check-missing --year 2024` |
| Start dashboard | `python run_dashboard.py` |
| Parse HTML | `python -m scrapers.bddk_table_parser` |

---

## 🎉 You're Ready!

The new system is **much more professional** and **easier to use**:

✅ No more confusing files
✅ Beautiful professional dashboard
✅ Easy monthly updates
✅ No duplicate data
✅ Real BDDK table support
✅ Enterprise-grade features

**Start by adding your first month of data!**

```bash
python add_monthly_data.py --interactive
```
