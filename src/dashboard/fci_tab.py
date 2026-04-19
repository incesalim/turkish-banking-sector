"""
Financial Conditions Index Dashboard Tab
=========================================
BBVA-style visualization of the Financial Conditions Index.
"""

import pandas as pd
import numpy as np
from dash import dcc, html
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Optional

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from analytics.fci_engine import FCIEngine


# Color scheme for components
COMPONENT_COLORS = {
    "real_exchange_rate": "#1f77b4",    # Blue
    "real_lending_rate": "#9467bd",      # Purple
    "bist100_real_return": "#2ca02c",    # Green
    "policy_rate": "#ff7f0e",            # Orange
    "capital_inflows": "#17becf",        # Cyan
    "yield_slope": "#e377c2",            # Pink (if added later)
}

COMPONENT_LABELS = {
    "real_exchange_rate": "Real Exchange Rate",
    "real_lending_rate": "Real Lending Rate",
    "bist100_real_return": "BIST100 Real Return",
    "policy_rate": "Policy Rate",
    "capital_inflows": "Cap Inflows",
    "yield_slope": "Yield Slope",
}


def create_fci_chart(fci_df: pd.DataFrame, start_date: str = "2019-12-01") -> go.Figure:
    """
    Create BBVA-style FCI visualization.

    Stacked bar chart for component contributions + line for composite FCI.

    Args:
        fci_df: DataFrame with FCI and component z-scores
        start_date: Filter start date

    Returns:
        Plotly Figure
    """
    if fci_df is None or fci_df.empty:
        return go.Figure().add_annotation(
            text="No FCI data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )

    # Filter to start date
    df = fci_df.copy()
    df = df[df.index >= pd.to_datetime(start_date)]

    if df.empty:
        return go.Figure().add_annotation(
            text="No data in selected date range",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )

    # Get component columns (exclude 'fci')
    component_cols = [c for c in df.columns if c != "fci" and c in COMPONENT_COLORS]

    fig = go.Figure()

    # Add stacked bars for each component
    for component in component_cols:
        if component in df.columns:
            fig.add_trace(go.Bar(
                x=df.index,
                y=df[component],
                name=COMPONENT_LABELS.get(component, component),
                marker_color=COMPONENT_COLORS.get(component, "#888888"),
                hovertemplate=(
                    f"<b>{COMPONENT_LABELS.get(component, component)}</b><br>"
                    "Date: %{x|%b %Y}<br>"
                    "Z-Score: %{y:.2f}<br>"
                    "<extra></extra>"
                ),
            ))

    # Add FCI line
    if "fci" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["fci"],
            mode="lines+markers",
            name="FCI (Composite)",
            line=dict(color="#d62728", width=3),
            marker=dict(size=6, color="#d62728"),
            hovertemplate=(
                "<b>Financial Conditions Index</b><br>"
                "Date: %{x|%b %Y}<br>"
                "FCI: %{y:.2f}<br>"
                "<extra></extra>"
            ),
        ))

    # Add zero reference line
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray",
        line_width=1,
        annotation_text="Neutral",
        annotation_position="right"
    )

    # Add annotations for easing/tightening zones
    fig.add_annotation(
        x=df.index[-1],
        y=2,
        text="← EASING",
        showarrow=False,
        font=dict(size=10, color="green"),
        xanchor="right"
    )
    fig.add_annotation(
        x=df.index[-1],
        y=-2,
        text="← TIGHTENING",
        showarrow=False,
        font=dict(size=10, color="red"),
        xanchor="right"
    )

    # Layout
    fig.update_layout(
        title=dict(
            text="<b>FINANCIAL CONDITIONS INDEX (FCI)</b><br><sup>Standardized: + Easing, - Tightening</sup>",
            x=0.5,
            xanchor="center"
        ),
        barmode="relative",  # Allows positive/negative stacking
        xaxis=dict(
            title="",
            tickformat="%b<br>%Y",
            dtick="M3",
            showgrid=True,
            gridcolor="rgba(128,128,128,0.2)"
        ),
        yaxis=dict(
            title="Standard Deviations",
            range=[-4, 4],
            showgrid=True,
            gridcolor="rgba(128,128,128,0.2)",
            zeroline=True,
            zerolinecolor="gray",
            zerolinewidth=2
        ),
        font=dict(family="Inter, sans-serif"),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        plot_bgcolor="white",
        hovermode="x unified",
        height=520,
        margin=dict(t=100, b=80)
    )

    return fig


