"""Utility functions for data serialization and coercion."""

from datetime import datetime


def serialize_payload(data: dict) -> dict:
    """Convert datetime objects to ISO format strings for JSON serialization."""
    result = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result