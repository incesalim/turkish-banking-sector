"""
Comprehensive Financial Analysis Module for Turkish Banking Sector

Provides advanced financial analysis, benchmarking, and insights.
"""

import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
from pathlib import Path
import sys
from loguru import logger

sys.path.append(str(Path(__file__).parent.parent))
from config import *


class BankingFinancialAnalyzer:
    """Comprehensive financial analysis for Turkish banking sector"""

    def __init__(self):
        """Initialize analyzer"""
        logger.add(
            LOGS_DIR / "financial_analyzer_{time}.log",
            rotation="1 day",
            level="INFO"
        )

    def asset_quality_analysis(self, df):
        """
        Comprehensive asset quality analysis

        Args:
            df: DataFrame with banking data

        Returns:
            Dictionary with asset quality metrics and insights
        """
        analysis = {
            'metrics': {},
            'trends': {},
            'alerts': []
        }

        try:
            # NPL Ratio Analysis
            if 'npl_ratio' in df.columns:
                analysis['metrics']['current_npl_ratio'] = df['npl_ratio'].iloc[-1]
                analysis['metrics']['avg_npl_ratio'] = df['npl_ratio'].mean()
                analysis['metrics']['min_npl_ratio'] = df['npl_ratio'].min()
                analysis['metrics']['max_npl_ratio'] = df['npl_ratio'].max()

                # Trend analysis
                npl_trend = self._calculate_trend(df['npl_ratio'])
                analysis['trends']['npl_trend'] = npl_trend

                # Alert if NPL ratio is deteriorating
                if npl_trend > 10:  # More than 10% increase
                    analysis['alerts'].append(f"NPL ratio increasing by {npl_trend:.1f}%")

            # Provision Coverage Analysis
            if 'provision_coverage' in df.columns:
                analysis['metrics']['current_provision_coverage'] = df['provision_coverage'].iloc[-1]
                analysis['metrics']['avg_provision_coverage'] = df['provision_coverage'].mean()

                # Alert if coverage is low
                if df['provision_coverage'].iloc[-1] < 70:
                    analysis['alerts'].append("Provision coverage below 70%")

            # Loan Growth Analysis
            if 'total_loans' in df.columns:
                loan_growth = self._calculate_yoy_growth(df, 'total_loans')
                analysis['metrics']['loan_growth_yoy'] = loan_growth

                # Alert if loan growth is too high (credit bubble risk)
                if loan_growth > 30:
                    analysis['alerts'].append(f"High loan growth: {loan_growth:.1f}% YoY")

            logger.info("Completed asset quality analysis")

        except Exception as e:
            logger.error(f"Error in asset quality analysis: {str(e)}")

        return analysis

    def profitability_analysis(self, df):
        """
        Comprehensive profitability analysis

        Args:
            df: DataFrame with banking data

        Returns:
            Dictionary with profitability metrics
        """
        analysis = {
            'metrics': {},
            'trends': {},
            'efficiency': {},
            'alerts': []
        }

        try:
            # ROA Analysis
            if 'roa' in df.columns:
                analysis['metrics']['current_roa'] = df['roa'].iloc[-1]
                analysis['metrics']['avg_roa'] = df['roa'].mean()
                analysis['trends']['roa_trend'] = self._calculate_trend(df['roa'])

                if df['roa'].iloc[-1] < 0.5:
                    analysis['alerts'].append(f"Low ROA: {df['roa'].iloc[-1]:.2f}%")

            # ROE Analysis
            if 'roe' in df.columns:
                analysis['metrics']['current_roe'] = df['roe'].iloc[-1]
                analysis['metrics']['avg_roe'] = df['roe'].mean()
                analysis['trends']['roe_trend'] = self._calculate_trend(df['roe'])

                if df['roe'].iloc[-1] < 5:
                    analysis['alerts'].append(f"Low ROE: {df['roe'].iloc[-1]:.2f}%")

            # NIM Analysis
            if 'nim' in df.columns:
                analysis['metrics']['current_nim'] = df['nim'].iloc[-1]
                analysis['metrics']['avg_nim'] = df['nim'].mean()
                analysis['trends']['nim_trend'] = self._calculate_trend(df['nim'])

                # Margin compression warning
                if analysis['trends']['nim_trend'] < -5:
                    analysis['alerts'].append("Net interest margin compressing")

            # Cost-to-Income Analysis
            if 'cost_income_ratio' in df.columns:
                analysis['efficiency']['current_ci_ratio'] = df['cost_income_ratio'].iloc[-1]
                analysis['efficiency']['avg_ci_ratio'] = df['cost_income_ratio'].mean()

                if df['cost_income_ratio'].iloc[-1] > 60:
                    analysis['alerts'].append(f"High cost/income ratio: {df['cost_income_ratio'].iloc[-1]:.1f}%")

            # Profit Growth
            if 'net_profit' in df.columns:
                profit_growth = self._calculate_yoy_growth(df, 'net_profit')
                analysis['metrics']['profit_growth_yoy'] = profit_growth

            logger.info("Completed profitability analysis")

        except Exception as e:
            logger.error(f"Error in profitability analysis: {str(e)}")

        return analysis

    def liquidity_analysis(self, df):
        """
        Comprehensive liquidity analysis

        Args:
            df: DataFrame with banking data

        Returns:
            Dictionary with liquidity metrics
        """
        analysis = {
            'metrics': {},
            'trends': {},
            'alerts': []
        }

        try:
            # Loan-to-Deposit Ratio
            if 'loan_deposit_ratio' in df.columns:
                analysis['metrics']['current_ld_ratio'] = df['loan_deposit_ratio'].iloc[-1]
                analysis['metrics']['avg_ld_ratio'] = df['loan_deposit_ratio'].mean()
                analysis['trends']['ld_trend'] = self._calculate_trend(df['loan_deposit_ratio'])

                # High L/D ratio warning
                if df['loan_deposit_ratio'].iloc[-1] > 120:
                    analysis['alerts'].append(f"High loan/deposit ratio: {df['loan_deposit_ratio'].iloc[-1]:.1f}%")

            # Liquid Assets Ratio
            if 'liquid_assets_ratio' in df.columns:
                analysis['metrics']['current_liquid_ratio'] = df['liquid_assets_ratio'].iloc[-1]
                analysis['metrics']['avg_liquid_ratio'] = df['liquid_assets_ratio'].mean()

                if df['liquid_assets_ratio'].iloc[-1] < 20:
                    analysis['alerts'].append("Low liquid assets ratio")

            # Deposit Growth
            if 'total_deposits' in df.columns:
                deposit_growth = self._calculate_yoy_growth(df, 'total_deposits')
                analysis['metrics']['deposit_growth_yoy'] = deposit_growth

                # Funding pressure if deposits growing slower than loans
                if 'total_loans' in df.columns:
                    loan_growth = self._calculate_yoy_growth(df, 'total_loans')
                    if loan_growth > deposit_growth + 5:
                        analysis['alerts'].append("Loans growing faster than deposits - funding pressure")

            logger.info("Completed liquidity analysis")

        except Exception as e:
            logger.error(f"Error in liquidity analysis: {str(e)}")

        return analysis

    def capital_analysis(self, df):
        """
        Capital adequacy analysis

        Args:
            df: DataFrame with banking data

        Returns:
            Dictionary with capital metrics
        """
        analysis = {
            'metrics': {},
            'trends': {},
            'alerts': []
        }

        try:
            # Capital Adequacy Ratio
            if 'capital_adequacy_ratio' in df.columns:
                analysis['metrics']['current_car'] = df['capital_adequacy_ratio'].iloc[-1]
                analysis['metrics']['avg_car'] = df['capital_adequacy_ratio'].mean()
                analysis['trends']['car_trend'] = self._calculate_trend(df['capital_adequacy_ratio'])

                # Regulatory minimum is typically 12% in Turkey
                if df['capital_adequacy_ratio'].iloc[-1] < 12:
                    analysis['alerts'].append(f"CAR below regulatory minimum: {df['capital_adequacy_ratio'].iloc[-1]:.2f}%")
                elif df['capital_adequacy_ratio'].iloc[-1] < 15:
                    analysis['alerts'].append(f"CAR close to minimum buffer: {df['capital_adequacy_ratio'].iloc[-1]:.2f}%")

            # Tier 1 Ratio
            if 'tier1_ratio' in df.columns:
                analysis['metrics']['current_tier1'] = df['tier1_ratio'].iloc[-1]
                analysis['metrics']['avg_tier1'] = df['tier1_ratio'].mean()

                if df['tier1_ratio'].iloc[-1] < 10:
                    analysis['alerts'].append("Tier 1 ratio below 10%")

            # Leverage Ratio
            if 'leverage_ratio' in df.columns:
                analysis['metrics']['current_leverage'] = df['leverage_ratio'].iloc[-1]
                analysis['metrics']['avg_leverage'] = df['leverage_ratio'].mean()

            logger.info("Completed capital analysis")

        except Exception as e:
            logger.error(f"Error in capital analysis: {str(e)}")

        return analysis

    def comprehensive_analysis(self, df):
        """
        Run all analysis modules

        Args:
            df: DataFrame with banking data

        Returns:
            Complete analysis report
        """
        report = {
            'summary': {},
            'asset_quality': {},
            'profitability': {},
            'liquidity': {},
            'capital': {},
            'overall_health': None,
            'all_alerts': []
        }

        # Run all analysis modules
        report['asset_quality'] = self.asset_quality_analysis(df)
        report['profitability'] = self.profitability_analysis(df)
        report['liquidity'] = self.liquidity_analysis(df)
        report['capital'] = self.capital_analysis(df)

        # Compile all alerts
        for category in ['asset_quality', 'profitability', 'liquidity', 'capital']:
            report['all_alerts'].extend(report[category].get('alerts', []))

        # Overall health score
        report['overall_health'] = self._calculate_health_score(report)

        # Summary statistics
        report['summary'] = {
            'total_alerts': len(report['all_alerts']),
            'health_score': report['overall_health'],
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        logger.info("Completed comprehensive analysis")
        return report

    def comparative_analysis(self, df, benchmark='sector'):
        """
        Compare metrics against benchmarks

        Args:
            df: DataFrame with banking data
            benchmark: Benchmark type ('sector', 'historical')

        Returns:
            Comparative analysis results
        """
        comparison = {
            'vs_benchmark': {},
            'percentile_ranks': {}
        }

        # Define benchmark values (these would ideally come from external data)
        sector_benchmarks = {
            'npl_ratio': 3.5,
            'roa': 1.5,
            'roe': 15.0,
            'nim': 3.0,
            'capital_adequacy_ratio': 17.0,
            'loan_deposit_ratio': 100.0
        }

        for metric, benchmark_value in sector_benchmarks.items():
            if metric in df.columns:
                current_value = df[metric].iloc[-1]
                difference = current_value - benchmark_value
                pct_diff = (difference / benchmark_value) * 100

                comparison['vs_benchmark'][metric] = {
                    'current': current_value,
                    'benchmark': benchmark_value,
                    'difference': difference,
                    'pct_difference': pct_diff,
                    'status': 'above' if current_value > benchmark_value else 'below'
                }

        logger.info("Completed comparative analysis")
        return comparison

    def trend_analysis(self, df, periods=[3, 6, 12]):
        """
        Multi-period trend analysis

        Args:
            df: DataFrame with time series data
            periods: List of periods to analyze

        Returns:
            Trend analysis results
        """
        trends = {}

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            trends[col] = {}

            for period in periods:
                if len(df) >= period:
                    recent_data = df[col].iloc[-period:]
                    trend = self._calculate_trend(recent_data)
                    volatility = recent_data.std()

                    trends[col][f'{period}_month'] = {
                        'trend': trend,
                        'volatility': volatility,
                        'direction': 'increasing' if trend > 1 else 'decreasing' if trend < -1 else 'stable'
                    }

        logger.info("Completed trend analysis")
        return trends

    def stress_test_analysis(self, df, scenarios):
        """
        Perform stress test scenarios

        Args:
            df: Current data
            scenarios: Dictionary of stress scenarios

        Returns:
            Stress test results
        """
        results = {}

        # Example scenario: NPL ratio shock
        if 'npl_ratio' in df.columns and 'npl_ratio_shock' in scenarios:
            shock_pct = scenarios['npl_ratio_shock']
            current_npl = df['npl_ratio'].iloc[-1]
            stressed_npl = current_npl * (1 + shock_pct / 100)

            results['npl_shock'] = {
                'current': current_npl,
                'stressed': stressed_npl,
                'impact': stressed_npl - current_npl
            }

        # Capital adequacy under stress
        if 'capital_adequacy_ratio' in df.columns and 'car_shock' in scenarios:
            shock_pct = scenarios['car_shock']
            current_car = df['capital_adequacy_ratio'].iloc[-1]
            stressed_car = current_car * (1 + shock_pct / 100)

            results['capital_shock'] = {
                'current': current_car,
                'stressed': stressed_car,
                'regulatory_buffer': stressed_car - 12  # Assuming 12% minimum
            }

        logger.info("Completed stress test analysis")
        return results

    # Helper methods
    def _calculate_trend(self, series):
        """Calculate trend as percentage change"""
        if len(series) < 2:
            return 0
        return ((series.iloc[-1] - series.iloc[0]) / series.iloc[0]) * 100

    def _calculate_yoy_growth(self, df, column):
        """Calculate year-over-year growth"""
        if len(df) < 12:
            return None

        current = df[column].iloc[-1]
        year_ago = df[column].iloc[-12]

        return ((current - year_ago) / year_ago) * 100

    def _calculate_health_score(self, report):
        """
        Calculate overall banking sector health score (0-100)

        Args:
            report: Complete analysis report

        Returns:
            Health score
        """
        score = 100
        alert_count = len(report['all_alerts'])

        # Deduct points for alerts
        score -= alert_count * 5

        # Ensure score is between 0 and 100
        score = max(0, min(100, score))

        return score


def main():
    """Example usage"""
    analyzer = BankingFinancialAnalyzer()

    # Create sample data
    sample_data = pd.DataFrame({
        'date': pd.date_range('2023-01-01', periods=12, freq='M'),
        'total_assets': np.linspace(10000, 11000, 12),
        'total_loans': np.linspace(7000, 7500, 12),
        'total_deposits': np.linspace(8000, 8300, 12),
        'npl_ratio': np.linspace(3.2, 3.8, 12),
        'roa': np.linspace(1.5, 1.3, 12),
        'roe': np.linspace(14, 13, 12),
        'capital_adequacy_ratio': np.linspace(17, 16.5, 12)
    })

    # Run comprehensive analysis
    report = analyzer.comprehensive_analysis(sample_data)

    print(f"Overall Health Score: {report['overall_health']}")
    print(f"\nTotal Alerts: {report['summary']['total_alerts']}")
    for alert in report['all_alerts']:
        print(f"  - {alert}")


if __name__ == "__main__":
    main()