def create_component_table(latest_fci: dict) -> html.Table:
    """Create component breakdown table."""
    if not latest_fci or "components" not in latest_fci:
        return html.Div("No component data available")

    rows = [
        html.Tr([
            html.Th("Component"),
            html.Th("Z-Score"),
            html.Th("Contribution")
        ])
    ]

    for comp_id, comp_data in latest_fci.get("components", {}).items():
        z_score = comp_data.get("z_score", 0)
        contribution = comp_data.get("contribution", "")

        # Color code based on contribution
        if contribution == "easing":
            color = "green"
            arrow = "↑"
        else:
            color = "red"
            arrow = "↓"

        rows.append(html.Tr([
            html.Td(comp_data.get("name", comp_id)),
            html.Td(f"{z_score:.2f}" if not np.isnan(z_score) else "N/A"),
            html.Td(f"{arrow} {contribution.title()}", style={"color": color})
        ]))

    return html.Table(rows, className="fci-table", style={
        "width": "100%",
        "borderCollapse": "collapse",
        "fontSize": "14px"
    })


def create_fci_kpi_cards(latest_fci: dict) -> html.Div:
    """Create KPI cards for FCI tab."""
    if not latest_fci:
        return html.Div("No FCI data available")

    fci_value = latest_fci.get("fci", 0)
    fci_change = latest_fci.get("fci_change", 0)
    interpretation = latest_fci.get("interpretation", "N/A")
    period = latest_fci.get("period", "N/A")

    # Determine colors
    if fci_value > 0:
        fci_color = "#2ecc71"  # Green for easing
    elif fci_value < -0.5:
        fci_color = "#e74c3c"  # Red for tightening
    else:
        fci_color = "#f39c12"  # Orange for neutral

    change_color = "#2ecc71" if fci_change > 0 else "#e74c3c"

    card_style = {
        "flex": "1",
        "padding": "15px",
        "backgroundColor": "#ffffff",
        "borderRadius": "10px",
        "textAlign": "center",
        "margin": "5px",
        "border": "1px solid #e5e7eb",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
    }
    label_style = {
        "margin": "0",
        "color": "#6b7280",
        "fontSize": "0.75rem",
        "textTransform": "uppercase",
        "letterSpacing": "0.05em",
        "fontWeight": "500",
    }

    cards = html.Div([
        # FCI Value Card
        html.Div([
            html.P("FCI Value", style=label_style),
            html.H3(f"{fci_value:.2f}", style={"margin": "5px 0", "color": fci_color, "fontWeight": "700"}),
            html.P(f"as of {period}", style={"margin": "0", "fontSize": "12px", "color": "#999"})
        ], style=card_style),

        # FCI Change Card
        html.Div([
            html.P("MoM Change", style=label_style),
            html.H3(
                f"{'+' if fci_change > 0 else ''}{fci_change:.2f}",
                style={"margin": "5px 0", "color": change_color, "fontWeight": "700"}
            ),
            html.P("vs previous month", style={"margin": "0", "fontSize": "12px", "color": "#999"})
        ], style=card_style),

        # Interpretation Card
        html.Div([
            html.P("Conditions", style=label_style),
            html.H3(interpretation, style={"margin": "5px 0", "color": fci_color, "fontSize": "18px", "fontWeight": "700"}),
            html.P("financial stance", style={"margin": "0", "fontSize": "12px", "color": "#999"})
        ], style=card_style),

    ], style={"display": "flex", "flexWrap": "wrap", "marginBottom": "20px"})

    return cards


import threading

_fci_cache = {"fci_df": None, "latest_fci": None, "loaded": False, "loading": False, "error": None}
_fci_lock = threading.Lock()


def _load_fci_data():
    """Fetch FCI data once in background and cache it."""
    with _fci_lock:
        if _fci_cache["loaded"] or _fci_cache["loading"]:
            return
        _fci_cache["loading"] = True

    try:
        print("Initializing FCI for dashboard...")
        engine = FCIEngine(start_date="2019-01-01")
        _fci_cache["fci_df"] = engine.calculate_fci()
        _fci_cache["latest_fci"] = engine.get_latest_fci()
        _fci_cache["loaded"] = True
        print("FCI data loaded.")
    except Exception as e:
        _fci_cache["error"] = str(e)
        _fci_cache["loaded"] = True
        print(f"FCI load failed: {e}")
    finally:
        _fci_cache["loading"] = False


