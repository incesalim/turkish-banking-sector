"""Credit section — BBVA-style credit developments:
growth, currency breakdown, segment mix, public vs private differentiators.
"""

from __future__ import annotations

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc

from src.analytics import data_store
from src.dashboard import charts as C, metrics_ext as M, theme


SECTOR = "10001"
PRIVATE = "10003"
STATE = "10004"
FOREIGN = "10005"
PARTICIP = "10006"
DEV_INV = "10007"
OWNERSHIP = [PRIVATE, STATE, FOREIGN, PARTICIP, DEV_INV]


# ---------------------------------------------------------------------------
# Panel 1 — Total Credit Growth
# ---------------------------------------------------------------------------
def _panel_total_growth():
    yoy_df = data_store.get("loan_growth_yoy")
    # MoM growth of total loans
    mom_df = M.mom_growth(data_store.get("total_loans"))

    yoy_chart = C.chart_panel(
        C.zero_line_trend_chart(yoy_df, "Loan Growth — YoY (%)",
                                bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_growth(yoy_df, "Sector loan growth YoY", SECTOR),
    )
    mom_chart = C.chart_panel(
        C.zero_line_trend_chart(mom_df, "Loan Growth — MoM (%)",
                                bank_types=[SECTOR, PRIVATE, STATE], height=280),
        caption=C.caption_growth(mom_df, "Sector loan growth MoM", SECTOR),
    )
    bar_chart = C.chart_panel(
        C.bar_chart_by_bank(M.latest_snapshot(yoy_df),
                            "YoY Growth by Bank Type", value_format="pct",
                            height=280),
        caption=C.caption_comparison(M.latest_snapshot(yoy_df),
                                      "YoY loan growth", "pct"),
    )

    return html.Div([
        C.section_header(
            "Credit Developments",
            "Total loan growth — cross-sectional and time-series views.",
        ),
        dbc.Row([
            dbc.Col(yoy_chart, md=4),
            dbc.Col(mom_chart, md=4),
            dbc.Col(bar_chart, md=4),
        ], className="g-3"),
    ])


# ---------------------------------------------------------------------------
# Panel 2 — TL vs FX Credit
# ---------------------------------------------------------------------------
def _panel_currency():
    tl = data_store.get("total_loans_tl")
    fx = data_store.get("total_loans_fx")
    fx_share = data_store.get("fx_loan_share")

    tl_chart = C.chart_panel(
        C.trend_chart(tl, "TL Loans — Level", value_format="tl",
                      bank_types=[SECTOR], height=260),
        caption=C.caption_level(tl, "TL loans", SECTOR),
    )
    fx_chart = C.chart_panel(
        C.trend_chart(fx, "FX Loans — Level (in TL equivalent)",
                      value_format="tl",
                      bank_types=[SECTOR], height=260),
        caption=C.caption_level(fx, "FX loans", SECTOR),
    )
    share_chart = C.chart_panel(
        C.trend_chart(fx_share, "FX Share of Total Loans (%)",
                      value_format="pct",
                      bank_types=[SECTOR] + OWNERSHIP, height=260),
        caption=C.caption_comparison(M.latest_snapshot(fx_share),
                                      "FX share", "pct"),
    )

    return html.Div([
        C.section_header(
            "Currency Breakdown",
            "FX exposure stays moderate; TL loans drive sector growth.",
        ),
        dbc.Row([
            dbc.Col(tl_chart, md=4),
            dbc.Col(fx_chart, md=4),
            dbc.Col(share_chart, md=4),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Panel 3 — Consumer Credit Breakdown
# ---------------------------------------------------------------------------
def _panel_consumer():
    mix = M.get_consumer_mix(SECTOR)
    # stacked-area composition
    comp_fig = C.stacked_area(mix, "Consumer Credit Composition (Sector)",
                              height=300, value_format="tl")

    # YoY growth by consumer segment
    import plotly.graph_objects as go
    fig = go.Figure()
    segments = [
        ("Housing", data_store.get("consumer_housing")),
        ("Auto", data_store.get("consumer_auto")),
        ("GPL", data_store.get("consumer_gpl")),
        ("Retail Cards", data_store.get("retail_credit_cards")),
    ]
    for i, (label, df) in enumerate(segments):
        yoy = M.yoy_growth(df) if df is not None and not df.empty else None
        if yoy is None or yoy.empty:
            continue
        sub = yoy[yoy["bank_type_code"] == SECTOR].sort_values("period")
        fig.add_trace(go.Scatter(
            x=sub["period"], y=sub["value"], mode="lines",
            name=label,
            line=dict(color=theme.CATEGORICAL[i % len(theme.CATEGORICAL)], width=2.2),
            hovertemplate=f"<b>{label}</b><br>%{{x|%b %Y}}<br>" + "%{y:.1f}%<extra></extra>",
        ))
    fig.add_hline(y=0, line=dict(color=theme.MUTED, width=1, dash="dot"))
    C._apply_layout(fig, "Consumer Segment Growth (YoY)", height=300)
    fig.update_yaxes(ticksuffix="%", tickformat=".0f")
    fig.update_xaxes(tickformat="%b %y")

    # Cards split (retail vs corporate)
    retail_cc = data_store.get("retail_credit_cards")
    corp_cc = data_store.get("corporate_credit_cards")
    cards_fig = go.Figure()
    for df, label, color in [
        (retail_cc, "Retail Cards", theme.BANK_COLORS["10003"]),
        (corp_cc, "Corporate Cards", theme.BANK_COLORS["10004"]),
    ]:
        if df is None or df.empty:
            continue
        sub = df[df["bank_type_code"] == SECTOR].sort_values("period")
        cards_fig.add_trace(go.Scatter(
            x=sub["period"], y=sub["value"], mode="lines",
            name=label, line=dict(color=color, width=2.2),
            hovertemplate=f"<b>{label}</b><br>%{{x|%b %Y}}<br>" + "%{y:,.0f} M TL<extra></extra>",
        ))
    C._apply_layout(cards_fig, "Credit Cards — Retail vs Corporate", height=300)
    max_v = max(
        retail_cc[retail_cc["bank_type_code"] == SECTOR]["value"].max() if retail_cc is not None and not retail_cc.empty else 0,
        corp_cc[corp_cc["bank_type_code"] == SECTOR]["value"].max() if corp_cc is not None and not corp_cc.empty else 0,
    )
    cards_fig.update_yaxes(**C._tl_tick_config(float(max_v or 0)))
    cards_fig.update_xaxes(tickformat="%b %y")

    return html.Div([
        C.section_header(
            "Consumer Credit",
            "Non-capped items (credit cards, GPL) drive the headline growth.",
        ),
        dbc.Row([
            dbc.Col(C.chart_panel(comp_fig,
                                   caption="Retail cards and GPL dominate consumer credit."), md=4),
            dbc.Col(C.chart_panel(fig,
                                   caption="Credit cards lead; auto lending lags."), md=4),
            dbc.Col(C.chart_panel(cards_fig,
                                   caption="Retail cards outpace corporate in absolute size."), md=4),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Panel 4 — SME & Commercial
# ---------------------------------------------------------------------------
def _panel_sme_commercial():
    sme = M.get_sme_loans([SECTOR] + OWNERSHIP)
    sme_yoy = M.yoy_growth(sme)
    sme_breakdown = M.get_sme_breakdown(SECTOR)

    sme_level = C.chart_panel(
        C.trend_chart(sme, "SME Loans — Level (Sector)",
                      value_format="tl", bank_types=[SECTOR], height=280),
        caption=C.caption_level(sme, "SME loans", SECTOR),
    )
    sme_growth = C.chart_panel(
        C.zero_line_trend_chart(sme_yoy, "SME Loan Growth YoY (%)",
                                bank_types=[SECTOR, PRIVATE, STATE], height=280),
        caption=C.caption_growth(sme_yoy, "SME growth", SECTOR),
    )
    sme_mix = C.chart_panel(
        C.stacked_area(sme_breakdown, "SME Mix — Micro / Small / Medium",
                       height=280, value_format="tl"),
        caption="Mid-sized enterprises remain the largest SME sub-segment.",
    )

    return html.Div([
        C.section_header(
            "SME & Commercial",
            "SME exposure, size mix, and public-vs-private differentiation.",
        ),
        dbc.Row([
            dbc.Col(sme_level, md=4),
            dbc.Col(sme_growth, md=4),
            dbc.Col(sme_mix, md=4),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Panel 5 — Public vs Private differentiator
# ---------------------------------------------------------------------------
def _panel_public_vs_private():
    """BBVA's signature: two-line comparison focused on the public-private gap."""
    yoy = data_store.get("loan_growth_yoy")
    tl_yoy = M.yoy_growth(data_store.get("total_loans_tl"))

    total_chart = C.chart_panel(
        C.zero_line_trend_chart(
            yoy[yoy["bank_type_code"].isin([PRIVATE, STATE])],
            "Total Credit YoY — Public vs Private", height=300,
        ),
        caption=C.caption_comparison(
            M.latest_snapshot(yoy[yoy["bank_type_code"].isin([PRIVATE, STATE])]),
            "YoY growth", "pct",
        ),
    )
    tl_chart = C.chart_panel(
        C.zero_line_trend_chart(
            tl_yoy[tl_yoy["bank_type_code"].isin([PRIVATE, STATE])],
            "TL Loans YoY — Public vs Private", height=300,
        ),
        caption=C.caption_comparison(
            M.latest_snapshot(tl_yoy[tl_yoy["bank_type_code"].isin([PRIVATE, STATE])]),
            "TL loan growth", "pct",
        ),
    )

    return html.Div([
        C.section_header(
            "Public vs Private",
            "Ownership differential in credit growth — the clearest sector signal.",
        ),
        dbc.Row([
            dbc.Col(total_chart, md=6),
            dbc.Col(tl_chart, md=6),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build_credit():
    return dbc.Container([
        _panel_total_growth(),
        _panel_currency(),
        _panel_consumer(),
        _panel_sme_commercial(),
        _panel_public_vs_private(),
        html.Div(style={"height": "24px"}),
    ], fluid=True)
