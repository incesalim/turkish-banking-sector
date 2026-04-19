"""Dashboard theme: colors, fonts, constants."""

# ---------------------------------------------------------------------------
# Brand / chrome
# ---------------------------------------------------------------------------
HEADER_BG = "#0f172a"          # slate-900, deep neutral
HEADER_FG = "#f1f5f9"          # slate-100
ACCENT = "#0ea5e9"             # sky-500 for highlights
TEXT = "#0f172a"
MUTED = "#64748b"              # slate-500
BG = "#f8fafc"                 # slate-50
CARD_BG = "#ffffff"
BORDER = "#e2e8f0"             # slate-200
GRID = "#eef2f7"               # even lighter for plot gridlines

# ---------------------------------------------------------------------------
# Direction semantics for KPI deltas
# ---------------------------------------------------------------------------
# color meaning: green = good, red = bad, gray = neutral
POS_COLOR = "#059669"          # emerald-600
NEG_COLOR = "#dc2626"          # red-600
NEUTRAL_COLOR = "#64748b"

# ---------------------------------------------------------------------------
# Bank-type palette
# Sector is neutral gray (baseline). Ownership types get saturated hues so
# "public vs private" comparisons pop. Participation / Dev&Inv get secondary.
# ---------------------------------------------------------------------------
BANK_COLORS = {
    "10001": "#475569",  # Sector — slate-600 (neutral anchor)
    "10003": "#2563eb",  # Private Deposit — blue-600
    "10004": "#dc2626",  # State Deposit  — red-600
    "10005": "#f59e0b",  # Foreign Deposit — amber-500
    "10006": "#059669",  # Participation  — emerald-600
    "10007": "#7c3aed",  # Dev & Investment — violet-600
    # Ownership cross-cuts (used rarely)
    "10008": "#2563eb",
    "10009": "#dc2626",
    "10010": "#f59e0b",
}

BANK_SHORT = {
    "Sector": "Sector",
    "Private Deposit Banks": "Private",
    "State Deposit Banks": "State",
    "Foreign Deposit Banks": "Foreign",
    "Participation Banks": "Participation",
    "Dev & Investment Banks": "Dev & Inv",
}

# Categorical palette for segment breakdowns (consumer sub-types etc.)
CATEGORICAL = [
    "#2563eb", "#059669", "#f59e0b", "#7c3aed",
    "#dc2626", "#0ea5e9", "#ec4899", "#64748b",
]

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"

# ---------------------------------------------------------------------------
# Plotly layout defaults (used via apply_layout() in charts.py)
# ---------------------------------------------------------------------------
PLOTLY_LAYOUT_DEFAULTS = dict(
    font=dict(family=FONT_FAMILY, size=12, color=TEXT),
    plot_bgcolor=CARD_BG,
    paper_bgcolor=CARD_BG,
    margin=dict(l=56, r=56, t=48, b=48),
    hoverlabel=dict(
        bgcolor="#1e293b",
        bordercolor="#1e293b",
        font=dict(color="#f1f5f9", family=FONT_FAMILY, size=11),
    ),
    legend=dict(
        orientation="h",
        yanchor="top", y=-0.18, xanchor="center", x=0.5,
        font=dict(size=11, color=MUTED),
    ),
)

# Graph config applied to every dcc.Graph
GRAPH_CONFIG = {
    "displaylogo": False,
    "displayModeBar": False,   # cleaner BBVA-style pages
}