# Start loading immediately on import
threading.Thread(target=_load_fci_data, daemon=True).start()


def build_fci_tab() -> html.Div:
    """
    Build the complete FCI tab content.

    Returns:
        Dash HTML Div containing all FCI visualizations
    """
    # If still loading, show a loading message instead of blocking
    if not _fci_cache["loaded"]:
        return html.Div([
            html.H4("Financial Conditions Index", style={
                "marginBottom": "4px", "color": "#1e3a8a",
                "fontFamily": "Inter, sans-serif",
            }),
            html.Div([
                html.P("Loading FCI data from CBRT EVDS...", style={
                    "textAlign": "center", "padding": "60px 20px",
                    "color": "#6b7280", "fontSize": "1.1rem",
                }),
                html.P("Please refresh the page in a few seconds.", style={
                    "textAlign": "center", "color": "#9ca3af", "fontSize": "0.9rem",
                }),
            ], style={
                "backgroundColor": "#ffffff", "borderRadius": "10px",
                "border": "1px solid #e5e7eb", "margin": "20px 0",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
            }),
        ], style={"padding": "20px", "fontFamily": "Inter, sans-serif"})

    fci_df = _fci_cache["fci_df"]
    latest_fci = _fci_cache["latest_fci"]

    # Build tab content
    tab_content = html.Div([
        # Header
        html.H4("Financial Conditions Index", style={
            "marginBottom": "4px",
            "color": "#1e3a8a",
            "fontFamily": "Inter, sans-serif",
        }),
        html.P("Composite measure of monetary and financial conditions", style={
            "color": "#6b7280",
            "marginBottom": "16px",
            "fontSize": "0.9rem",
        }),

        # KPI Cards
        create_fci_kpi_cards(latest_fci),

        # Main Chart
        html.Div([
            dcc.Graph(
                id="fci-main-chart",
                figure=create_fci_chart(fci_df),
                config={
                    'displaylogo': False,
                    'displayModeBar': 'hover',
                    'modeBarButtonsToRemove': [
                        'select2d', 'lasso2d', 'autoScale2d',
                        'hoverClosestCartesian', 'hoverCompareCartesian',
                        'toggleSpikelines',
                    ],
                }
            )
        ], style={"marginBottom": "20px"}),

        # Component Details Row
        html.Div([
            # Component Table
            html.Div([
                html.H5("Component Breakdown", style={"marginBottom": "10px", "color": "#1e3a8a", "fontWeight": "600"}),
                create_component_table(latest_fci)
            ], style={
                "flex": "1",
                "padding": "15px",
                "backgroundColor": "#ffffff",
                "borderRadius": "10px",
                "margin": "5px",
                "border": "1px solid #e5e7eb",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
            }),

            # Methodology Box
            html.Div([
                html.H5("Methodology", style={"marginBottom": "10px", "color": "#1e3a8a", "fontWeight": "600"}),
                html.P([
                    "The Financial Conditions Index (FCI) combines multiple financial indicators ",
                    "into a single measure of monetary and financial conditions.",
                ], style={"fontSize": "13px"}),
                html.Ul([
                    html.Li("Each component is standardized using 36-month rolling z-scores"),
                    html.Li("Positive values indicate easing (stimulative) conditions"),
                    html.Li("Negative values indicate tightening (restrictive) conditions"),
                ], style={"fontSize": "13px", "paddingLeft": "20px"}),
                html.P([
                    html.Strong("Source: "),
                    "CBRT EVDS, Yahoo Finance"
                ], style={"fontSize": "12px", "color": "#666", "marginTop": "10px"})
            ], style={
                "flex": "1",
                "padding": "15px",
                "backgroundColor": "#ffffff",
                "borderRadius": "10px",
                "margin": "5px",
                "border": "1px solid #e5e7eb",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
            }),
        ], style={"display": "flex", "flexWrap": "wrap"}),

    ], style={"padding": "20px", "fontFamily": "Inter, sans-serif"})

    return tab_content


# For standalone testing
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    print("Testing FCI Tab Components...")

    engine = FCIEngine(start_date="2019-12-01")
    fci_df = engine.calculate_fci()
    latest = engine.get_latest_fci()

    print(f"\nLatest FCI: {latest}")

    # Create chart and save as HTML for preview
    fig = create_fci_chart(fci_df)
    fig.write_html("fci_chart_preview.html")
    print("\nChart saved to fci_chart_preview.html")
