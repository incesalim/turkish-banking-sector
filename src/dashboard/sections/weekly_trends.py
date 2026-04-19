"""Weekly Trends — BBVA-style nowcast charts built from BDDK weekly bulletin.

4-week and 13-week compound-annualized growth rates are the workhorses of
BBVA's Banking Sector Outlook; they surface turning points well before
monthly data does.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html
import dash_bootstrap_components as dbc

from src.dashboard import charts as C, weekly_ext as W, theme


# Monthly-code conventions (weekly data is already stored in monthly codes)
SECTOR = "10001"
PRIVATE = "10003"
STATE = "10004"
FOREIGN = "10005"
PARTICIP = "10006"
DEV_INV = "10007"
OWNERSHIP = [PRIVATE, STATE, FOREIGN, PARTICIP, DEV_INV]

# Key weekly items from BDDK's KiyaslamaJson chart IDs
ITEM = {
    "total_loans":     "1.0.1",
    "cons_cards":      "1.0.2",   # Consumer + Retail Cards
    "consumer":        "1.0.3",
    "housing":         "1.0.4",
    "auto":            "1.0.5",
    "gpl":             "1.0.6",
    "retail_cards":    "1.0.8",
    "sme_info":        "1.0.11",  # Bilgi (info-only)
    "commercial":      "1.0.12",  # Ticari ve Diğer
    "npl":             "2.0.1",
    "deposits":        "4.0.1",
    "demand_indiv":    "4.0.3",
    "time_indiv":      "4.0.4",
}


# ---------------------------------------------------------------------------
# Chart helpers specific to weekly trends
# ---------------------------------------------------------------------------
def _trend_from_weekly(df: pd.DataFrame, title: str, height: int = 280) -> go.Figure:
    """Wrap charts.zero_line_trend_chart for a weekly multi-bank df."""
    fig = C.zero_line_trend_chart(
        W.to_trend_format(df),
        title=title,
        bank_types=list(df["bank_type_code"].unique()) if "bank_type_code" in df.columns else None,
        height=height,
    )
    # weekly is dense — override x tick format
    fig.update_xaxes(tickformat="%b %y")
    return fig


def _single_line_growth(
    df: pd.DataFrame, title: str, color: str, height: int = 280
) -> go.Figure:
    """Single-series growth chart with zero line and endpoint label."""
    fig = go.Figure()
    if df is None or df.empty:
        return C._empty_fig()
    sub = df.sort_values("period_date")
    fig.add_trace(go.Scatter(
        x=sub["period_date"], y=sub["value"], mode="lines",
        line=dict(color=color, width=2.2),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>" + "%{y:.1f}%<extra></extra>",
        showlegend=False,
    ))
    last = sub.iloc[-1]
    fig.add_annotation(
        x=last["period_date"], y=last["value"],
        text=f"{last['value']:.1f}%", showarrow=False,
        xanchor="left", xshift=6,
        font=dict(color=color, size=10, family=theme.FONT_FAMILY),
    )
    fig.add_hline(y=0, line=dict(color=theme.MUTED, width=1, dash="dot"))
    C._apply_layout(fig, title, height=height)
    fig.update_yaxes(ticksuffix="%", tickformat=".0f")
    fig.update_xaxes(tickformat="%b %y")
    return fig


def _two_line_growth(
    df_a: pd.DataFrame, label_a: str, color_a: str,
    df_b: pd.DataFrame, label_b: str, color_b: str,
    title: str, height: int = 280,
) -> go.Figure:
    fig = go.Figure()
    for df, label, color in [(df_a, label_a, color_a), (df_b, label_b, color_b)]:
        if df is None or df.empty:
            continue
        sub = df.sort_values("period_date")
        fig.add_trace(go.Scatter(
            x=sub["period_date"], y=sub["value"], mode="lines",
            name=label, line=dict(color=color, width=2.2),
            hovertemplate=f"<b>{label}</b><br>%{{x|%d %b %Y}}<br>" + "%{y:.1f}%<extra></extra>",
        ))
        last = sub.iloc[-1]
        fig.add_annotation(
            x=last["period_date"], y=last["value"],
            text=f"{last['value']:.1f}%", showarrow=False,
            xanchor="left", xshift=6,
            font=dict(color=color, size=10, family=theme.FONT_FAMILY),
        )
    fig.add_hline(y=0, line=dict(color=theme.MUTED, width=1, dash="dot"))
    C._apply_layout(fig, title, height=height)
    fig.update_yaxes(ticksuffix="%", tickformat=".0f")
    fig.update_xaxes(tickformat="%b %y")
    return fig


def _caption_latest_vs_prev(df: pd.DataFrame, label: str) -> str:
    """'Latest 50.0%, 4w ago 48.2% (+1.8pp)'"""
    if df is None or df.empty:
        return ""
    sub = df.sort_values("period_date")
    if len(sub) < 5:
        return ""
    latest = sub.iloc[-1]
    prev = sub.iloc[-5]   # 4 weeks ago
    delta = latest["value"] - prev["value"]
    return (f"{label} at {latest['value']:.1f}% "
            f"({delta:+.1f}pp vs 4w ago, {latest['period_date']:%d %b %Y}).")


# ---------------------------------------------------------------------------
# Panel 1 — Total credit growth (4w & 13w trends)
# ---------------------------------------------------------------------------
def _panel_total_credit():
    base = W.get_series_multi_bank(ITEM["total_loans"],
                                    [SECTOR] + OWNERSHIP, "TOTAL")
    g4 = W.growth_annualized(base, 4)
    g13 = W.growth_annualized(base, 13)

    c_4w = C.chart_panel(
        _trend_from_weekly(g4, "Total Loan Growth — 4w Annualized (%)"),
        caption=_caption_latest_vs_prev(
            g4[g4.bank_type_code == SECTOR], "Sector 4w growth"),
    )
    c_13w = C.chart_panel(
        _trend_from_weekly(g13, "Total Loan Growth — 13w Annualized (%)"),
        caption=_caption_latest_vs_prev(
            g13[g13.bank_type_code == SECTOR], "Sector 13w growth"),
    )

    return html.Div([
        C.section_header(
            "Total Credit Growth — Weekly Nowcast",
            "Compound annualized 4-week and 13-week growth rates. Short-term "
            "trend turns up before monthly YoY moves.",
        ),
        dbc.Row([
            dbc.Col(c_4w, md=6),
            dbc.Col(c_13w, md=6),
        ], className="g-3"),
    ])


# ---------------------------------------------------------------------------
# Panel 2 — TL vs FX credit growth
# ---------------------------------------------------------------------------
def _panel_currency_growth():
    tl = W.get_series(ITEM["total_loans"], SECTOR, "TL")
    fx = W.get_series(ITEM["total_loans"], SECTOR, "FX")
    g4_tl = W.growth_annualized(tl, 4)
    g4_fx = W.growth_annualized(fx, 4)

    cur_chart = C.chart_panel(
        _two_line_growth(
            g4_tl, "TL", theme.BANK_COLORS[PRIVATE],
            g4_fx, "FX", theme.BANK_COLORS[STATE],
            "TL vs FX Credit Growth — 4w Annualized (%)"),
        caption="FX credit growth decelerates under BDDK caps; TL carries the "
                "headline expansion.",
    )

    # TL loans public vs private
    tl_mb = W.get_series_multi_bank(ITEM["total_loans"],
                                     [PRIVATE, STATE], "TL")
    g4_tl_mb = W.growth_annualized(tl_mb, 4)
    priv_pub_chart = C.chart_panel(
        _trend_from_weekly(g4_tl_mb, "TL Credit — Public vs Private (4w Ann., %)"),
        caption="Divergence between state and private banks on TL expansion.",
    )

    return html.Div([
        C.section_header(
            "Currency & Ownership Differentiators",
            "How the 4-week momentum splits across currency and ownership.",
        ),
        dbc.Row([
            dbc.Col(cur_chart, md=6),
            dbc.Col(priv_pub_chart, md=6),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Panel 3 — Consumer segment growth
# ---------------------------------------------------------------------------
def _panel_consumer_segments():
    segs = {
        "Housing": (ITEM["housing"], theme.CATEGORICAL[0]),
        "Auto": (ITEM["auto"], theme.CATEGORICAL[1]),
        "GPL": (ITEM["gpl"], theme.CATEGORICAL[2]),
        "Retail Cards": (ITEM["retail_cards"], theme.CATEGORICAL[3]),
    }
    fig = go.Figure()
    for label, (item_id, color) in segs.items():
        df = W.growth_annualized(W.get_series(item_id, SECTOR, "TOTAL"), 4)
        if df is None or df.empty:
            continue
        sub = df.sort_values("period_date")
        fig.add_trace(go.Scatter(
            x=sub["period_date"], y=sub["value"], mode="lines",
            name=label, line=dict(color=color, width=2.2),
            hovertemplate=f"<b>{label}</b><br>%{{x|%d %b %Y}}<br>" + "%{y:.1f}%<extra></extra>",
        ))
        last = sub.iloc[-1]
        fig.add_annotation(
            x=last["period_date"], y=last["value"],
            text=f"{last['value']:.0f}%", showarrow=False,
            xanchor="left", xshift=6,
            font=dict(color=color, size=10, family=theme.FONT_FAMILY),
        )
    fig.add_hline(y=0, line=dict(color=theme.MUTED, width=1, dash="dot"))
    C._apply_layout(fig, "Consumer Segment Growth — 4w Annualized (%)", height=320)
    fig.update_yaxes(ticksuffix="%", tickformat=".0f")
    fig.update_xaxes(tickformat="%b %y")

    # GPL public vs private
    gpl_mb = W.get_series_multi_bank(ITEM["gpl"], [PRIVATE, STATE], "TOTAL")
    gpl_g = W.growth_annualized(gpl_mb, 4)
    gpl_chart = C.chart_panel(
        _trend_from_weekly(gpl_g, "GPL Growth — Public vs Private (4w Ann.)"),
        caption="Private banks are typically more active in non-capped GPL growth.",
    )

    return html.Div([
        C.section_header(
            "Consumer Segments",
            "Non-capped items (cards, GPL) usually lead consumer credit.",
        ),
        dbc.Row([
            dbc.Col(C.chart_panel(
                fig,
                caption="Credit cards and GPL typically outpace housing and auto."
            ), md=7),
            dbc.Col(gpl_chart, md=5),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Panel 4 — SME vs Commercial
# ---------------------------------------------------------------------------
def _panel_sme_commercial():
    sme = W.growth_annualized(W.get_series(ITEM["sme_info"], SECTOR, "TOTAL"), 4)
    com = W.growth_annualized(W.get_series(ITEM["commercial"], SECTOR, "TOTAL"), 4)

    chart = C.chart_panel(
        _two_line_growth(
            sme, "SME (info)", theme.BANK_COLORS[PARTICIP],
            com, "Commercial & Other", theme.BANK_COLORS[DEV_INV],
            "SME vs Commercial Credit — 4w Annualized (%)", height=300),
        caption=_caption_latest_vs_prev(sme, "Sector SME 4w growth"),
    )

    # SME TL public vs private
    sme_mb = W.get_series_multi_bank(ITEM["sme_info"],
                                      [PRIVATE, STATE], "TL")
    sme_pp = W.growth_annualized(sme_mb, 4)
    sme_chart = C.chart_panel(
        _trend_from_weekly(sme_pp, "SME TL Growth — Public vs Private (4w Ann.)"),
        caption="Public banks historically push TL SME lending faster.",
    )

    return html.Div([
        C.section_header(
            "SME & Commercial",
            "SME growth and its public-vs-private differentiation.",
        ),
        dbc.Row([
            dbc.Col(chart, md=6),
            dbc.Col(sme_chart, md=6),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Panel 5 — Deposit growth (TL vs FX; time vs demand)
# ---------------------------------------------------------------------------
def _panel_deposits():
    tl = W.growth_annualized(W.get_series(ITEM["deposits"], SECTOR, "TL"), 4)
    fx = W.growth_annualized(W.get_series(ITEM["deposits"], SECTOR, "FX"), 4)
    depo_chart = C.chart_panel(
        _two_line_growth(
            tl, "TL Deposits", theme.BANK_COLORS[PRIVATE],
            fx, "FX Deposits", theme.BANK_COLORS[STATE],
            "Deposit Growth — TL vs FX (4w Annualized, %)"),
        caption="Residents' TL-tilt shows as TL deposits outpacing FX.",
    )

    # Individuals: demand vs time
    demand = W.growth_annualized(W.get_series(ITEM["demand_indiv"], SECTOR, "TOTAL"), 4)
    time_d = W.growth_annualized(W.get_series(ITEM["time_indiv"], SECTOR, "TOTAL"), 4)
    split_chart = C.chart_panel(
        _two_line_growth(
            demand, "Demand (individuals)", theme.CATEGORICAL[0],
            time_d, "Time (individuals)", theme.CATEGORICAL[1],
            "Individual Deposits — Demand vs Time (4w Ann., %)"),
        caption="Time deposits dominate when rates are high; demand drifts in low-rate regimes.",
    )

    return html.Div([
        C.section_header(
            "Deposits",
            "Funding-side momentum. TL vs FX and maturity mix tell the "
            "dollarization story.",
        ),
        dbc.Row([
            dbc.Col(depo_chart, md=6),
            dbc.Col(split_chart, md=6),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Panel 6 — NPL stock momentum
# ---------------------------------------------------------------------------
def _panel_npl():
    npl = W.get_series_multi_bank(ITEM["npl"],
                                   [SECTOR, PRIVATE, STATE], "TOTAL")
    g13 = W.growth_annualized(npl, 13)
    chart = C.chart_panel(
        _trend_from_weekly(g13, "Gross NPL Stock — 13w Annualized Growth (%)",
                            height=300),
        caption="NPL stock moves more slowly than credit — 13w is the more "
                "informative horizon.",
    )

    # Also level (sector)
    npl_lvl = W.get_series(ITEM["npl"], SECTOR, "TOTAL")
    fig_lvl = go.Figure()
    if not npl_lvl.empty:
        sub = npl_lvl.sort_values("period_date")
        fig_lvl.add_trace(go.Scatter(
            x=sub["period_date"], y=sub["value"], mode="lines",
            line=dict(color=theme.BANK_COLORS[STATE], width=2.2),
            hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:,.0f} M TL<extra></extra>",
            showlegend=False,
        ))
        last = sub.iloc[-1]
        fig_lvl.add_annotation(
            x=last["period_date"], y=last["value"],
            text=C.fmt_tl(last["value"]), showarrow=False,
            xanchor="left", xshift=6,
            font=dict(color=theme.BANK_COLORS[STATE], size=10, family=theme.FONT_FAMILY),
        )
    C._apply_layout(fig_lvl, "Gross NPL Stock — Sector Level", height=300)
    fig_lvl.update_yaxes(**C._tl_tick_config(float(npl_lvl["value"].max()) if not npl_lvl.empty else 0))
    fig_lvl.update_xaxes(tickformat="%b %y")

    lvl_chart = C.chart_panel(
        fig_lvl,
        caption=f"Latest sector NPL stock: {C.fmt_tl(float(npl_lvl.iloc[-1]['value'])) if not npl_lvl.empty else '—'}.",
    )

    return html.Div([
        C.section_header(
            "NPL Momentum",
            "NPL stock momentum — steady rise in credit cards and GPL is the "
            "visible trend; restructurings temper it.",
        ),
        dbc.Row([
            dbc.Col(chart, md=7),
            dbc.Col(lvl_chart, md=5),
        ], className="g-3"),
    ], className="mt-4")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build_weekly_trends():
    return dbc.Container([
        html.Div(
            "All growth rates below are compound-annualized from weekly "
            "BDDK data. 4-week trends act as a nowcast; 13-week smooths "
            "through noise.",
            style={
                "fontSize": "0.75rem", "color": theme.MUTED,
                "backgroundColor": "#f0f9ff", "border": "1px solid #bae6fd",
                "padding": "8px 12px", "borderRadius": "6px", "marginBottom": "14px",
            },
        ),
        _panel_total_credit(),
        _panel_currency_growth(),
        _panel_consumer_segments(),
        _panel_sme_commercial(),
        _panel_deposits(),
        _panel_npl(),
        html.Div(style={"height": "24px"}),
    ], fluid=True)
