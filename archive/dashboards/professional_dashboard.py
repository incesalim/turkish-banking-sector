"""
Professional Banking Dashboard - Enterprise Grade

Advanced interactive dashboard with drill-down capabilities,
comparative analysis, and professional styling.
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config import *
from utils.database import DatabaseManager
from utils.monthly_data_manager import MonthlyDataManager


# Professional color scheme
COLORS = {
    'primary': '#1E3A8A',      # Deep blue
    'secondary': '#0EA5E9',    # Sky blue
    'success': '#10B981',      # Green
    'warning': '#F59E0B',      # Amber
    'danger': '#EF4444',       # Red
    'background': '#F8FAFC',   # Light gray
    'surface': '#FFFFFF',      # White
    'text': '#1E293B',         # Dark gray
    'text_secondary': '#64748B', # Medium gray
    'border': '#E2E8F0',       # Light border
    'accent': '#8B5CF6'        # Purple
}


class ProfessionalBankingDashboard:
    """Enterprise-grade banking dashboard"""

    def __init__(self, data_manager=None):
        """
        Initialize dashboard

        Args:
            data_manager: MonthlyDataManager instance
        """
        self.data_manager = data_manager or MonthlyDataManager()

        # Initialize Dash app with Bootstrap theme
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
            meta_tags=[
                {"name": "viewport", "content": "width=device-width, initial-scale=1"}
            ]
        )

        self.app.title = "BDDK Banking Analysis - Professional Dashboard"

        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self):
        """Setup professional dashboard layout"""

        # Navigation bar
        navbar = dbc.Navbar(
            dbc.Container([
                dbc.Row([
                    dbc.Col(
                        html.Div([
                            html.I(className="fas fa-chart-line me-2",
                                  style={'fontSize': '24px'}),
                            html.Span("BDDK Banking Analysis",
                                     style={'fontSize': '20px', 'fontWeight': '600'})
                        ]),
                        width="auto"
                    ),
                ], align="center", className="g-0"),

                dbc.Row([
                    dbc.Col([
                        dbc.NavItem(dbc.NavLink([
                            html.I(className="fas fa-sync-alt me-1"),
                            "Refresh"
                        ], id="refresh-btn", className="btn btn-sm btn-outline-light"))
                    ], width="auto"),
                    dbc.Col([
                        html.Span(id="last-update", className="text-light small")
                    ], width="auto")
                ], align="center")
            ], fluid=True),
            color=COLORS['primary'],
            dark=True,
            className="mb-4 shadow-sm"
        )

        # Control Panel
        control_panel = dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Period", className="fw-bold small mb-1"),
                        dcc.Dropdown(
                            id='period-selector',
                            placeholder="Select period...",
                            className="dash-dropdown"
                        )
                    ], md=3),

                    dbc.Col([
                        html.Label("Currency", className="fw-bold small mb-1"),
                        dcc.Dropdown(
                            id='currency-selector',
                            options=[
                                {'label': '🇹🇷 Turkish Lira (TL)', 'value': 'TL'},
                                {'label': '🇺🇸 US Dollar (USD)', 'value': 'USD'}
                            ],
                            value='TL',
                            clearable=False
                        )
                    ], md=2),

                    dbc.Col([
                        html.Label("Compare With", className="fw-bold small mb-1"),
                        dcc.Dropdown(
                            id='compare-period',
                            placeholder="Select period to compare...",
                        )
                    ], md=3),

                    dbc.Col([
                        html.Label("Data Type", className="fw-bold small mb-1"),
                        dcc.Dropdown(
                            id='data-type-selector',
                            options=[
                                {'label': 'Balance Sheet (Bilanço)', 'value': 'bilanco'},
                                {'label': 'Income Statement (Gelir-Gider)', 'value': 'gelir_gider'},
                                {'label': 'Loans (Krediler)', 'value': 'krediler'},
                                {'label': 'Deposits (Mevduat)', 'value': 'mevduat'}
                            ],
                            value='bilanco',
                            clearable=False
                        )
                    ], md=2),

                    dbc.Col([
                        html.Label("View", className="fw-bold small mb-1"),
                        dbc.ButtonGroup([
                            dbc.Button([html.I(className="fas fa-table me-1"), "Table"],
                                      id="view-table", size="sm", outline=True, color="primary"),
                            dbc.Button([html.I(className="fas fa-chart-bar me-1"), "Charts"],
                                      id="view-charts", size="sm", outline=True, color="primary", active=True),
                        ], size="sm")
                    ], md=2)
                ])
            ])
        ], className="mb-4 shadow-sm")

        # KPI Cards Row
        kpi_cards = dbc.Row(id="kpi-cards", className="mb-4")

        # Main Content Tabs
        tabs = dbc.Tabs([
            dbc.Tab(label="📊 Overview", tab_id="overview",
                   label_style={"padding": "12px 24px"}),
            dbc.Tab(label="📈 Trends", tab_id="trends",
                   label_style={"padding": "12px 24px"}),
            dbc.Tab(label="🔍 Deep Dive", tab_id="deepdive",
                   label_style={"padding": "12px 24px"}),
            dbc.Tab(label="⚖️ Comparative", tab_id="comparative",
                   label_style={"padding": "12px 24px"}),
            dbc.Tab(label="📑 Data Table", tab_id="datatable",
                   label_style={"padding": "12px 24px"}),
        ], id="main-tabs", active_tab="overview", className="mb-4")

        # Tab Content
        tab_content = html.Div(id="tab-content", className="mb-4")

        # Footer
        footer = dbc.Container([
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    html.P([
                        html.I(className="fas fa-info-circle me-2"),
                        "Data source: BDDK (Banking Regulation and Supervision Agency) | ",
                        html.A("www.bddk.org.tr", href="https://www.bddk.org.tr",
                              target="_blank", className="text-decoration-none")
                    ], className="text-muted small mb-0")
                ], md=8),
                dbc.Col([
                    html.P([
                        html.I(className="fas fa-clock me-2"),
                        html.Span(id="footer-timestamp")
                    ], className="text-muted small mb-0 text-end")
                ], md=4)
            ])
        ], fluid=True, className="py-3")

        # Complete Layout
        self.app.layout = dbc.Container([
            navbar,
            control_panel,
            kpi_cards,
            tabs,
            tab_content,
            footer,

            # Stores for data
            dcc.Store(id='data-store'),
            dcc.Store(id='compare-data-store'),
            dcc.Interval(id='interval-update', interval=60*1000, n_intervals=0)  # Update every minute

        ], fluid=True, style={'backgroundColor': COLORS['background'], 'minHeight': '100vh'})

    def setup_callbacks(self):
        """Setup interactive callbacks"""

        @self.app.callback(
            [Output('period-selector', 'options'),
             Output('period-selector', 'value'),
             Output('compare-period', 'options')],
            [Input('currency-selector', 'value'),
             Input('data-type-selector', 'value')]
        )
        def update_period_options(currency, data_type):
            """Update available periods based on currency and data type"""
            periods = self.data_manager.get_available_periods(currency, data_type)

            if not periods:
                return [], None, []

            options = [
                {
                    'label': f"{datetime(year, month, 1).strftime('%B %Y')}",
                    'value': f"{year}-{month:02d}"
                }
                for year, month in periods
            ]

            # Set latest period as default
            latest = f"{periods[0][0]}-{periods[0][1]:02d}" if periods else None

            return options, latest, options

        @self.app.callback(
            Output('kpi-cards', 'children'),
            [Input('data-store', 'data'),
             Input('compare-data-store', 'data')]
        )
        def update_kpi_cards(data, compare_data):
            """Update KPI cards"""
            if not data:
                return self._create_loading_kpis()

            df = pd.DataFrame(data)

            # Calculate key metrics
            kpis = self._calculate_kpis(df, compare_data)

            return self._create_kpi_cards(kpis)

        @self.app.callback(
            Output('tab-content', 'children'),
            [Input('main-tabs', 'active_tab'),
             Input('data-store', 'data'),
             Input('compare-data-store', 'data')]
        )
        def render_tab_content(active_tab, data, compare_data):
            """Render content based on active tab"""
            if not data:
                return self._create_loading_content()

            df = pd.DataFrame(data)

            if active_tab == 'overview':
                return self._create_overview_tab(df, compare_data)
            elif active_tab == 'trends':
                return self._create_trends_tab(df)
            elif active_tab == 'deepdive':
                return self._create_deepdive_tab(df)
            elif active_tab == 'comparative':
                return self._create_comparative_tab(df, compare_data)
            elif active_tab == 'datatable':
                return self._create_datatable_tab(df)

        @self.app.callback(
            Output('last-update', 'children'),
            Input('interval-update', 'n_intervals')
        )
        def update_timestamp(n):
            """Update last refresh timestamp"""
            return f"Last updated: {datetime.now().strftime('%H:%M:%S')}"

        @self.app.callback(
            Output('footer-timestamp', 'children'),
            Input('interval-update', 'n_intervals')
        )
        def update_footer_timestamp(n):
            """Update footer timestamp"""
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Helper methods for creating content

    def _create_kpi_card(self, title, value, change=None, icon="fa-chart-line",
                        color='primary', format_type='number'):
        """Create a KPI card"""
        # Format value
        if format_type == 'number':
            value_str = f"{value:,.0f}" if value else "N/A"
        elif format_type == 'percent':
            value_str = f"{value:.2f}%" if value else "N/A"
        elif format_type == 'currency':
            value_str = f"₺{value:,.0f}" if value else "N/A"
        else:
            value_str = str(value)

        # Change indicator
        change_element = None
        if change is not None:
            change_color = 'success' if change >= 0 else 'danger'
            change_icon = 'fa-arrow-up' if change >= 0 else 'fa-arrow-down'
            change_element = html.Div([
                html.I(className=f"fas {change_icon} me-1"),
                html.Span(f"{abs(change):.1f}%")
            ], className=f"text-{change_color} small fw-bold mt-2")

        card = dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.P(title, className="text-muted small mb-1"),
                            html.H4(value_str, className="mb-0 fw-bold"),
                            change_element if change_element else html.Div()
                        ])
                    ], width=9),
                    dbc.Col([
                        html.Div([
                            html.I(className=f"fas {icon} fa-2x text-{color} opacity-50")
                        ], className="text-end")
                    ], width=3)
                ], align="center")
            ])
        ], className="shadow-sm h-100", style={'borderLeft': f'4px solid var(--bs-{color})'})

        return card

    def _create_loading_kpis(self):
        """Create loading skeleton for KPI cards"""
        return dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    dbc.Spinner(size="sm"),
                    html.P("Loading...", className="text-muted small mt-2")
                ])
            ]), md=3)
            for _ in range(4)
        ])

    def _create_loading_content(self):
        """Create loading content"""
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        dbc.Spinner(color="primary"),
                        html.H5("Loading data...", className="text-muted mt-3")
                    ], className="text-center py-5")
                ])
            ])
        ])

    def _calculate_kpis(self, df, compare_data=None):
        """Calculate KPIs from data"""
        kpis = {
            'total_items': len(df),
            'total_tp': df['tp'].sum() if 'tp' in df.columns else 0,
            'total_yp': df['yp'].sum() if 'yp' in df.columns else 0,
            'total_value': df['total'].sum() if 'total' in df.columns else 0,
        }

        # Calculate changes if comparison data provided
        if compare_data:
            compare_df = pd.DataFrame(compare_data)
            if 'total' in compare_df.columns and 'total' in df.columns:
                current_total = df['total'].sum()
                compare_total = compare_df['total'].sum()
                if compare_total != 0:
                    kpis['total_change'] = ((current_total - compare_total) / compare_total) * 100

        return kpis

    def _create_kpi_cards(self, kpis):
        """Create KPI cards from calculated metrics"""
        return dbc.Row([
            dbc.Col(
                self._create_kpi_card(
                    "Total Items",
                    kpis.get('total_items', 0),
                    icon="fa-list",
                    color="primary",
                    format_type="number"
                ), md=3
            ),
            dbc.Col(
                self._create_kpi_card(
                    "Total (TP)",
                    kpis.get('total_tp', 0),
                    icon="fa-lira-sign",
                    color="info",
                    format_type="currency"
                ), md=3
            ),
            dbc.Col(
                self._create_kpi_card(
                    "Total (YP)",
                    kpis.get('total_yp', 0),
                    icon="fa-dollar-sign",
                    color="warning",
                    format_type="currency"
                ), md=3
            ),
            dbc.Col(
                self._create_kpi_card(
                    "Grand Total",
                    kpis.get('total_value', 0),
                    change=kpis.get('total_change'),
                    icon="fa-chart-bar",
                    color="success",
                    format_type="currency"
                ), md=3
            ),
        ])

    def _create_overview_tab(self, df, compare_data=None):
        """Create overview tab content"""
        # Top categories chart
        top_categories = df.nlargest(10, 'total')[['item_name_clean', 'total']]

        fig_top = go.Figure()
        fig_top.add_trace(go.Bar(
            x=top_categories['total'],
            y=top_categories['item_name_clean'],
            orientation='h',
            marker_color=COLORS['primary']
        ))

        fig_top.update_layout(
            title="Top 10 Categories by Value",
            xaxis_title="Total Value",
            yaxis_title="",
            height=400,
            template="plotly_white"
        )

        # Distribution chart
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Pie(
            labels=['TP', 'YP'],
            values=[df['tp'].sum(), df['yp'].sum()],
            hole=0.4,
            marker_colors=[COLORS['primary'], COLORS['secondary']]
        ))

        fig_dist.update_layout(
            title="TP vs YP Distribution",
            height=400,
            template="plotly_white"
        )

        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            dcc.Graph(figure=fig_top, config={'displayModeBar': False})
                        ])
                    ], className="shadow-sm")
                ], md=8),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            dcc.Graph(figure=fig_dist, config={'displayModeBar': False})
                        ])
                    ], className="shadow-sm")
                ], md=4)
            ])
        ], fluid=True)

    def _create_trends_tab(self, df):
        """Create trends tab"""
        return html.Div([
            html.H5("Trend Analysis Coming Soon"),
            html.P("This will show historical trends when multiple periods are loaded.")
        ])

    def _create_deepdive_tab(self, df):
        """Create deep dive tab"""
        # Category breakdown
        if 'category' in df.columns:
            category_totals = df.groupby('category')['total'].sum().sort_values(ascending=False)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=category_totals.index,
                y=category_totals.values,
                marker_color=COLORS['accent']
            ))

            fig.update_layout(
                title="Category Breakdown",
                xaxis_title="Category",
                yaxis_title="Total Value",
                height=500,
                template="plotly_white"
            )

            return dbc.Card([
                dbc.CardBody([
                    dcc.Graph(figure=fig, config={'displayModeBar': True})
                ])
            ], className="shadow-sm")

        return html.Div("No category data available")

    def _create_comparative_tab(self, df, compare_data):
        """Create comparative analysis tab"""
        if not compare_data:
            return html.Div([
                dbc.Alert("Please select a period to compare in the control panel above.",
                         color="info", className="mt-4")
            ])

        return html.Div("Comparative analysis will be shown here")

    def _create_datatable_tab(self, df):
        """Create interactive data table tab"""
        # Prepare data for table
        display_cols = ['item_name_clean', 'tp', 'yp', 'total', 'category', 'level']
        display_df = df[[col for col in display_cols if col in df.columns]]

        table = dash_table.DataTable(
            data=display_df.to_dict('records'),
            columns=[{'name': col, 'id': col} for col in display_df.columns],
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '12px',
                'fontSize': '14px',
                'fontFamily': 'Inter, sans-serif'
            },
            style_header={
                'backgroundColor': COLORS['primary'],
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'left'
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': COLORS['background']
                }
            ],
            page_size=20,
            filter_action='native',
            sort_action='native',
            export_format='xlsx',
            export_headers='display'
        )

        return dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.H5("Interactive Data Table", className="mb-3"),
                    html.P("Filter, sort, and export data", className="text-muted small"),
                    table
                ])
            ])
        ], className="shadow-sm")

    def run(self, debug=True, port=8050, host='127.0.0.1'):
        """Run the dashboard"""
        print(f"\n{'='*70}")
        print("🚀 PROFESSIONAL BDDK BANKING DASHBOARD")
        print(f"{'='*70}")
        print(f"\n📊 Dashboard starting on http://{host}:{port}")
        print(f"📅 Data loaded from database")
        print(f"\n{'='*70}\n")

        self.app.run_server(debug=debug, port=port, host=host)


def main():
    """Run professional dashboard"""
    dashboard = ProfessionalBankingDashboard()
    dashboard.run(debug=True, port=8050)


if __name__ == "__main__":
    main()
