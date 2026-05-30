"""
Centralized color constants for Python-side rendering (Plotly, dynamic HTML).
CSS-side colors live in static/theme.css as CSS custom properties.
"""

# Semantic
PROFIT = "#059669"
LOSS = "#f43f5e"
PROFIT_BG = "#ecfdf5"
LOSS_BG = "#fff1f2"

# Text hierarchy
TEXT_PRIMARY = "#292524"
TEXT_SECONDARY = "#78716c"
TEXT_MUTED = "#a8a29e"
TEXT_FAINT = "#d6d3d1"

# Surface & border
BG = "#fafaf9"
SURFACE = "#ffffff"
SURFACE_ALT = "#f5f5f4"
BORDER = "#e7e5e4"
BORDER_SOFT = "#f0eeec"

# Accent
ACCENT = "#4f46e5"

# Broker brand
BROKER_COLORS = {
    "IBKR": "#f97316",
    "Schwab": "#3b82f6",
    "Firstrade": "#10b981",
    "Manual": "#8b5cf6",
}
BROKER_DEFAULT = "#6b7280"

# Chart palette (16 colors, distinct on cream background)
CHART_COLORS = [
    "#4f46e5", "#7c3aed", "#2563eb", "#0891b2",
    "#059669", "#65a30d", "#ca8a04", "#ea580c",
    "#dc2626", "#e11d48", "#9333ea", "#6366f1",
    "#14b8a6", "#f59e0b", "#3b82f6", "#8b5cf6",
]

# Font family (matches CSS --font-sans)
FONT_FAMILY = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"


def pnl_color(value: float) -> str:
    """Return profit/loss hex color based on sign."""
    return PROFIT if value >= 0 else LOSS
