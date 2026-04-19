"""
Formatting utilities for BDDK Banking Analytics Dashboard
"""

from typing import Union


def format_currency(value: float, decimals: int = 1, suffix: str = 'TL') -> str:
    """Format currency values with Turkish Lira notation

    Args:
        value: Numeric value
        decimals: Number of decimal places
        suffix: Currency suffix

    Returns:
        Formatted string (e.g., "12.5T TL")
    """
    if value == 0:
        return f"0 {suffix}"

    # Convert to millions for display
    abs_value = abs(value)

    if abs_value >= 1_000_000:  # Trillions
        formatted = f"{value / 1_000_000:.{decimals}f}T"
    elif abs_value >= 1_000:  # Billions
        formatted = f"{value / 1_000:.{decimals}f}B"
    else:  # Millions
        formatted = f"{value:.{decimals}f}M"

    return f"{formatted} {suffix}"


def format_percentage(value: float, decimals: int = 1, include_sign: bool = False) -> str:
    """Format percentage values

    Args:
        value: Percentage value (as decimal or percentage)
        decimals: Number of decimal places
        include_sign: Whether to include + for positive values

    Returns:
        Formatted string (e.g., "+5.2%" or "2.8%")
    """
    if include_sign and value > 0:
        return f"+{value:.{decimals}f}%"
    return f"{value:.{decimals}f}%"


def format_number(value: float, decimals: int = 0, thousands_sep: str = ',') -> str:
    """Format number with thousands separator

    Args:
        value: Numeric value
        decimals: Number of decimal places
        thousands_sep: Thousands separator

    Returns:
        Formatted string (e.g., "1,234,567")
    """
    if decimals == 0:
        return f"{int(value):,}".replace(',', thousands_sep)
    return f"{value:,.{decimals}f}".replace(',', thousands_sep)


def format_date(year: int, month: int, format_str: str = 'short') -> str:
    """Format year and month as date string

    Args:
        year: Year
        month: Month (1-12)
        format_str: Format type ('short', 'long', 'full')

    Returns:
        Formatted date string
    """
    months_short = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    months_long = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']

    if format_str == 'short':
        return f"{months_short[month]} {year}"
    elif format_str == 'long':
        return f"{months_long[month]} {year}"
    elif format_str == 'full':
        return f"{months_long[month]} {year}"
    else:
        return f"{year}-{month:02d}"


def calculate_change(current: float, previous: float) -> tuple:
    """Calculate absolute and percentage change

    Args:
        current: Current value
        previous: Previous value

    Returns:
        Tuple of (absolute_change, percentage_change)
    """
    if previous == 0:
        return (current, 0)

    absolute_change = current - previous
    percentage_change = (absolute_change / previous) * 100

    return (absolute_change, percentage_change)


def get_change_indicator(value: float) -> str:
    """Get arrow indicator for change

    Args:
        value: Change value

    Returns:
        Arrow emoji (↗, ↘, →)
    """
    if value > 0.1:
        return "↗"
    elif value < -0.1:
        return "↘"
    else:
        return "→"


def get_change_color(value: float, inverse: bool = False) -> str:
    """Get color for change value

    Args:
        value: Change value
        inverse: If True, positive is red (for NPL, etc.)

    Returns:
        Color name ('success', 'danger', 'secondary')
    """
    if inverse:
        if value > 0:
            return "danger"
        elif value < 0:
            return "success"
    else:
        if value > 0:
            return "success"
        elif value < 0:
            return "danger"

    return "secondary"
