"""
Quick Test Dashboard - See It Working Now!
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Create sample BDDK-like data
np.random.seed(42)
categories = [
    'Nakit Değerler', 'T.C. Merkez Bankasından Alacaklar',
    'Para Piyasalarından Alacaklar', 'Bankalardan Alacaklar',
    'Krediler', 'Menkul Kıymetler', 'Finansal Varlıklar',
    'Sabit Kıymetler', 'Diğer Aktifler'
]

data = {
    'Kalem': categories,
    'TP (Milyon TL)': [76980, 2006184, 264634, 425535, 13873015, 3607123, 1580204, 689226, 1312662],
    'YP (Milyon TL)': [335646, 1604220, 5549, 1249573, 8134335, 2526591, 864864, 4204923, 90878],
}

df = pd.DataFrame(data)
df['Toplam'] = df['TP (Milyon TL)'] + df['YP (Milyon TL)']

# Create Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Professional colors
COLORS = {
    'primary': '#1E3A8A',
    'secondary': '#0EA5E9',
    'success': '#10B981',
}

# Layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H1("🏦 BDDK Banking Analysis - Professional Dashboard",
                   className="text-center my-4",
                   style={'color': COLORS['primary']})
        ])
    ]),

    # KPI Cards
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total Items", className="text-muted"),
                    html.H3(f"{len(df)}", className="text-primary"),
                    html.P("Categories", className="small text-muted")
                ])
            ], className="shadow-sm mb-4")
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total (TP)", className="text-muted"),
                    html.H3(f"₺{df['TP (Milyon TL)'].sum()/1e6:.1f}T", className="text-info"),
                    html.P("Turkish Lira", className="small text-muted")
                ])
            ], className="shadow-sm mb-4")
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total (YP)", className="text-muted"),
                    html.H3(f"₺{df['YP (Milyon TL)'].sum()/1e6:.1f}T", className="text-warning"),
                    html.P("Foreign Currency", className="small text-muted")
                ])
            ], className="shadow-sm mb-4")
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Grand Total", className="text-muted"),
                    html.H3(f"₺{df['Toplam'].sum()/1e6:.1f}T", className="text-success"),
                    html.P("+12.3% vs prev month", className="small text-success")
                ])
            ], className="shadow-sm mb-4")
        ], md=3),
    ]),

    # Charts Row
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("📊 Top Categories by Value", className="mb-0")
                ]),
                dbc.CardBody([
                    dcc.Graph(
                        figure=go.Figure(
                            data=[go.Bar(
                                x=df.nlargest(8, 'Toplam')['Toplam'],
                                y=df.nlargest(8, 'Toplam')['Kalem'],
                                orientation='h',
                                marker_color=COLORS['primary']
                            )],
                            layout=go.Layout(
                                xaxis_title="Total Value (Million TL)",
                                yaxis_title="",
                                height=400,
                                template='plotly_white',
                                margin=dict(l=20, r=20, t=20, b=40)
                            )
                        ),
                        config={'displayModeBar': False}
                    )
                ])
            ], className="shadow-sm mb-4")
        ], md=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("📈 TP vs YP Distribution", className="mb-0")
                ]),
                dbc.CardBody([
                    dcc.Graph(
                        figure=go.Figure(
                            data=[go.Pie(
                                labels=['TP (Turkish Lira)', 'YP (Foreign Currency)'],
                                values=[df['TP (Milyon TL)'].sum(), df['YP (Milyon TL)'].sum()],
                                hole=0.4,
                                marker_colors=[COLORS['primary'], COLORS['secondary']]
                            )],
                            layout=go.Layout(
                                height=400,
                                template='plotly_white',
                                margin=dict(l=20, r=20, t=20, b=20)
                            )
                        ),
                        config={'displayModeBar': False}
                    )
                ])
            ], className="shadow-sm mb-4")
        ], md=4),
    ]),

    # Data Table
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("📑 Interactive Data Table", className="mb-0")
                ]),
                dbc.CardBody([
                    html.P("Filter, sort, and export banking sector data", className="text-muted small"),
                    dash_table.DataTable(
                        data=df.to_dict('records'),
                        columns=[{'name': col, 'id': col} for col in df.columns],
                        style_table={'overflowX': 'auto'},
                        style_cell={
                            'textAlign': 'left',
                            'padding': '12px',
                            'fontSize': '14px',
                        },
                        style_header={
                            'backgroundColor': COLORS['primary'],
                            'color': 'white',
                            'fontWeight': 'bold',
                        },
                        style_data_conditional=[
                            {
                                'if': {'row_index': 'odd'},
                                'backgroundColor': 'rgb(248, 248, 248)'
                            }
                        ],
                        page_size=10,
                        filter_action='native',
                        sort_action='native',
                        export_format='xlsx',
                        export_headers='display'
                    )
                ])
            ], className="shadow-sm")
        ])
    ]),

    # Footer
    html.Hr(className="my-4"),
    dbc.Row([
        dbc.Col([
            html.P([
                html.I(className="fas fa-info-circle me-2"),
                "Sample BDDK Banking Data | ",
                html.Span("Professional Dashboard v2.0", className="text-primary fw-bold")
            ], className="text-muted small text-center")
        ])
    ]),

], fluid=True, style={'backgroundColor': '#F8FAFC', 'minHeight': '100vh', 'padding': '20px'})

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  🚀 PROFESSIONAL BDDK BANKING DASHBOARD")
    print("="*70)
    print("\n  📊 Dashboard running at: http://localhost:8050")
    print("  🎯 Features:")
    print("     • Beautiful KPI cards")
    print("     • Interactive charts")
    print("     • Filterable data table")
    print("     • Export to Excel")
    print("\n  Press Ctrl+C to stop")
    print("="*70 + "\n")

    app.run_server(debug=True, port=8050)
