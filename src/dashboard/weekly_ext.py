"""Query helpers for the weekly_series table + BBVA-style growth transforms."""

from __future__ import annotations
from pathlib import Path
import sqlite3
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bddk_data.db"


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(sql, con, params=params)
    if not df.empty and "period_date" in df.columns:
        df["period_date"] = pd.to_datetime(df["period_date"])
    return df


def get_series(
    item_id: str,
    bank_type_code: str = "10001",
    currency: str = "TOTAL",
) -> pd.DataFrame:
    """Return DataFrame[period_date, value] for one series."""
    q = """
    SELECT period_date, value, item_name
    FROM weekly_series
    WHERE item_id = ? AND bank_type_code = ? AND currency = ?
    ORDER BY period_date
    """
    return _query(q, (item_id, bank_type_code, currency))


def get_series_multi_bank(
    item_id: str,
    bank_type_codes: list[str],
    currency: str = "TOTAL",
) -> pd.DataFrame:
    """Long-format: [period_date, bank_type_code, value]."""
    placeholders = ",".join("?" * len(bank_type_codes))
    q = f"""
    SELECT period_date, bank_type_code, value, item_name
    FROM weekly_series
    WHERE item_id = ?
      AND bank_type_code IN ({placeholders})
      AND currency = ?
    ORDER BY bank_type_code, period_date
    """
    return _query(q, (item_id, *bank_type_codes, currency))


# ---------------------------------------------------------------------------
# Growth transforms — BBVA conventions
# ---------------------------------------------------------------------------
def growth_annualized(df: pd.DataFrame, weeks: int) -> pd.DataFrame:
    """Compound annualized N-week growth.

    Formula: `(value_t / value_{t-N})^(52/N) - 1`, percent.
    For per-bank long-format, group by bank_type_code first.
    """
    if df is None or df.empty:
        return df
    df = df.sort_values(["bank_type_code", "period_date"] if "bank_type_code" in df.columns else "period_date").copy()
    exp = 52.0 / weeks

    def _apply(g):
        g = g.copy()
        prev = g["value"].shift(weeks)
        # Guard against zero / negative prev values
        ratio = g["value"] / prev
        ratio = ratio.where((prev > 0) & (g["value"] > 0))
        g["value"] = (ratio ** exp - 1) * 100
        return g

    if "bank_type_code" in df.columns:
        return df.groupby("bank_type_code", group_keys=False).apply(_apply).dropna(subset=["value"])
    return _apply(df).dropna(subset=["value"])


def growth_4w(df: pd.DataFrame) -> pd.DataFrame:
    """Compound annualized 4-week growth, BBVA-style nowcast."""
    return growth_annualized(df, 4)


def growth_13w(df: pd.DataFrame) -> pd.DataFrame:
    """Compound annualized 13-week growth, BBVA-style medium-term trend."""
    return growth_annualized(df, 13)


def growth_yoy(df: pd.DataFrame) -> pd.DataFrame:
    """52-week year-over-year percent change (not annualized — already yearly)."""
    if df is None or df.empty:
        return df
    df = df.sort_values(["bank_type_code", "period_date"] if "bank_type_code" in df.columns else "period_date").copy()

    def _apply(g):
        g = g.copy()
        prev = g["value"].shift(52)
        ratio = g["value"] / prev
        ratio = ratio.where((prev > 0) & (g["value"] > 0))
        g["value"] = (ratio - 1) * 100
        return g

    if "bank_type_code" in df.columns:
        return df.groupby("bank_type_code", group_keys=False).apply(_apply).dropna(subset=["value"])
    return _apply(df).dropna(subset=["value"])


# ---------------------------------------------------------------------------
# Convenience: adapt weekly df to shape that dashboard charts.trend_chart expects
# ---------------------------------------------------------------------------
def to_trend_format(df: pd.DataFrame) -> pd.DataFrame:
    """Rename period_date -> period and add bank_type (text name) for chart helpers."""
    if df is None or df.empty:
        return df
    from src.analytics.metrics_catalog import BANK_TYPES
    out = df.rename(columns={"period_date": "period"}).copy()
    if "bank_type_code" in out.columns:
        out["bank_type"] = out["bank_type_code"].map(
            lambda c: BANK_TYPES.get(c, {}).get("name", c)
        )
    return out
