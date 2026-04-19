"""
Financial Conditions Index (FCI) Engine
========================================
Calculates a BBVA-style Financial Conditions Index for Turkey.

Components:
- Real Exchange Rate (USD/TRY adjusted for inflation)
- Real Lending Rate (Commercial loan rate - CPI YoY)
- BIST100 Real Return (Stock returns - inflation)
- Policy Rate (CBRT policy rate as monetary stance indicator)

Methodology:
- Each component is standardized using rolling 36-month z-scores
- (+) Positive = Easing financial conditions
- (-) Negative = Tightening financial conditions
- Composite FCI = weighted average of components
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

# Try to import yfinance for BIST100 data
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("Warning: yfinance not installed. BIST100 data will be limited.")


class FCIEngine:
    """
    Financial Conditions Index calculation engine.

    Fetches data from EVDS API and external sources,
    calculates z-scores, and produces composite FCI.
    """

    # EVDS API configuration
    EVDS_BASE_URL = "https://evds2.tcmb.gov.tr/service/evds"

    # Series codes for FCI components
    EVDS_SERIES = {
        "usd_try": "TP.DK.USD.A",
        "cpi_index": "TP.FG.J0",
        "commercial_loan_rate": "TP.KTF17",
        "policy_rate": "TP.APIFON4",
        "bist100": "TP.HKFE01",
        "net_reserves": "TP.AB.N01",  # CBRT Net Reserves (proxy for capital flows)
    }

    # Component configuration
    COMPONENTS = {
        "real_exchange_rate": {
            "name": "Real Exchange Rate",
            "description": "USD/TRY adjusted for inflation (depreciation = easing)",
            "sign_flip": False,  # Depreciation is easing
            "weight": 1.0,
        },
        "real_lending_rate": {
            "name": "Real Lending Rate",
            "description": "Commercial loan rate minus CPI YoY",
            "sign_flip": True,  # Higher rate = tighter
            "weight": 1.0,
        },
        "bist100_real_return": {
            "name": "BIST100 Real Return",
            "description": "Stock market returns minus inflation",
            "sign_flip": False,  # Higher returns = easing
            "weight": 1.0,
        },
        "policy_rate": {
            "name": "Policy Rate",
            "description": "CBRT policy rate (monetary stance)",
            "sign_flip": True,  # Higher rate = tighter
            "weight": 1.0,
        },
        "capital_inflows": {
            "name": "Capital Inflows",
            "description": "CBRT net reserves change (proxy for capital flows)",
            "sign_flip": False,  # Higher inflows = easing
            "weight": 1.0,
        },
        "yield_slope": {
            "name": "Yield Slope",
            "description": "Commercial loan rate - Policy rate (credit spread proxy)",
            "sign_flip": False,  # Steeper slope = easing
            "weight": 1.0,
        },
    }

    def __init__(self, lookback_months: int = 36, start_date: str = "2019-01-01"):
        """
        Initialize FCI Engine.

        Args:
            lookback_months: Rolling window for z-score calculation
            start_date: Start date for data fetching (need extra history for z-scores)
        """
        self.lookback_months = lookback_months
        self.start_date = start_date
        self.api_key = os.getenv('EVDS_API_KEY')

        # Data cache
        self._cache: Dict[str, pd.DataFrame] = {}
        self._components_data: Optional[pd.DataFrame] = None
        self._fci_data: Optional[pd.DataFrame] = None

    def _fetch_evds_series(
        self,
        series_code: str,
        start_date: str,
        end_date: str,
        frequency: int = 5  # 5 = monthly
    ) -> pd.DataFrame:
        """
        Fetch a time series from EVDS API.

        Args:
            series_code: EVDS series code
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            frequency: Data frequency (5=monthly, 6=weekly, 7=daily)

        Returns:
            DataFrame with date index and value column
        """
        cache_key = f"{series_code}_{start_date}_{end_date}_{frequency}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Convert date format for EVDS API (DD-MM-YYYY)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        evds_start = start_dt.strftime("%d-%m-%Y")
        evds_end = end_dt.strftime("%d-%m-%Y")

        url = (
            f"{self.EVDS_BASE_URL}/series={series_code}"
            f"&startDate={evds_start}&endDate={evds_end}"
            f"&type=json&frequency={frequency}"
        )

        try:
            resp = requests.get(
                url,
                headers={"key": self.api_key},
                timeout=(3, 5)
            )
            resp.raise_for_status()
            data = resp.json()

            if "items" not in data or len(data["items"]) == 0:
                print(f"Warning: No data for series {series_code}")
                return pd.DataFrame()

            # Parse response
            items = data["items"]
            records = []

            for item in items:
                date_str = item.get("Tarih", "")
                date = None

                # Handle different date formats from EVDS
                try:
                    if "-" in date_str:
                        if len(date_str) == 7:  # YYYY-M format (e.g., "2024-1")
                            date = pd.to_datetime(date_str, format="%Y-%m")
                        elif len(date_str) == 10 and date_str[2] == "-":  # DD-MM-YYYY
                            date = pd.to_datetime(date_str, format="%d-%m-%Y")
                        elif "Q" in date_str:  # Quarterly (e.g., "2016-Q2")
                            # Skip quarterly data for now
                            continue
                        elif "S" in date_str:  # Semi-annual (e.g., "2016-S1")
                            # Skip semi-annual data
                            continue
                        else:
                            # Try generic parsing
                            date = pd.to_datetime(date_str)
                except Exception:
                    continue

                if date is None:
                    continue

                # Get value (column name varies by series)
                value_key = [k for k in item.keys() if k.startswith("TP_")][0] if any(k.startswith("TP_") for k in item.keys()) else None
                if value_key:
                    value = item.get(value_key)
                    if value is not None and value != "":
                        try:
                            records.append({"date": date, "value": float(value)})
                        except (ValueError, TypeError):
                            pass

            if not records:
                return pd.DataFrame()

            df = pd.DataFrame(records)
            df = df.set_index("date").sort_index()
            df = df[~df.index.duplicated(keep='last')]

            self._cache[cache_key] = df
            return df

        except Exception as e:
            print(f"Error fetching {series_code}: {e}")
            return pd.DataFrame()

    def _fetch_bist100_yfinance(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch BIST100 data from Yahoo Finance.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with monthly BIST100 values
        """
        if not YFINANCE_AVAILABLE:
            print("yfinance not available, cannot fetch BIST100")
            return pd.DataFrame()

        try:
            # XU100.IS is BIST100 on Yahoo Finance
            ticker = yf.Ticker("XU100.IS")
            hist = ticker.history(start=start_date, end=end_date, interval="1mo")

            if hist.empty:
                return pd.DataFrame()

            df = hist[["Close"]].rename(columns={"Close": "value"})
            df.index = pd.to_datetime(df.index).to_period("M").to_timestamp()
            df = df[~df.index.duplicated(keep='last')]

            return df

        except Exception as e:
            print(f"Error fetching BIST100 from yfinance: {e}")
            return pd.DataFrame()

    def _resample_to_monthly(self, df: pd.DataFrame, method: str = "last") -> pd.DataFrame:
        """Resample higher frequency data to monthly."""
        if df.empty:
            return df

        df = df.copy()
        df.index = pd.to_datetime(df.index)

        if method == "last":
            monthly = df.resample("M").last()
        elif method == "mean":
            monthly = df.resample("M").mean()
        else:
            monthly = df.resample("M").last()

        # Standardize index to month start for consistency
        monthly.index = monthly.index.to_period("M").to_timestamp()

        return monthly.dropna()

    def _calculate_yoy_change(self, series: pd.Series) -> pd.Series:
        """Calculate year-over-year percentage change."""
        return series.pct_change(periods=12) * 100

    def _calculate_mom_change(self, series: pd.Series) -> pd.Series:
        """Calculate month-over-month percentage change."""
        return series.pct_change(periods=1) * 100

    def _calculate_z_score(
        self,
        series: pd.Series,
        sign_flip: bool = False,
        window: int = None
    ) -> pd.Series:
        """
        Calculate rolling z-score.

        Args:
            series: Input time series
            sign_flip: If True, multiply by -1 (for components where higher = tighter)
            window: Rolling window size (default: self.lookback_months)

        Returns:
            Z-score series
        """
        if window is None:
            window = self.lookback_months

        rolling_mean = series.rolling(window=window, min_periods=12).mean()
        rolling_std = series.rolling(window=window, min_periods=12).std()

        z_score = (series - rolling_mean) / rolling_std

        if sign_flip:
            z_score = -z_score

        return z_score

    def calculate_real_exchange_rate(self) -> pd.DataFrame:
        """
        Calculate real exchange rate component.

        Method: USD/TRY indexed to base period, adjusted for relative CPI.
        Higher value = more depreciation = easing.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        # Fetch with extra history for z-score calculation
        hist_start = (datetime.strptime(self.start_date, "%Y-%m-%d") - timedelta(days=self.lookback_months * 35)).strftime("%Y-%m-%d")

        # Fetch USD/TRY
        usd_try = self._fetch_evds_series(
            self.EVDS_SERIES["usd_try"],
            hist_start, end_date,
            frequency=5  # monthly
        )

        # Fetch CPI
        cpi = self._fetch_evds_series(
            self.EVDS_SERIES["cpi_index"],
            hist_start, end_date,
            frequency=5
        )

        if usd_try.empty or cpi.empty:
            print("Warning: Missing data for real exchange rate calculation")
            return pd.DataFrame()

        # Align data
        df = pd.DataFrame({
            "usd_try": usd_try["value"],
            "cpi": cpi["value"]
        }).dropna()

        if df.empty:
            return pd.DataFrame()

        # Calculate real exchange rate (indexed)
        # RER = Nominal rate / (CPI / CPI_base)
        base_cpi = df["cpi"].iloc[0]
        df["cpi_indexed"] = df["cpi"] / base_cpi
        df["real_exchange_rate"] = df["usd_try"] / df["cpi_indexed"]

        # Calculate z-score (depreciation = easing, no flip)
        df["z_score"] = self._calculate_z_score(
            df["real_exchange_rate"],
            sign_flip=self.COMPONENTS["real_exchange_rate"]["sign_flip"]
        )

        return df[["real_exchange_rate", "z_score"]].dropna()

    def calculate_real_lending_rate(self) -> pd.DataFrame:
        """
        Calculate real lending rate component.

        Method: Commercial loan rate - CPI YoY
        Higher rate = tighter conditions (sign flip).
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        hist_start = (datetime.strptime(self.start_date, "%Y-%m-%d") - timedelta(days=self.lookback_months * 35)).strftime("%Y-%m-%d")

        # Fetch commercial loan rate (weekly data - use frequency=1 for weekly)
        loan_rate = self._fetch_evds_series(
            self.EVDS_SERIES["commercial_loan_rate"],
            hist_start, end_date,
            frequency=1  # returns weekly data with DD-MM-YYYY format
        )

        # Fetch CPI for YoY inflation
        cpi = self._fetch_evds_series(
            self.EVDS_SERIES["cpi_index"],
            hist_start, end_date,
            frequency=5
        )

        if loan_rate.empty or cpi.empty:
            print("Warning: Missing data for real lending rate calculation")
            return pd.DataFrame()

        # Resample loan rate to monthly
        loan_rate_monthly = self._resample_to_monthly(loan_rate, method="last")

        # Calculate CPI YoY
        cpi_yoy = self._calculate_yoy_change(cpi["value"])

        # Align data
        df = pd.DataFrame({
            "nominal_rate": loan_rate_monthly["value"],
            "cpi_yoy": cpi_yoy
        }).dropna()

        if df.empty:
            return pd.DataFrame()

        # Calculate real lending rate
        df["real_lending_rate"] = df["nominal_rate"] - df["cpi_yoy"]

        # Calculate z-score (higher = tighter, so flip)
        df["z_score"] = self._calculate_z_score(
            df["real_lending_rate"],
            sign_flip=self.COMPONENTS["real_lending_rate"]["sign_flip"]
        )

        return df[["real_lending_rate", "z_score"]].dropna()

    def calculate_bist100_real_return(self) -> pd.DataFrame:
        """
        Calculate BIST100 real return component.

        Method: BIST100 YoY return - CPI YoY
        Higher returns = easing conditions.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        hist_start = (datetime.strptime(self.start_date, "%Y-%m-%d") - timedelta(days=self.lookback_months * 35)).strftime("%Y-%m-%d")

        # Try EVDS first, then yfinance
        bist = self._fetch_evds_series(
            self.EVDS_SERIES["bist100"],
            hist_start, end_date,
            frequency=5
        )

        # Check if EVDS data is recent enough (within last 6 months)
        evds_is_stale = True
        if not bist.empty:
            latest_date = bist.index.max()
            months_old = (pd.Timestamp.now() - latest_date).days / 30
            evds_is_stale = months_old > 6

        if bist.empty or len(bist) < 24 or evds_is_stale:
            print(f"EVDS BIST100 data limited or stale, trying yfinance...")
            bist = self._fetch_bist100_yfinance(hist_start, end_date)

        # Fetch CPI
        cpi = self._fetch_evds_series(
            self.EVDS_SERIES["cpi_index"],
            hist_start, end_date,
            frequency=5
        )

        if bist.empty or cpi.empty:
            print("Warning: Missing data for BIST100 real return calculation")
            return pd.DataFrame()

        # Calculate returns
        bist_yoy = self._calculate_yoy_change(bist["value"])
        cpi_yoy = self._calculate_yoy_change(cpi["value"])

        # Align data
        df = pd.DataFrame({
            "bist100_return": bist_yoy,
            "cpi_yoy": cpi_yoy
        }).dropna()

        if df.empty:
            return pd.DataFrame()

        # Calculate real return
        df["bist100_real_return"] = df["bist100_return"] - df["cpi_yoy"]

        # Calculate z-score (higher = easing, no flip)
        df["z_score"] = self._calculate_z_score(
            df["bist100_real_return"],
            sign_flip=self.COMPONENTS["bist100_real_return"]["sign_flip"]
        )

        return df[["bist100_real_return", "z_score"]].dropna()

    def calculate_policy_rate(self) -> pd.DataFrame:
        """
        Calculate policy rate component.

        Method: CBRT policy rate level
        Higher rate = tighter conditions (sign flip).
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        hist_start = (datetime.strptime(self.start_date, "%Y-%m-%d") - timedelta(days=self.lookback_months * 35)).strftime("%Y-%m-%d")

        # Fetch policy rate (daily data - use frequency=1 for daily)
        policy_rate = self._fetch_evds_series(
            self.EVDS_SERIES["policy_rate"],
            hist_start, end_date,
            frequency=1  # returns daily data with DD-MM-YYYY format
        )

        if policy_rate.empty:
            print("Warning: Missing data for policy rate calculation")
            return pd.DataFrame()

        # Resample to monthly (use last value of month)
        df = self._resample_to_monthly(policy_rate, method="last")
        df.columns = ["policy_rate"]

        # Calculate z-score (higher = tighter, so flip)
        df["z_score"] = self._calculate_z_score(
            df["policy_rate"],
            sign_flip=self.COMPONENTS["policy_rate"]["sign_flip"]
        )

        return df[["policy_rate", "z_score"]].dropna()

    def calculate_yield_slope(self) -> pd.DataFrame:
        """
        Calculate yield slope component using credit spread proxy.

        Method: Commercial loan rate - Policy rate
        Higher spread (steeper slope) = easing conditions.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        hist_start = (datetime.strptime(self.start_date, "%Y-%m-%d") - timedelta(days=self.lookback_months * 35)).strftime("%Y-%m-%d")

        # Fetch commercial loan rate (weekly data)
        loan_rate = self._fetch_evds_series(
            self.EVDS_SERIES["commercial_loan_rate"],
            hist_start, end_date,
            frequency=1  # weekly
        )

        # Fetch policy rate (daily data)
        policy_rate = self._fetch_evds_series(
            self.EVDS_SERIES["policy_rate"],
            hist_start, end_date,
            frequency=1  # daily
        )

        if loan_rate.empty or policy_rate.empty:
            print("Warning: Missing data for yield slope calculation")
            return pd.DataFrame()

        # Resample both to monthly
        loan_monthly = self._resample_to_monthly(loan_rate, method="last")
        policy_monthly = self._resample_to_monthly(policy_rate, method="last")

        # Align data
        df = pd.DataFrame({
            "loan_rate": loan_monthly["value"],
            "policy_rate": policy_monthly["value"]
        }).dropna()

        if df.empty:
            return pd.DataFrame()

        # Calculate yield slope (spread)
        df["yield_slope"] = df["loan_rate"] - df["policy_rate"]

        # Calculate z-score (steeper = easing, no flip)
        df["z_score"] = self._calculate_z_score(
            df["yield_slope"],
            sign_flip=self.COMPONENTS["yield_slope"]["sign_flip"]
        )

        return df[["yield_slope", "z_score"]].dropna()

    def calculate_capital_inflows(self) -> pd.DataFrame:
        """
        Calculate capital inflows component using CBRT net reserves change.

        Method: Month-over-month change in net reserves (USD thousands)
        Higher inflows = easing conditions.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        hist_start = (datetime.strptime(self.start_date, "%Y-%m-%d") - timedelta(days=self.lookback_months * 35)).strftime("%Y-%m-%d")

        # Fetch net reserves (monthly data)
        reserves = self._fetch_evds_series(
            self.EVDS_SERIES["net_reserves"],
            hist_start, end_date,
            frequency=5  # monthly
        )

        if reserves.empty:
            print("Warning: Missing data for capital inflows calculation")
            return pd.DataFrame()

        df = reserves.copy()
        df.columns = ["net_reserves"]

        # Calculate month-over-month change (in billions USD for scale)
        df["reserves_change"] = df["net_reserves"].diff() / 1e6  # Convert to billions

        # Calculate z-score (higher inflows = easing, no flip)
        df["z_score"] = self._calculate_z_score(
            df["reserves_change"],
            sign_flip=self.COMPONENTS["capital_inflows"]["sign_flip"]
        )

        return df[["reserves_change", "z_score"]].dropna()

    def calculate_all_components(self) -> pd.DataFrame:
        """
        Calculate all FCI components and combine into single DataFrame.

        Returns:
            DataFrame with date index and columns for each component's z-score
        """
        print("Calculating FCI components...")

        components = {}

        # Real Exchange Rate
        print("  - Real Exchange Rate...")
        rer = self.calculate_real_exchange_rate()
        if not rer.empty:
            components["real_exchange_rate"] = rer["z_score"]

        # Real Lending Rate
        print("  - Real Lending Rate...")
        rlr = self.calculate_real_lending_rate()
        if not rlr.empty:
            components["real_lending_rate"] = rlr["z_score"]

        # BIST100 Real Return
        print("  - BIST100 Real Return...")
        bist = self.calculate_bist100_real_return()
        if not bist.empty:
            components["bist100_real_return"] = bist["z_score"]

        # Policy Rate
        print("  - Policy Rate...")
        pr = self.calculate_policy_rate()
        if not pr.empty:
            components["policy_rate"] = pr["z_score"]

        # Capital Inflows (Net Reserves Change)
        print("  - Capital Inflows...")
        ci = self.calculate_capital_inflows()
        if not ci.empty:
            components["capital_inflows"] = ci["z_score"]

        # Yield Slope (Credit Spread Proxy)
        print("  - Yield Slope...")
        ys = self.calculate_yield_slope()
        if not ys.empty:
            components["yield_slope"] = ys["z_score"]

        if not components:
            print("Error: No components calculated successfully")
            return pd.DataFrame()

        # Combine into single DataFrame
        df = pd.DataFrame(components)

        # Filter to start date
        start_dt = pd.to_datetime(self.start_date)
        df = df[df.index >= start_dt]

        self._components_data = df
        print(f"  Components calculated: {len(df)} periods, {len(components)} components")

        return df

    def calculate_fci(self, weights: str = "equal") -> pd.DataFrame:
        """
        Calculate composite Financial Conditions Index.

        Args:
            weights: Weighting scheme ("equal" or "custom")

        Returns:
            DataFrame with FCI values and component contributions
        """
        if self._components_data is None:
            self.calculate_all_components()

        if self._components_data is None or self._components_data.empty:
            return pd.DataFrame()

        df = self._components_data.copy()

        # Calculate weighted FCI
        n_components = len(df.columns)

        if weights == "equal":
            # Equal weights
            df["fci"] = df.mean(axis=1)
        else:
            # Use custom weights from COMPONENTS config
            weight_sum = sum(self.COMPONENTS[c]["weight"] for c in df.columns if c in self.COMPONENTS)
            for col in df.columns:
                if col in self.COMPONENTS:
                    w = self.COMPONENTS[col]["weight"] / weight_sum
                    df[col + "_contribution"] = df[col] * w

            contribution_cols = [c for c in df.columns if c.endswith("_contribution")]
            df["fci"] = df[contribution_cols].sum(axis=1)

        self._fci_data = df

        return df

    def get_latest_fci(self) -> dict:
        """Get latest FCI value and component breakdown."""
        if self._fci_data is None:
            self.calculate_fci()

        if self._fci_data is None or self._fci_data.empty:
            return {}

        latest = self._fci_data.iloc[-1]
        period = self._fci_data.index[-1]

        # Get previous period for change calculation
        if len(self._fci_data) > 1:
            prev = self._fci_data.iloc[-2]
            fci_change = latest["fci"] - prev["fci"]
        else:
            fci_change = 0

        result = {
            "period": period.strftime("%Y-%m"),
            "fci": round(latest["fci"], 2),
            "fci_change": round(fci_change, 2),
            "interpretation": self._interpret_fci(latest["fci"]),
            "components": {}
        }

        for comp in self.COMPONENTS:
            if comp in latest.index:
                result["components"][comp] = {
                    "name": self.COMPONENTS[comp]["name"],
                    "z_score": round(latest[comp], 2),
                    "contribution": "easing" if latest[comp] > 0 else "tightening"
                }

        return result

    def _interpret_fci(self, fci_value: float) -> str:
        """Interpret FCI value."""
        if fci_value > 1.5:
            return "Significantly Easing"
        elif fci_value > 0.5:
            return "Moderately Easing"
        elif fci_value > -0.5:
            return "Neutral"
        elif fci_value > -1.5:
            return "Moderately Tightening"
        else:
            return "Significantly Tightening"

    def get_fci_timeseries(self) -> pd.DataFrame:
        """Get FCI time series for charting."""
        if self._fci_data is None:
            self.calculate_fci()

        return self._fci_data

    def get_component_contributions(self) -> pd.DataFrame:
        """Get component contributions for stacked bar chart."""
        if self._fci_data is None:
            self.calculate_fci()

        if self._fci_data is None:
            return pd.DataFrame()

        # Return only z-score columns (not FCI or contributions)
        z_cols = [c for c in self._fci_data.columns if c in self.COMPONENTS]
        return self._fci_data[z_cols]


# Singleton instance
fci_engine = FCIEngine()


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("FINANCIAL CONDITIONS INDEX - TEST")
    print("=" * 60)

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    engine = FCIEngine(start_date="2019-12-01")

    # Calculate FCI
    fci_df = engine.calculate_fci()

    if not fci_df.empty:
        print("\n" + "=" * 60)
        print("FCI TIM SERIES (Last 12 months):")
        print("=" * 60)
        print(fci_df.tail(12).round(2))

        print("\n" + "=" * 60)
        print("LATEST FCI:")
        print("=" * 60)
        latest = engine.get_latest_fci()
        print(f"Period: {latest.get('period')}")
        print(f"FCI Value: {latest.get('fci')}")
        print(f"Change: {latest.get('fci_change')}")
        print(f"Interpretation: {latest.get('interpretation')}")
        print("\nComponents:")
        for comp, data in latest.get("components", {}).items():
            print(f"  {data['name']}: {data['z_score']} ({data['contribution']})")
    else:
        print("Failed to calculate FCI - check data availability")
