"""
Generate Metrics Documentation
==============================
Auto-generates docs/METRICS.md from metrics_catalog.py and metrics_engine.py.
Run this script whenever metrics are added or modified.

Usage:
    python scripts/generate_metrics_docs.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.analytics.metrics_catalog import (
    METRICS_CATALOG,
    CALCULATED_RATIOS,
    GROWTH_METRICS,
    BANK_TYPES,
    CURRENCY_TYPES,
    METRIC_CATEGORIES,
)


def generate_markdown():
    """Generate the full METRICS.md content"""

    today = datetime.now().strftime("%Y-%m-%d")

    doc = f"""# BDDK Metrics Documentation

This document describes all metrics calculated from BDDK (Banking Regulation and Supervision Agency) data. Each metric includes its definition, calculation formula, data source, and available dimensions.

**Last Updated:** {today}

> **Note:** This documentation is auto-generated from `metrics_catalog.py`. Run `python scripts/generate_metrics_docs.py` to regenerate.

---

## Table of Contents

1. [Data Sources](#data-sources)
2. [Dimensions](#dimensions)
3. [Base Metrics](#base-metrics)
4. [Calculated Ratios](#calculated-ratios)
5. [Growth Metrics](#growth-metrics)
6. [FX-Adjusted Growth Metrics](#fx-adjusted-growth-metrics)

---

## Data Sources

| Table | Description | Key Fields |
|-------|-------------|------------|
| `balance_sheet` | Monthly balance sheet items | `item_name`, `amount_tl`, `amount_fx`, `amount_total` |
| `loans` | Loan portfolio with NPL data | `total_tl`, `total_fx`, `npl_amount`, `customer_count` |
| `deposits` | Deposit breakdown by maturity | `demand`, `maturity_1m`, `maturity_1_3m`, etc. |
| `weekly_bulletin` | Weekly loans data | `tp_value`, `yp_value`, `total_value` |

---

## Dimensions

### Bank Types

| Code | Name (EN) | Name (TR) | Description |
|------|-----------|-----------|-------------|
"""

    # Add bank types
    for code, info in BANK_TYPES.items():
        doc += f"| `{code}` | {info['name']} | {info['name_tr']} | {info['description']} |\n"

    doc += """
**Primary Bank Types for Analysis:** `10001` (Sector), `10009` (Public), `10008` (Private)

### Currency Types

| Code | Name | Description |
|------|------|-------------|
"""

    # Add currency types
    for code, info in CURRENCY_TYPES.items():
        doc += f"| `{code}` | {info['name']} | {info['name_tr']} |\n"

    doc += """
---

## Base Metrics

"""

    # Group base metrics by category
    categories_with_metrics = {}
    for metric_id, metric in METRICS_CATALOG.items():
        cat = metric.get('category', 'other')
        if cat not in categories_with_metrics:
            categories_with_metrics[cat] = []
        categories_with_metrics[cat].append((metric_id, metric))

    for cat, metrics in categories_with_metrics.items():
        cat_info = METRIC_CATEGORIES.get(cat, {'name': cat.title(), 'name_tr': cat})
        doc += f"### {cat_info['name']} Metrics\n\n"

        for metric_id, metric in metrics:
            source = metric.get('source', {})
            doc += f"#### `{metric_id}`\n"
            doc += f"- **Name:** {metric['name']} / {metric['name_tr']}\n"
            doc += f"- **Description:** {metric['description']}\n"
            doc += f"- **Unit:** {metric.get('unit', 'N/A').replace('_', ' ').title()}\n"
            doc += f"- **Source:** `{source.get('table', 'N/A')}` table\n"
            doc += f"- **Filter:** `{source.get('filter', 'N/A')}`\n"

            value_cols = source.get('value_columns', {})
            if value_cols:
                agg = source.get('aggregation', 'SUM')
                cols_str = ', '.join([f"`{agg}({v})`" for v in value_cols.values() if isinstance(v, str)])
                doc += f"- **Calculation:** {cols_str}\n"

            if source.get('notes'):
                doc += f"- **Notes:** {source['notes']}\n"

            dims = metric.get('dimensions', [])
            doc += f"- **Dimensions:** {', '.join(dims)}\n"
            doc += "\n"

    doc += """---

## Calculated Ratios

"""

    for metric_id, metric in CALCULATED_RATIOS.items():
        formula = metric.get('formula', {})
        doc += f"### `{metric_id}`\n"
        doc += f"- **Name:** {metric['name']} / {metric['name_tr']}\n"
        doc += f"- **Description:** {metric['description']}\n"
        doc += f"- **Category:** {metric.get('category', 'N/A').replace('_', ' ').title()}\n"
        doc += f"- **Unit:** {metric.get('unit', 'N/A').replace('_', ' ').title()}\n"
        doc += f"- **Formula:**\n"
        doc += f"  ```\n"
        doc += f"  {metric['name']} = ({formula.get('numerator', 'N/A')} / {formula.get('denominator', 'N/A')}) × {formula.get('multiply_by', 1)}\n"
        doc += f"  ```\n"
        dims = metric.get('dimensions', [])
        doc += f"- **Dimensions:** {', '.join(dims)}\n"
        doc += "\n"

    doc += """---

## Growth Metrics

### Year-over-Year (YoY) Growth

**Formula:**
```
YoY Growth = ((Current Month Value - Same Month Last Year Value) / Same Month Last Year Value) × 100
```

### Month-over-Month (MoM) Growth

**Formula:**
```
MoM Growth = ((Current Month Value - Previous Month Value) / Previous Month Value) × 100
```

### Available Growth Metrics

| Metric ID | Name | Base Metric | Calculation |
|-----------|------|-------------|-------------|
"""

    for metric_id, metric in GROWTH_METRICS.items():
        doc += f"| `{metric_id}` | {metric['name']} | `{metric['base_metric']}` | {metric['calculation'].upper()} |\n"

    doc += """
---

## FX-Adjusted Growth Metrics

FX-adjusted growth removes exchange rate effects to show "real" credit growth. This is important because nominal TL growth can be inflated by TRY depreciation when FX loans are converted to TL.

### Methodology (BBVA Style)

1. **Separate TL and FX loans** from balance sheet data
2. **Convert FX loans to USD** using TCMB (Central Bank) exchange rates
3. **Calculate growth separately:**
   - TL loans: growth in TL terms
   - FX loans: growth in USD terms (removes exchange rate effect)
4. **Combine for total FX-adjusted growth**

### Exchange Rate Source

- **API:** EVDS (Electronic Data Delivery System) from TCMB
- **Series:** `TP.DK.USD.A` (USD buying rate)
- **Endpoint:** `https://evds2.tcmb.gov.tr/service/evds`
- **Authentication:** Requires `EVDS_API_KEY` in environment variables

### `credit_growth_fx_adjusted_yoy`
- **Name:** FX-Adjusted Credit Growth (YoY)
- **Description:** Year-over-year credit growth adjusted for exchange rate effects
- **Unit:** Percentage (%)
- **Formula:**
  ```
  Let:
    TL_t = TL loans at time t
    FX_t = FX loans at time t (in TL)
    USD_TRY_t = USD/TRY exchange rate at time t

  FX loans in USD:
    FX_USD_t = FX_t / USD_TRY_t

  Growth components:
    TL Growth = (TL_t - TL_{t-12}) / TL_{t-12} × 100
    FX Growth (USD) = (FX_USD_t - FX_USD_{t-12}) / FX_USD_{t-12} × 100

  Weighted FX-Adjusted Growth:
    = (TL_{t-12} × TL_Growth + FX_{t-12} × FX_Growth) / (TL_{t-12} + FX_{t-12})
  ```
- **Dimensions:** time, bank_type

### `credit_growth_fx_adjusted_3m_ann`
- **Name:** FX-Adjusted Credit Growth (3M Annualized)
- **Description:** 3-month credit growth, annualized, adjusted for FX effects
- **Unit:** Percentage (%)
- **Formula:**
  ```
  3-Month Simple Growth:
    growth_3m = (Value_t - Value_{t-3}) / Value_{t-3}

  Annualized:
    growth_ann = ((1 + growth_3m) ^ 4 - 1) × 100

  Applied separately to TL and FX (in USD), then combined.
  ```
- **Dimensions:** time, bank_type

---

## Code References

- **Metrics Catalog:** `src/analytics/metrics_catalog.py`
- **Metrics Engine:** `src/analytics/metrics_engine.py`
- **FX-Adjusted Methods:**
  - `MetricsEngine._fetch_usd_try_rates()` - Fetches USD/TRY from EVDS API
  - `MetricsEngine.get_loans_with_fx_breakdown()` - Gets TL/FX loan data
  - `MetricsEngine.calculate_fx_adjusted_growth()` - Main calculation
  - `MetricsEngine.get_credit_growth_summary()` - Dashboard summary

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-01-24 | Initial documentation created | Claude |
| 2026-01-24 | Added FX-adjusted growth metrics using EVDS API | Claude |
"""

    return doc


def main():
    """Generate and save the metrics documentation"""
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    output_path = docs_dir / "METRICS.md"

    print("Generating metrics documentation...")
    content = generate_markdown()

    output_path.write_text(content, encoding='utf-8')
    print(f"Documentation saved to: {output_path}")

    # Print summary
    print(f"\nSummary:")
    print(f"  - Base metrics: {len(METRICS_CATALOG)}")
    print(f"  - Calculated ratios: {len(CALCULATED_RATIOS)}")
    print(f"  - Growth metrics: {len(GROWTH_METRICS)}")
    print(f"  - Total: {len(METRICS_CATALOG) + len(CALCULATED_RATIOS) + len(GROWTH_METRICS)}")


if __name__ == "__main__":
    main()
