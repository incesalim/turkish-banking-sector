"""Rates section — weekly flow interest rates and monetary policy context.

Data source: TCMB EVDS (evds3.tcmb.gov.tr). See src/dashboard/evds.py.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc
import dash_bootstrap_components as dbc

from src.dashboard import charts as C, theme, evds


# ---------------------------------------------------------------------------
# Weekly TL loan & deposit rates (matches BBVA's "TL LOAN & DEPOSIT RATES" chart)
# ---------------------------------------------------------------------------
RATE_SERIES = {
    "Consumer loan":               "TP.KTFTUK",
    "Consumer loan (incl. overdraft)": "TP.KTFTUK01",
    "Commercial (ex cards & overdraft)": "TP.KTF18",
    "Deposit (total TL)":          "TP.TRY.MT06",
}
RATE_COLORS = {
    "Consumer loan":                     "#1e3a8a",   # dark navy
    "Consumer loan (incl. overdraft)":   "#60a5fa",   # light blue
    "Commercial (ex cards & overdraft)": "#22c55e",   # green
    "Deposit (total TL)":                "#f59e0b",   # orange
}


def _panel_tl_rates():
    today = datetime.today().strftime("%Y-%m-%d")
    start = "2024-01-01"
    df = evds.fetch_many(RATE_SERIES, start, today)
    if df.empty:
        return C.chart_panel(C._empty_fig("EVDS unavailable"),
                              caption="Could not reach TCMB EVDS.")

    fig = go.Figure()
    for label, color in RATE_COLORS.items():
        sub = df[df["label"] == label].sort_values("date")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["date"], y=sub["value"], mode="lines",
            name=label, line=dict(color=color, width=2.2),
            hovertemplate=f"<b>{label}</b><br>%{{x|%d %b %Y}}<br>" + "%{y:.2f}%<extra></extra>",
        ))
        # Endpoint label
        last = sub.iloc[-1]
        fig.add_annotation(
            x=last["date"], y=last["value"],
            text=f"{last['value']:.1f}%",
            showarrow=False, xanchor="left", xshift=6,
            font=dict(color=color, size=10, family=theme.FONT_FAMILY),
        )

    C._apply_layout(fig, "TL Loan & Deposit Rates (Weekly, Flow, Sector)", height=360)
    fig.update_yaxes(ticksuffix="%", tickformat=".0f")
    fig.update_xaxes(tickformat="%b %y")

    # Narrative caption from latest data
    latest = (
        df.sort_values("date").groupby("label").tail(1).set_index("label")["value"].to_dict()
    )
    spread = None
    if "Consumer loan" in latest and "Deposit (total TL)" in latest:
        spread = latest["Consumer loan"] - latest["Deposit (total TL)"]
    caption_parts = [
        f"Consumer {latest.get('Consumer loan', 0):.1f}%",
        f"Commercial {latest.get('Commercial (ex cards & overdraft)', 0):.1f}%",
        f"Deposit {latest.get('Deposit (total TL)', 0):.1f}%",
    ]
    caption = " · ".join(caption_parts)
    if spread is not None:
        caption += f" · Consumer-vs-deposit spread {spread:+.1f}pp."

    return C.chart_panel(fig, caption=caption)


def _panel_policy_rate():
    df = evds.fetch_series("TP.APIFON4", "2024-01-01",
                           datetime.today().strftime("%Y-%m-%d"))
    if df.empty:
        return C.chart_panel(C._empty_fig(), caption="")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["value"], mode="lines",
        name="Policy Rate",
        line=dict(color=theme.ACCENT, width=2.4),
        hovertemplate="<b>Policy Rate</b><br>%{x|%d %b %Y}<br>" + "%{y:.2f}%<extra></extra>",
    ))
    # Endpoint label
    last = df.iloc[-1]
    fig.add_annotation(
        x=last["date"], y=last["value"],
        text=f"{last['value']:.1f}%",
        showarrow=False, xanchor="left", xshift=6,
        font=dict(color=theme.ACCENT, size=10, family=theme.FONT_FAMILY),
    )
    C._apply_layout(fig, "CBRT Policy Rate (One-Week Repo)", height=280)
    fig.update_yaxes(ticksuffix="%", tickformat=".0f")
    fig.update_xaxes(tickformat="%b %y")
    fig.update_layout(showlegend=False)

    first, last = df.iloc[0], df.iloc[-1]
    delta = last["value"] - first["value"]
    caption = (f"Policy rate at {last['value']:.1f}% "
               f"({delta:+.1f}pp since {first['date']:%b %Y}).")
    return C.chart_panel(fig, caption=caption)


def _panel_usdtry():
    df = evds.fetch_series("TP.DK.USD.A", "2024-01-01",
                           datetime.today().strftime("%Y-%m-%d"))
    if df.empty:
        return C.chart_panel(C._empty_fig(), caption="")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["value"], mode="lines",
        name="USD/TRY",
        line=dict(color="#7c3aed", width=2.4),
        hovertemplate="<b>USD/TRY</b><br>%{x|%d %b %Y}<br>" + "%{y:.3f}<extra></extra>",
    ))
    last = df.iloc[-1]
    fig.add_annotation(
        x=last["date"], y=last["value"],
        text=f"{last['value']:.2f}",
        showarrow=False, xanchor="left", xshift=6,
        font=dict(color="#7c3aed", size=10, family=theme.FONT_FAMILY),
    )
    C._apply_layout(fig, "USD/TRY — Buying Rate", height=280)
    fig.update_xaxes(tickformat="%b %y")
    fig.update_layout(showlegend=False)

    first, last = df.iloc[0], df.iloc[-1]
    chg = (last["value"] / first["value"] - 1) * 100
    caption = (f"USD/TRY at {last['value']:.2f} "
               f"({chg:+.1f}% since {first['date']:%b %Y}).")
    return C.chart_panel(fig, caption=caption)


# ---------------------------------------------------------------------------
def build_rates():
    return dbc.Container([
        html.Div(
            "Interest rates and key macro series from TCMB EVDS (weekly flow rates, "
            "sector-average, not adjusted for required-reserve cost).",
            style={
                "fontSize": "0.75rem", "color": theme.MUTED,
                "backgroundColor": "#f0f9ff", "border": "1px solid #bae6fd",
                "padding": "8px 12px", "borderRadius": "6px", "marginBottom": "14px",
            },
        ),
        C.section_header(
            "Lending & Funding Rates",
            "Weekly flow rates published by TCMB — headline indicator for monetary transmission.",
        ),
        dbc.Row([dbc.Col(_panel_tl_rates(), md=12)], className="g-3"),
        html.Div(style={"height": "8px"}),
        C.section_header(
            "Monetary & Currency Context",
            "Policy rate and the Lira exchange rate.",
        ),
        dbc.Row([
            dbc.Col(_panel_policy_rate(), md=6),
            dbc.Col(_panel_usdtry(), md=6),
        ], className="g-3"),
        html.Div(style={"height": "24px"}),
    ], fluid=True)
