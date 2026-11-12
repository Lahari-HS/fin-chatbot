"""
formatting.py — INR number formatting and markdown table helpers.

All functions are pure (no I/O, no side effects).
"""

from __future__ import annotations

import sys
import os

# Allow running from project root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CURRENCY_SYMBOL


def format_inr(amount: float, symbol: str = CURRENCY_SYMBOL) -> str:
    """
    Format a number in Indian number system (lakh / crore notation).

    Examples
    --------
    >>> format_inr(1500)
    '₹1,500'
    >>> format_inr(150000)
    '₹1,50,000'
    >>> format_inr(10000000)
    '₹1,00,00,000'
    >>> format_inr(1_50_00_000)
    '₹1,50,00,000'
    """
    if not isinstance(amount, (int, float)):
        raise TypeError(f"Expected a number, got {type(amount).__name__}")

    negative = amount < 0
    amount = abs(amount)

    # Split into integer and decimal parts
    int_part = int(amount)
    dec_part = round(amount - int_part, 2)

    # Indian grouping: last 3 digits, then groups of 2
    s = str(int_part)
    if len(s) <= 3:
        formatted = s
    else:
        # rightmost 3 digits
        formatted = s[-3:]
        s = s[:-3]
        while s:
            formatted = s[-2:] + "," + formatted
            s = s[:-2]

    result = f"{symbol}{formatted}"
    if dec_part > 0:
        result += f".{int(round(dec_part * 100)):02d}"

    return f"-{result}" if negative else result


def format_amount(amount: float, symbol: str = CURRENCY_SYMBOL) -> str:
    """
    Human-readable compact form: use lakh/crore suffixes for large amounts.

    Examples
    --------
    >>> format_amount(500)
    '₹500'
    >>> format_amount(50000)
    '₹50,000'
    >>> format_amount(100000)
    '₹1.00 lakh'
    >>> format_amount(10000000)
    '₹1.00 crore'
    """
    abs_amount = abs(amount)
    sign = "-" if amount < 0 else ""

    if abs_amount >= 1_00_00_000:  # 1 crore
        return f"{sign}{symbol}{abs_amount / 1_00_00_000:.2f} crore"
    elif abs_amount >= 1_00_000:  # 1 lakh
        return f"{sign}{symbol}{abs_amount / 1_00_000:.2f} lakh"
    else:
        return f"{sign}{format_inr(abs_amount, symbol)}"


def make_table(rows: list[list], headers: list[str]) -> str:
    """
    Build a Markdown table string from rows and headers.

    Parameters
    ----------
    rows : list[list]
        Each inner list is a row; cells are converted to str.
    headers : list[str]
        Column header names.

    Returns
    -------
    str
        A GitHub-flavoured Markdown table.

    Examples
    --------
    >>> print(make_table([["EMI", "₹30,000"], ["Total", "₹50,000"]], ["Item", "Value"]))
    | Item | Value |
    | --- | --- |
    | EMI | ₹30,000 |
    | Total | ₹50,000 |
    """
    if not headers:
        raise ValueError("headers must not be empty")

    sep = "| " + " | ".join("---" for _ in headers) + " |"
    header_row = "| " + " | ".join(str(h) for h in headers) + " |"
    data_rows = [
        "| " + " | ".join(str(cell) for cell in row) + " |"
        for row in rows
    ]
    return "\n".join([header_row, sep] + data_rows)


def months_to_human(months: int) -> str:
    """
    Convert a number of months to a human-readable string.

    Examples
    --------
    >>> months_to_human(0)
    '0 months'
    >>> months_to_human(1)
    '1 month'
    >>> months_to_human(13)
    '1 year 1 month'
    >>> months_to_human(24)
    '2 years'
    """
    if months < 0:
        raise ValueError("months must be non-negative")
    years, rem = divmod(int(months), 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if rem:
        parts.append(f"{rem} month{'s' if rem != 1 else ''}")
    return " ".join(parts) if parts else "0 months"

