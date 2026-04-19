"""
Interactive Dashboard for Turkish Banking Sector Analysis

Built with Plotly Dash for real-time visualization and analysis.
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config import *


class BankingDashboard:
    """Interactive dashboard for banking sector analysis"""

    def __init__(self, data_source=None):
        """
        Initialize dashboard

        Args:
            data_source: DatabaseManager instance or DataFrame
        """
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP],
            suppress_callback_exceptions=True
        )
        self.data_source = data_source
        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self):
        """Setup dashboard layout"""

        self.app.layout = dbc.Container([
            # Header
            dbc.Row([
                dbc.Col([
                    html.H1("Turkish Banking Sector Analysis Dashboard",
                            className="text-center mb-4 mt-4"),
                    html.H5(f"Data as of: {datetime.now().strftime('%Y-%m-%d')}",
                            className="text-center text-muted mb-4")
                ])
            ]),

            # Control Panel
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("Filters", className="card-title"),
                            dbc.Label("Currency"),
                            dcc.Dropdown(
                                id='currency-dropdown',
                                options=[
                                    {'label': 'Turkish Lira', 'value': 'TL'},
                                    {'label': 'US Dollar', 'value': 'USD'}
                                ],
                                value='TL'
                            ),
                            html.Br(),
                            dbc.Label("Time Period"),
                            dcc.Dropdown(
                                id='period-dropdown',
                                options=[
                                    {'label': 'Last 3 Months', 'value': 3},
                                    {'label': 'Last 6 Months', 'value': 6},
                                    {'label': 'Last 12 Months', 'value': 12},
                                    {'label': 'Last 2 Years', 'value': 24},
                                    {'label': 'All Data', 'value': -1}
                                ],
                                value=12
                            ),
                            html.Br(),
                            dbc.Label("View Type"),
                            dcc.Dropdown(
                                id='view-dropdown',
                                options=[
                                    {'label': 'Overview', 'value': 'overview'},
                                    {'label': 'Asset Quality', 'value': 'asset_quality'},
                                    {'label': 'Profitability', 'value': 'profitability'},
                                    {'label': 'Liquidity', 'value': 'liquidity'},
                                    {'label': 'Capital', 'value': 'capital'}
                                ],
                                value='overview'
                            ),
                            html.Br(),
                            dbc.Button("Refresh Data", id='refresh-btn',
                                       color="primary", className="w-100")
                        ])
                    ])
                ], width=3),

                # Main Display Area
                dbc.Col([
                    dbc.Tabs([
                        dbc.Tab(label="Key Metrics", tab_id="metrics"),
                        dbc.Tab(label="Trends", tab_id="trends"),
                        dbc.Tab(label="Comparative", tab_id="comparative"),
                        dbc.Tab(label="Analytics", tab_id="analytics")
                    ], id="tabs", active_tab="metrics")
                ], width=9)
            ]),

            html.Br(),

            # Content Area
            dbc.Row([
                dbc.Col([
                    html.Div(id='dashboard-content')
                ], width=12)
            ]),

            # Store for data
            dcc.Store(id='data-store')

        ], fluid=True)

    def setup_callbacks(self):
        """Setup interactive callbacks"""

        @self.app.callback(
            Output('dashboard-content', 'children'),
            [Input('tabs', 'active_tab'),
             Input('currency-dropdown', 'value'),
             Input('period-dropdown', 'value'),
             Input('view-dropdown', 'value'),
             Input('refresh-btn', 'n_clicks')]
        )
        def update_content(active_tab, currency, period, view, n_clicks):
            """Update dashboard content based on selections"""

            if active_tab == 'metrics':
                return self.create_metrics_view(currency, period, view)
            elif active_tab == 'trends':
                return self.create_trends_view(currency, period)
            elif active_tab == 'comparative':
                return self.create_comparative_view(currency, period)
            elif active_tab == 'analytics':
                return self.create_analytics_view(currency, period)

    def create_metrics_view(self, currency, period, view):
        """Create key metrics cards and charts"""

        # Generate sample data (replace with actual data loading)
        df = self.generate_sample_data(period)

        if view == 'overview':
            return dbc.Container([
                # KPI Cards
                dbc.Row([
                    dbc.Col([
                        self.create_kpi_card("Total Assets", "12.5T", "+8.5%", "success")
                    ], width=3),
                    dbc.Col([
                        self.create_kpi_card("Total Loans", "8.2T", "+12.3%", "success")
                    ], width=3),
                    dbc.Col([
                        self.create_kpi_card("NPL Ratio", "3.8%", "+0.3pp", "warning")
                    ], width=3),
                    dbc.Col([
                        self.create_kpi_card("CAR", "16.5%", "-0.5pp", "info")
                    ], width=3)
                ], className="mb-4"),

                # Charts
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=self.create_asset_growth_chart(df))
                    ], width=6),
                    dbc.Col([
                        dcc.Graph(figure=self.create_loan_composition_chart(df))
                    ], width=6)
                ])
            ])

        elif view == 'asset_quality':
            return dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=self.create_npl_trend_chart(df))
                    ], width=6),
                    dbc.Col([
                        dcc.Graph(figure=self.create_provision_chart(df))
                    ], width=6)
                ]),
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=self.create_loan_growth_chart(df))
                    ], width=12)
                ])
            ])

        elif view == 'profitability':
            return dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=self.create_roa_roe_chart(df))
                    ], width=6),
                    dbc.Col([
                        dcc.Graph(figure=self.create_nim_chart(df))
                    ], width=6)
                ]),
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=self.create_profit_breakdown_chart(df))
                    ], width=12)
                ])
            ])

        elif view == 'liquidity':
            return dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=self.create_ld_ratio_chart(df))
                    ], width=6),
                    dbc.Col([
                        dcc.Graph(figure=self.create_liquid_assets_chart(df))
                    ], width=6)
                ])
            ])

        elif view == 'capital':
            return dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=self.create_car_chart(df))
                    ], width=6),
                    dbc.Col([
                        dcc.Graph(figure=self.create_capital_composition_chart(df))
                    ], width=6)
                ])
            ])

    def create_trends_view(self, currency, period):
        """Create trends analysis view"""
        df = self.generate_sample_data(period)

        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H4("Multi-Metric Trend Analysis"),
                    dcc.Graph(figure=self.create_multi_metric_chart(df))
                ], width=12)
            ]),
            html.Br(),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(figure=self.create_growth_rates_chart(df))
                ], width=6),
                dbc.Col([
                    dcc.Graph(figure=self.create_volatility_chart(df))
                ], width=6)
            ])
        ])

    def create_comparative_view(self, currency, period):
        """Create comparative analysis view"""
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H4("Benchmark Comparison"),
                    dcc.Graph(figure=self.create_benchmark_radar_chart())
                ], width=6),
                dbc.Col([
                    html.H4("Peer Analysis"),
                    dcc.Graph(figure=self.create_peer_comparison_chart())
                ], width=6)
            ])
        ])

    def create_analytics_view(self, currency, period):
        """Create advanced analytics view"""
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H4("Correlation Analysis"),
                    dcc.Graph(figure=self.create_correlation_heatmap())
                ], width=6),
                dbc.Col([
                    html.H4("Statistical Summary"),
                    html.Div(id='stats-summary')
                ], width=6)
            ])
        ])

    # Chart creation methods
    def create_kpi_card(self, title, value, change, color):
        """Create KPI card"""
        return dbc.Card([
            dbc.CardBody([
                html.H6(title, className="card-subtitle text-muted"),
                html.H3(value, className="card-title"),
                html.P(change, className=f"text-{color}")
            ])
        ])

    def create_asset_growth_chart(self, df):
        """Asset growth time series"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['total_assets'],
            mode='lines+markers',
            name='Total Assets',
            line=dict(color='#1f77b4', width=2)
        ))
        fig.update_layout(
            title="Total Assets Growth",
            xaxis_title="Date",
            yaxis_title="Total Assets (Billions TL)",
            hovermode='x unified'
        )
        return fig

    def create_loan_composition_chart(self, df):
        """Loan composition pie chart"""
        labels = ['Commercial', 'Consumer', 'SME', 'Credit Cards']
        values = [45, 25, 20, 10]

        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3)])
        fig.update_layout(title="Loan Portfolio Composition")
        return fig

    def create_npl_trend_chart(self, df):
        """NPL ratio trend"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['npl_ratio'],
            mode='lines+markers',
            name='NPL Ratio',
            line=dict(color='red', width=2)
        ))
        fig.add_hline(y=5, line_dash="dash", line_color="orange",
                      annotation_text="Threshold")
        fig.update_layout(
            title="NPL Ratio Trend",
            xaxis_title="Date",
            yaxis_title="NPL Ratio (%)",
            hovermode='x unified'
        )
        return fig

    def create_provision_chart(self, df):
        """Provision coverage chart"""
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['date'],
            y=df['provision_coverage'],
            name='Provision Coverage',
            marker_color='lightblue'
        ))
        fig.update_layout(
            title="Provision Coverage Ratio",
            xaxis_title="Date",
            yaxis_title="Coverage (%)"
        )
        return fig

    def create_loan_growth_chart(self, df):
        """Loan growth rate chart"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['loan_growth'],
            mode='lines',
            fill='tozeroy',
            name='Loan Growth',
            line=dict(color='green')
        ))
        fig.update_layout(
            title="Year-over-Year Loan Growth",
            xaxis_title="Date",
            yaxis_title="Growth Rate (%)"
        )
        return fig

    def create_roa_roe_chart(self, df):
        """ROA and ROE dual axis chart"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['roa'],
            mode='lines+markers',
            name='ROA',
            line=dict(color='blue')
        ))
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['roe'],
            mode='lines+markers',
            name='ROE',
            line=dict(color='green')
        ))
        fig.update_layout(
            title="Profitability Metrics: ROA vs ROE",
            xaxis_title="Date",
            yaxis_title="Return (%)",
            hovermode='x unified'
        )
        return fig

    def create_nim_chart(self, df):
        """Net Interest Margin chart"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['nim'],
            mode='lines+markers',
            name='NIM',
            line=dict(color='purple', width=2)
        ))
        fig.update_layout(
            title="Net Interest Margin Trend",
            xaxis_title="Date",
            yaxis_title="NIM (%)"
        )
        return fig

    def create_profit_breakdown_chart(self, df):
        """Profit breakdown stacked bar"""
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Interest Income', x=df['date'],
                             y=df['interest_income']))
        fig.add_trace(go.Bar(name='Fee Income', x=df['date'],
                             y=df['fee_income']))
        fig.add_trace(go.Bar(name='Trading Income', x=df['date'],
                             y=df['trading_income']))
        fig.update_layout(barmode='stack', title="Income Composition")
        return fig

    def create_ld_ratio_chart(self, df):
        """Loan to Deposit ratio"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['ld_ratio'],
            mode='lines+markers',
            name='L/D Ratio',
            line=dict(color='orange', width=2)
        ))
        fig.add_hline(y=100, line_dash="dash", annotation_text="100%")
        fig.update_layout(
            title="Loan-to-Deposit Ratio",
            xaxis_title="Date",
            yaxis_title="L/D Ratio (%)"
        )
        return fig

    def create_liquid_assets_chart(self, df):
        """Liquid assets chart"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['liquid_assets'],
            mode='lines',
            fill='tozeroy',
            name='Liquid Assets'
        ))
        fig.update_layout(
            title="Liquid Assets Trend",
            xaxis_title="Date",
            yaxis_title="Liquid Assets (Billions TL)"
        )
        return fig

    def create_car_chart(self, df):
        """Capital Adequacy Ratio"""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['car'],
            mode='lines+markers',
            name='CAR',
            line=dict(color='darkgreen', width=2)
        ))
        fig.add_hline(y=12, line_dash="dash", line_color="red",
                      annotation_text="Regulatory Minimum (12%)")
        fig.update_layout(
            title="Capital Adequacy Ratio",
            xaxis_title="Date",
            yaxis_title="CAR (%)"
        )
        return fig

    def create_capital_composition_chart(self, df):
        """Capital composition"""
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Tier 1', x=df['date'], y=df['tier1']))
        fig.add_trace(go.Bar(name='Tier 2', x=df['date'], y=df['tier2']))
        fig.update_layout(
            barmode='stack',
            title="Capital Composition: Tier 1 vs Tier 2"
        )
        return fig

    def create_multi_metric_chart(self, df):
        """Multi-metric normalized chart"""
        # Normalize metrics to 0-100 scale
        metrics = ['total_assets', 'total_loans', 'total_deposits']
        fig = go.Figure()

        for metric in metrics:
            normalized = (df[metric] - df[metric].min()) / (df[metric].max() - df[metric].min()) * 100
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=normalized,
                mode='lines',
                name=metric.replace('_', ' ').title()
            ))

        fig.update_layout(
            title="Multi-Metric Trend (Normalized)",
            xaxis_title="Date",
            yaxis_title="Normalized Value (0-100)"
        )
        return fig

    def create_growth_rates_chart(self, df):
        """Growth rates comparison"""
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Asset Growth', x=df['date'], y=df['asset_growth']))
        fig.add_trace(go.Bar(name='Loan Growth', x=df['date'], y=df['loan_growth']))
        fig.add_trace(go.Bar(name='Deposit Growth', x=df['date'], y=df['deposit_growth']))

        fig.update_layout(
            barmode='group',
            title="Year-over-Year Growth Rates"
        )
        return fig

    def create_volatility_chart(self, df):
        """Volatility analysis"""
        # Calculate rolling volatility
        window = 3
        volatility = df['total_assets'].rolling(window).std()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=volatility,
            mode='lines',
            fill='tozeroy',
            name=f'{window}-Month Volatility'
        ))
        fig.update_layout(title="Asset Volatility", xaxis_title="Date")
        return fig

    def create_benchmark_radar_chart(self):
        """Radar chart for benchmark comparison"""
        categories = ['NPL Ratio', 'ROA', 'ROE', 'CAR', 'L/D Ratio']

        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=[85, 90, 75, 95, 80],
            theta=categories,
            fill='toself',
            name='Current'
        ))

        fig.add_trace(go.Scatterpolar(
            r=[80, 85, 80, 90, 85],
            theta=categories,
            fill='toself',
            name='Benchmark'
        ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="Performance vs Benchmark"
        )
        return fig

    def create_peer_comparison_chart(self):
        """Peer comparison bar chart"""
        metrics = ['ROA', 'ROE', 'CAR', 'L/D Ratio']
        sector = [1.5, 15, 17, 95]
        current = [1.3, 13, 16.5, 105]

        fig = go.Figure()
        fig.add_trace(go.Bar(name='Sector Average', x=metrics, y=sector))
        fig.add_trace(go.Bar(name='Current', x=metrics, y=current))

        fig.update_layout(
            barmode='group',
            title="Peer Comparison"
        )
        return fig

    def create_correlation_heatmap(self):
        """Correlation heatmap"""
        # Sample correlation matrix
        metrics = ['Assets', 'Loans', 'Deposits', 'NPL', 'CAR']
        corr_matrix = np.random.rand(5, 5)
        np.fill_diagonal(corr_matrix, 1)

        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix,
            x=metrics,
            y=metrics,
            colorscale='RdBu',
            zmid=0
        ))

        fig.update_layout(title="Metric Correlation Matrix")
        return fig

    def generate_sample_data(self, periods):
        """Generate sample data for demonstration"""
        if periods == -1:
            periods = 24

        dates = pd.date_range(end=datetime.now(), periods=periods, freq='M')

        df = pd.DataFrame({
            'date': dates,
            'total_assets': np.linspace(10000, 12500, periods) + np.random.randn(periods) * 200,
            'total_loans': np.linspace(7000, 8200, periods) + np.random.randn(periods) * 150,
            'total_deposits': np.linspace(8000, 9000, periods) + np.random.randn(periods) * 100,
            'npl_ratio': np.linspace(3.5, 3.8, periods) + np.random.randn(periods) * 0.1,
            'provision_coverage': np.linspace(75, 78, periods) + np.random.randn(periods) * 2,
            'loan_growth': np.linspace(10, 12, periods) + np.random.randn(periods) * 1,
            'roa': np.linspace(1.5, 1.3, periods) + np.random.randn(periods) * 0.1,
            'roe': np.linspace(14, 13, periods) + np.random.randn(periods) * 0.5,
            'nim': np.linspace(3.2, 2.9, periods) + np.random.randn(periods) * 0.1,
            'interest_income': np.random.rand(periods) * 500 + 1000,
            'fee_income': np.random.rand(periods) * 200 + 300,
            'trading_income': np.random.rand(periods) * 100 + 100,
            'ld_ratio': np.linspace(95, 105, periods) + np.random.randn(periods) * 2,
            'liquid_assets': np.linspace(2000, 2300, periods) + np.random.randn(periods) * 50,
            'car': np.linspace(17, 16.5, periods) + np.random.randn(periods) * 0.2,
            'tier1': np.linspace(14, 13.5, periods) + np.random.randn(periods) * 0.2,
            'tier2': np.linspace(3, 3, periods) + np.random.randn(periods) * 0.1,
            'asset_growth': np.linspace(8, 10, periods) + np.random.randn(periods) * 1,
            'deposit_growth': np.linspace(6, 8, periods) + np.random.randn(periods) * 1
        })

        return df

    def run(self, debug=True, port=8050):
        """Run the dashboard"""
        self.app.run_server(debug=debug, port=port)


def main():
    """Run dashboard"""
    dashboard = BankingDashboard()
    print("Starting dashboard on http://localhost:8050")
    dashboard.run(debug=True)


if __name__ == "__main__":
    main()
