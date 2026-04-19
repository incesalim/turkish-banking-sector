"""
Statistical Analysis and Forecasting Module

Provides time series forecasting, statistical testing, and predictive analytics.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import scipy.stats as stats
from prophet import Prophet
from pmdarima import auto_arima
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
import sys
from loguru import logger
import warnings
warnings.filterwarnings('ignore')

sys.path.append(str(Path(__file__).parent.parent))
from config import *


class BankingForecaster:
    """Time series forecasting and statistical analysis for banking data"""

    def __init__(self):
        """Initialize forecaster"""
        logger.add(
            LOGS_DIR / "forecaster_{time}.log",
            rotation="1 day",
            level="INFO"
        )
        self.models = {}
        self.forecasts = {}

    def prepare_time_series(self, df, date_column='date', value_column=None):
        """
        Prepare time series data

        Args:
            df: DataFrame
            date_column: Date column name
            value_column: Value column to forecast

        Returns:
            Prepared time series
        """
        ts_df = df.copy()

        # Convert to datetime
        ts_df[date_column] = pd.to_datetime(ts_df[date_column])
        ts_df = ts_df.sort_values(date_column)
        ts_df = ts_df.set_index(date_column)

        # Handle missing values
        ts_df = ts_df.fillna(method='ffill').fillna(method='bfill')

        # Ensure frequency
        if value_column:
            ts_df = ts_df[value_column].resample('M').last()

        logger.info(f"Prepared time series with {len(ts_df)} periods")
        return ts_df

    def decompose_series(self, series, model='additive', period=12):
        """
        Decompose time series into trend, seasonal, and residual components

        Args:
            series: Time series
            model: 'additive' or 'multiplicative'
            period: Seasonal period

        Returns:
            Decomposition result
        """
        try:
            decomposition = seasonal_decompose(
                series,
                model=model,
                period=period,
                extrapolate_trend='freq'
            )

            logger.info("Time series decomposition completed")
            return decomposition

        except Exception as e:
            logger.error(f"Error in decomposition: {str(e)}")
            return None

    def test_stationarity(self, series):
        """
        Test if series is stationary using ADF test

        Args:
            series: Time series

        Returns:
            Dictionary with test results
        """
        from statsmodels.tsa.stattools import adfuller

        result = adfuller(series.dropna())

        test_results = {
            'adf_statistic': result[0],
            'p_value': result[1],
            'critical_values': result[4],
            'is_stationary': result[1] < 0.05
        }

        logger.info(f"Stationarity test - p-value: {result[1]:.4f}")
        return test_results

    def auto_arima_forecast(self, series, periods=12):
        """
        Automatic ARIMA model selection and forecasting

        Args:
            series: Time series
            periods: Number of periods to forecast

        Returns:
            Forecast results
        """
        try:
            # Fit auto ARIMA
            model = auto_arima(
                series,
                seasonal=True,
                m=12,
                suppress_warnings=True,
                stepwise=True,
                trace=False
            )

            # Forecast
            forecast = model.predict(n_periods=periods)
            forecast_index = pd.date_range(
                start=series.index[-1] + pd.DateOffset(months=1),
                periods=periods,
                freq='M'
            )

            # Confidence intervals
            forecast_df = pd.DataFrame({
                'forecast': forecast
            }, index=forecast_index)

            self.models['auto_arima'] = model
            self.forecasts['auto_arima'] = forecast_df

            logger.info(f"Auto ARIMA forecast completed for {periods} periods")
            return forecast_df

        except Exception as e:
            logger.error(f"Error in auto ARIMA: {str(e)}")
            return None

    def exponential_smoothing_forecast(self, series, periods=12, seasonal_periods=12):
        """
        Exponential smoothing forecast (Holt-Winters)

        Args:
            series: Time series
            periods: Forecast periods
            seasonal_periods: Seasonal period length

        Returns:
            Forecast results
        """
        try:
            model = ExponentialSmoothing(
                series,
                seasonal_periods=seasonal_periods,
                trend='add',
                seasonal='add'
            )
            fitted_model = model.fit()

            # Forecast
            forecast = fitted_model.forecast(periods)
            forecast_index = pd.date_range(
                start=series.index[-1] + pd.DateOffset(months=1),
                periods=periods,
                freq='M'
            )

            forecast_df = pd.DataFrame({
                'forecast': forecast
            }, index=forecast_index)

            self.models['exp_smoothing'] = fitted_model
            self.forecasts['exp_smoothing'] = forecast_df

            logger.info(f"Exponential smoothing forecast completed")
            return forecast_df

        except Exception as e:
            logger.error(f"Error in exponential smoothing: {str(e)}")
            return None

    def prophet_forecast(self, df, date_column='date', value_column='value', periods=12):
        """
        Facebook Prophet forecast

        Args:
            df: DataFrame with date and value columns
            date_column: Date column name
            value_column: Value column name
            periods: Forecast periods

        Returns:
            Forecast DataFrame
        """
        try:
            # Prepare data for Prophet
            prophet_df = df[[date_column, value_column]].copy()
            prophet_df.columns = ['ds', 'y']

            # Initialize and fit model
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False
            )
            model.fit(prophet_df)

            # Create future dataframe
            future = model.make_future_dataframe(periods=periods, freq='M')

            # Forecast
            forecast = model.predict(future)

            self.models['prophet'] = model
            self.forecasts['prophet'] = forecast

            logger.info(f"Prophet forecast completed for {periods} periods")
            return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]

        except Exception as e:
            logger.error(f"Error in Prophet forecast: {str(e)}")
            return None

    def random_forest_forecast(self, df, target_column, feature_columns, periods=12):
        """
        Random Forest forecast with lag features

        Args:
            df: DataFrame with features
            target_column: Target variable
            feature_columns: Feature columns
            periods: Forecast periods

        Returns:
            Forecast results
        """
        try:
            # Prepare data
            X = df[feature_columns]
            y = df[target_column]

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, shuffle=False
            )

            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            # Forecast (simplified - would need lag feature generation)
            last_features = X.iloc[-1:].values
            forecasts = []

            for _ in range(periods):
                pred = model.predict(last_features)[0]
                forecasts.append(pred)
                # Update features for next prediction (simplified)
                last_features = last_features  # Would update with new prediction

            forecast_index = pd.date_range(
                start=df.index[-1] + pd.DateOffset(months=1),
                periods=periods,
                freq='M'
            )

            forecast_df = pd.DataFrame({
                'forecast': forecasts
            }, index=forecast_index)

            evaluation = {
                'mse': mse,
                'mae': mae,
                'r2': r2,
                'feature_importance': dict(zip(feature_columns, model.feature_importances_))
            }

            self.models['random_forest'] = model
            self.forecasts['random_forest'] = forecast_df

            logger.info(f"Random Forest forecast - R2: {r2:.4f}, MAE: {mae:.4f}")
            return forecast_df, evaluation

        except Exception as e:
            logger.error(f"Error in Random Forest forecast: {str(e)}")
            return None, None

    def ensemble_forecast(self, series, periods=12):
        """
        Ensemble forecast combining multiple methods

        Args:
            series: Time series
            periods: Forecast periods

        Returns:
            Ensemble forecast
        """
        forecasts = []

        # Get forecasts from different models
        try:
            arima_fc = self.auto_arima_forecast(series, periods)
            if arima_fc is not None:
                forecasts.append(arima_fc['forecast'].values)
        except:
            pass

        try:
            es_fc = self.exponential_smoothing_forecast(series, periods)
            if es_fc is not None:
                forecasts.append(es_fc['forecast'].values)
        except:
            pass

        if len(forecasts) > 0:
            # Average forecasts
            ensemble = np.mean(forecasts, axis=0)

            forecast_index = pd.date_range(
                start=series.index[-1] + pd.DateOffset(months=1),
                periods=periods,
                freq='M'
            )

            forecast_df = pd.DataFrame({
                'forecast': ensemble
            }, index=forecast_index)

            self.forecasts['ensemble'] = forecast_df

            logger.info(f"Ensemble forecast created from {len(forecasts)} models")
            return forecast_df
        else:
            logger.warning("No forecasts available for ensemble")
            return None

    def calculate_forecast_accuracy(self, actual, predicted):
        """
        Calculate forecast accuracy metrics

        Args:
            actual: Actual values
            predicted: Predicted values

        Returns:
            Dictionary of accuracy metrics
        """
        mse = mean_squared_error(actual, predicted)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(actual, predicted)
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100

        metrics = {
            'mse': mse,
            'rmse': rmse,
            'mae': mae,
            'mape': mape,
            'r2': r2_score(actual, predicted)
        }

        return metrics

    def scenario_analysis(self, base_forecast, scenarios):
        """
        Perform scenario analysis on forecasts

        Args:
            base_forecast: Base forecast
            scenarios: Dictionary of scenarios with adjustment factors

        Returns:
            Dictionary of scenario forecasts
        """
        scenario_forecasts = {'base': base_forecast}

        for scenario_name, adjustment in scenarios.items():
            scenario_fc = base_forecast.copy()
            scenario_fc['forecast'] = scenario_fc['forecast'] * (1 + adjustment / 100)
            scenario_forecasts[scenario_name] = scenario_fc

        logger.info(f"Scenario analysis completed for {len(scenarios)} scenarios")
        return scenario_forecasts

    def detect_anomalies(self, series, method='zscore', threshold=3):
        """
        Detect anomalies in time series

        Args:
            series: Time series
            method: 'zscore' or 'iqr'
            threshold: Threshold for anomaly detection

        Returns:
            Boolean series indicating anomalies
        """
        if method == 'zscore':
            z_scores = np.abs(stats.zscore(series.dropna()))
            anomalies = z_scores > threshold

        elif method == 'iqr':
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - threshold * IQR
            upper_bound = Q3 + threshold * IQR
            anomalies = ~series.between(lower_bound, upper_bound)

        else:
            raise ValueError(f"Unknown method: {method}")

        anomaly_count = anomalies.sum()
        logger.info(f"Detected {anomaly_count} anomalies using {method} method")

        return anomalies

    def backtesting(self, series, forecast_func, train_size=0.8, step_size=1):
        """
        Backtest forecast model

        Args:
            series: Time series
            forecast_func: Forecasting function
            train_size: Training data proportion
            step_size: Step size for rolling window

        Returns:
            Backtesting results
        """
        split_point = int(len(series) * train_size)
        errors = []

        for i in range(split_point, len(series), step_size):
            train = series[:i]
            actual = series[i]

            try:
                forecast = forecast_func(train, periods=1)
                if forecast is not None:
                    predicted = forecast['forecast'].iloc[0]
                    error = actual - predicted
                    errors.append(error)
            except:
                continue

        if errors:
            mae = np.mean(np.abs(errors))
            rmse = np.sqrt(np.mean(np.array(errors)**2))

            results = {
                'mae': mae,
                'rmse': rmse,
                'errors': errors
            }

            logger.info(f"Backtesting completed - MAE: {mae:.4f}, RMSE: {rmse:.4f}")
            return results
        else:
            logger.warning("Backtesting failed - no valid forecasts")
            return None

    def plot_forecast(self, historical, forecast, title="Forecast", save_path=None):
        """
        Plot historical data with forecast

        Args:
            historical: Historical series
            forecast: Forecast DataFrame
            title: Plot title
            save_path: Path to save plot

        Returns:
            Figure object
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot historical
        ax.plot(historical.index, historical.values, label='Historical', linewidth=2)

        # Plot forecast
        ax.plot(forecast.index, forecast['forecast'], label='Forecast',
                linewidth=2, linestyle='--', color='red')

        # Confidence intervals if available
        if 'lower' in forecast.columns and 'upper' in forecast.columns:
            ax.fill_between(forecast.index, forecast['lower'], forecast['upper'],
                           alpha=0.3, color='red', label='Confidence Interval')

        ax.set_title(title, fontsize=14)
        ax.set_xlabel('Date')
        ax.set_ylabel('Value')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Forecast plot saved to {save_path}")

        return fig


def main():
    """Example usage"""
    forecaster = BankingForecaster()

    # Generate sample data
    dates = pd.date_range('2020-01-01', periods=36, freq='M')
    trend = np.linspace(100, 150, 36)
    seasonal = 10 * np.sin(np.arange(36) * 2 * np.pi / 12)
    noise = np.random.randn(36) * 5
    values = trend + seasonal + noise

    series = pd.Series(values, index=dates)

    # Test forecasting
    print("Testing Auto ARIMA...")
    arima_forecast = forecaster.auto_arima_forecast(series, periods=12)
    print(arima_forecast)

    print("\nTesting Exponential Smoothing...")
    es_forecast = forecaster.exponential_smoothing_forecast(series, periods=12)
    print(es_forecast)

    print("\nTesting Ensemble...")
    ensemble_forecast = forecaster.ensemble_forecast(series, periods=12)
    print(ensemble_forecast)


if __name__ == "__main__":
    main()
