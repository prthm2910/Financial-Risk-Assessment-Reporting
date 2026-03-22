"""
financial_year.py

Utility to determine the current financial year in the format used for Indian fiscal calendars (e.g., "FY2025").
"""

from datetime import date

def get_current_financial_year() -> str:
    """
    Returns the current financial year (FY) based on the Indian financial calendar.

    The Indian financial year starts on April 1st and ends on March 31st.
    For example:
        - If today is July 22, 2025 => Returns "FY2025"
        - If today is February 5, 2025 => Returns "FY2024"

    Returns:
        str: A string representing the financial year, e.g., "FY2025"
    """
    today = date.today()
    year = today.year
    if today.month < 4:
        # January, February, and March are part of the previous FY
        return f"FY{year - 1}"
    else:
        # April onwards is the current FY
        return f"FY{year}"

# Example usage:
# print(get_current_financial_year())  # Output: 'FY2025' if today is in July 2025
