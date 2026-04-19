"""Profitability — ROE / ROA / NIM / cost efficiency.

BDDK Table 15 publishes income-based ratios as year-to-date (cumulative
Jan..month). For readability we annualize linearly (value × 12 / month),
which assumes roughly even monthly accrual. December values are unchanged.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import html
import dash_bootstrap_components as dbc

from src.analytics import data_store
from src.dashboard import charts as C, metrics_ext as M, theme


SECTOR = "10001"
OWNERSHIP = ["10003", "10004", "10005", "10006", "10007"]


def _panel_roe_roa():
    roe = M.annualize_ytd(M.ratio_roe_ytd([SECTOR] + OWNERSHIP))
    roa = M.annualize_ytd(M.ratio_roa_ytd([SECTOR] + OWNERSHIP))

    roe_chart = C.chart_panel(
        C.zero_line_trend_chart(roe, "ROE — Annualized (%)",
                                bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_comparison(M.latest_snapshot(roe),
                                      "ROE", "pct"),
    )
    roa_chart = C.chart_panel(
        C.zero_line_trend_chart(roa, "ROA — Annualized (%)",
                                bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_comparison(M.latest_snapshot(roa),
                                      "ROA", "pct"),
    )

    return html.Div([
        C.section_header(
            "Returns — Annualized",
            "Return on equity and assets, YTD values scaled to annual.",
        ),
        dbc.Row([
            dbc.Col(roe_chart, md=6),
            dbc.Col(roa_chart, md=6),
        ], className="g-3"),
    ])


def _panel_margin():
    nim = M.annualize_ytd(M.ratio_nim_ytd([SECTOR] + OWNERSHIP))
    interest_income = M.annualize_ytd(M.get_published_ratio(
        "Toplam Faiz Gelirleri / Faiz Getirili Aktifler Ortalaması%",
        bank_types=[SECTOR] + OWNERSHIP,
    ))
    interest_cost = M.annualize_ytd(M.get_published_ratio(
        "Toplam Faiz Giderleri / Faiz Maliyetli Pasifler Ortalaması%",
        bank_types=[SECTOR] + OWNERSHIP,
    ))

    nim_chart = C.chart_panel(
        C.zero_line_trend_chart(nim, "Net Interest Margin — Annualized (%)",
                                bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_comparison(M.latest_snapshot(nim),
                                      "NIM", "pct"),
    )

    # Spread = interest yield - interest cost (both annualized)
    spread = pd.merge(
        interest_income[["period", "bank_type_code", "bank_type", "value"]],
        interest_cost[["period", "bank_type_code", "value"]],
        on=["period", "bank_type_code"], suffixes=("_yld", "_cost"),
    )
    spread["value"] = spread["value_yld"] - spread["value_cost"]
    spread["year"] = spread["period"].dt.year
    spread["month"] = spread["period"].dt.month

    spread_chart = C.chart_panel(
        C.zero_line_trend_chart(spread, "Interest Yield − Cost (pp, annualized)",
                                bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption="Positive = earning more on assets than paying on funding.",
    )

    return html.Div([
        C.section_header(
            "Margins",
            "Net interest margin and yield-cost spread (annualized from Table 15 YTD).",
        ),
        dbc.Row([
            dbc.Col(nim_chart, md=6),
            dbc.Col(spread_chart, md=6),
        ], className="g-3"),
    ], className="mt-4")


def _panel_efficiency():
    # OPEX is a flow-over-stock ratio (YTD) → annualize.
    # Fees/Total Income and NI-income/NI-expense are ratios of flows within
    # the same YTD window → already comparable across months without rescaling.
    opex = M.annualize_ytd(M.get_published_ratio(
        "İşletme Giderleri / Ortalama Toplam Aktifler%",
        bank_types=[SECTOR] + OWNERSHIP,
    ))
    fees_ratio = M.get_published_ratio(
        "Ücret, Komisyon ve Bankacılık Hizmetleri Gelirleri / Toplam Gelirler%",
        bank_types=[SECTOR] + OWNERSHIP,
    )
    non_interest_cover = M.get_published_ratio(
        "Faiz Dışı Gelirler / Faiz Dışı Giderler%",
        bank_types=[SECTOR] + OWNERSHIP,
    )

    opex_chart = C.chart_panel(
        C.trend_chart(opex, "OPEX / Avg Assets (annualized %)",
                      value_format="pct",
                      bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_comparison(M.latest_snapshot(opex),
                                      "OPEX intensity", "pct"),
    )
    fees_chart = C.chart_panel(
        C.trend_chart(fees_ratio,
                      "Fees & Commissions / Total Income (%)",
                      value_format="pct",
                      bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption=C.caption_comparison(M.latest_snapshot(fees_ratio),
                                      "Fee income share", "pct"),
    )
    cover_chart = C.chart_panel(
        C.trend_chart(non_interest_cover,
                      "Non-Interest Income / Non-Interest Expense (%)",
                      value_format="pct",
                      bank_types=[SECTOR] + OWNERSHIP, height=280),
        caption="Above 100% = non-interest income covers OPEX (+ other fee-driven items).",
    )

    return html.Div([
        C.section_header(
            "Cost Efficiency & Non-Interest Income",
            "Operating cost intensity and fee-driven income contribution.",
        ),
        dbc.Row([
            dbc.Col(opex_chart, md=4),
            dbc.Col(fees_chart, md=4),
            dbc.Col(cover_chart, md=4),
        ], className="g-3"),
    ], className="mt-4")


def build_profitability():
    return dbc.Container([
        html.Div(
            "Income-based ratios from BDDK Table 15 are published year-to-date. "
            "Values below are annualized (YTD × 12/month), assuming even "
            "monthly accrual. December values are unchanged.",
            style={
                "fontSize": "0.75rem", "color": theme.MUTED,
                "backgroundColor": "#fffbeb", "border": f"1px solid #fcd34d",
                "padding": "8px 12px", "borderRadius": "6px", "marginBottom": "14px",
            },
        ),
        _panel_roe_roa(),
        _panel_margin(),
        _panel_efficiency(),
        html.Div(style={"height": "24px"}),
    ], fluid=True)
