# Project State — verified 2026-04-18

> **See also:** [METRICS.md](METRICS.md) for the metric catalogue — every
> number on the dashboard is traceable to a BDDK table / EVDS code / formula
> there.



Snapshot of what **actually exists** in the repo right now. Earlier docs in this folder (`START_HERE.md`, `SESSION_STATUS.md`, `UPGRADE_SUMMARY.md`, `NEXT_STEP.txt`, etc.) are from Dec 2025 and reference files that were refactored away — trust this document over them.

---

## Entry point
- **`run.py`** — interactive CLI: download monthly data, or launch dashboard on port 8050.
- Old entry scripts (`demo.py`, `run_dashboard.py`, `add_monthly_data.py`, `download_all_data.py`) **no longer exist**.

## Source layout (`src/`)

| Path | Purpose |
|---|---|
| `config.py` | Paths, BDDK URLs, bank-type config, EVDS series codes. Loads `.env`. |
| `scrapers/monthly_scraper.py` | Main monthly bulletin scraper. |
| `scrapers/weekly_scraper.py` | Weekly bulletin scraper. |
| `scrapers/bddk_table_parser.py` | HTML table parser (Turkish number formats, hierarchy). |
| `database/db_manager.py` | SQLite access layer. |
| `database/weekly_loader.py` | Weekly data loader. |
| `analytics/metrics_catalog.py` | Metric definitions + `BANK_TYPES` taxonomy. |
| `analytics/metrics_engine.py` | Computes metrics from raw tables. |
| `analytics/fci_engine.py` | BBVA-style Financial Conditions Index. |
| `analytics/data_store.py` | In-memory cache for the dashboard. |
| `dashboard/app.py` | Dash + Bootstrap app. |
| `dashboard/fci_tab.py` | FCI visualization tab. |
| `utils/data_processor.py`, `utils/monthly_data_manager.py` | Data prep helpers. |

## Database — `data/bddk_data.db` (~51 MB)

**Live tables (used):**

| Table | Rows | Coverage |
|---|---|---|
| `balance_sheet` | 15,500 | 2024-01 → 2025-12 |
| `income_statement` | 13,250 | 2024-01 → 2025-12 |
| `loans` | 35,500 | 2024-01 → 2025-12 |
| `deposits` | 12,500 | 2024-01 → 2025-12 |
| `financial_ratios` | 8,050 | 2024-01 → 2025-12 |
| `other_data` | 125,310 | 2024-01 → 2025-12 |
| `raw_api_responses` | 4,170 | 2024-01 → 2025-12 (raw JSON cache) |
| `weekly_bulletin` | 682 | 2025–2026 |
| `download_log` | 4,228 | audit trail |
| `bank_types`, `table_definitions` | reference data |

**Dead tables (leftover, safe to drop):**
- `monthly_data` (0 rows), `bank_metrics` (0 rows)
- `bddk_monthly_test` (1 row), `bddk_monthly_demo_data` (144 demo rows)

## Bank-type taxonomy (`metrics_catalog.py:31`)
Sector (10001) = Private (10003) + State (10004) + Foreign (10005) + Participation (10006) + Dev&Inv (10007).
Codes 10008–10010 are ownership-only cross-cuts across all business models.
Currency suffixes: `_tl`, `_fx`, `_total`.

## Data flow
1. `run.py` → `BDDKMonthlyScraper` hits `bddk.org.tr/BultenAylik` via Selenium.
2. Raw JSON cached in `raw_api_responses`, then parsed into typed tables.
3. Dashboard reads typed tables through `data_store` on startup.
4. FCI tab additionally pulls TCMB macro series via EVDS API (requires `EVDS_API_KEY` in `.env`).

## Known issues / things to flag before touching
- `data/raw/` and `data/processed/` are empty — everything is in the DB.
- `config.START_YEAR = 2004` but DB only has 2024–2025. Historical backfill never ran.
- `run.py:67` launches Dash with `debug=True, host='0.0.0.0'` — fine for local, not for exposed environments.
- Stray `nul` file in project root (Windows redirect accident).
- `archive/` contains pre-refactor code (`cli`, `dashboards`, `scrapers`, `scripts`, `tests`, `unused`) — preserved, not imported.
- `docs/` has ~18 older planning docs; treat this file as the source of truth for current structure.

## For the next session
Before editing anything, verify against the current code — the older docs in this folder describe a system that was refactored away.
