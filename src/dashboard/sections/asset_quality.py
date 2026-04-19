"""Asset Quality — NPL levels, ratio, coverage, segment breakdown."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html
import dash_bootstrap_components as dbc

from src.analytics import data_store
from src.dashboard import charts as C, metrics_ext as M, theme


SECTOR = "10001"
OWNERSHIP = ["10003", "10004", "10005", "10006", "10007"]


def _panel_npl_ratio():
    npl = M.ratio_npl([SECTOR] + OWNERSHIP)

    trend = C.chart_panel(
        C.zero_line_trend_chart(npl, "NPL Ratio (%) — Trend",
                                bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_comparison(M.latest_snapshot(npl),
                                      "NPL ratio", "pct"),
    )
    bar = C.chart_panel(
        C.bar_chart_by_bank(M.latest_snapshot(npl),
                            "NPL Ratio by Bank Type — Latest",
                            value_format="pct", height=280),
        caption="State banks sit well below sector average; "
                "participation and dev-inv typically carry the highest.",
    )

    return html.Div([
        C.section_header(
            "Non-Performing Loans",
            "Gross NPL / cash loans. BDDK-published (Table 15).",
        ),
        dbc.Row([
            dbc.Col(trend, md=8),
            dbc.Col(bar, md=4),
        ], className="g-3"),
    ])


def _panel_coverage_npl_level():
    cov = M.ratio_coverage([SECTOR] + OWNERSHIP)
    npl_amount = M.get_balance_item("%Takipteki Alacak%", [SECTOR])

    cov_chart = C.chart_panel(
        C.trend_chart(cov, "Provisions / Gross NPL (%)",
                      value_format="pct",
                      bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_comparison(M.latest_snapshot(cov),
                                      "Coverage", "pct"),
    )
    level_chart = C.chart_panel(
        C.trend_chart(npl_amount, "Gross NPL — Level",
                      value_format="tl", bank_types=[SECTOR], height=280),
        caption=C.caption_level(npl_amount, "Gross NPL", SECTOR),
    )

    return html.Div([
        C.section_header(
            "Provisioning & NPL Stock",
            "Coverage (loan-loss reserves over gross NPL) and absolute NPL level.",
        ),
        dbc.Row([
            dbc.Col(cov_chart, md=7),
            dbc.Col(level_chart, md=5),
        ], className="g-3"),
    ], className="mt-4")


def _panel_consumer_npl():
    segs = M.get_consumer_npl_segments(SECTOR)
    # Stacked area composition
    comp = C.stacked_area(segs, "Consumer NPL — Composition (Sector)",
                          height=280, value_format="tl")

    # YoY growth per segment
    fig = go.Figure()
    for i, (label, df) in enumerate(segs.items()):
        if df is None or df.empty:
            continue
        yoy = M.yoy_growth(df)
        sub = yoy[yoy["bank_type_code"] == SECTOR].sort_values("period")
        fig.add_trace(go.Scatter(
            x=sub["period"], y=sub["value"], mode="lines",
            name=label,
            line=dict(color=theme.CATEGORICAL[i % len(theme.CATEGORICAL)], width=2.2),
            hovertemplate=f"<b>{label}</b><br>%{{x|%b %Y}}<br>" + "%{y:.1f}%<extra></extra>",
        ))
    fig.add_hline(y=0, line=dict(color=theme.MUTED, width=1, dash="dot"))
    C._apply_layout(fig, "Consumer NPL Growth YoY (%)", height=280)
    fig.update_yaxes(ticksuffix="%", tickformat=".0f")
    fig.update_xaxes(tickformat="%b %y")

    return html.Div([
        C.section_header(
            "Consumer NPL Breakdown",
            "Where deterioration is concentrated: credit cards and GPL.",
        ),
        dbc.Row([
            dbc.Col(C.chart_panel(
                comp,
                caption="Retail credit cards and GPL dominate consumer NPL stock.",
            ), md=6),
            dbc.Col(C.chart_panel(
                fig,
                caption="Credit-card delinquencies grow fastest; "
                        "housing NPL remains negligible.",
            ), md=6),
        ], className="g-3"),
    ], className="mt-4")


def build_asset_quality():
    return dbc.Container([
        _panel_npl_ratio(),
        _panel_coverage_npl_level(),
        _panel_consumer_npl(),
        html.Div(style={"height": "24px"}),
    ], fluid=True)
