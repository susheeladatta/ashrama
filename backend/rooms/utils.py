# backend/utils.py
from datetime import datetime
from django.core.exceptions import ValidationError

def parse_date(date_str):
    """Parse date from various string formats"""
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValidationError(f"Date '{date_str}' is not in a known format (try YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY)")