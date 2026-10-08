"""
Unit tests for timestamp handling and UTC standardization.
Verifies conversion from epoch milliseconds, localized ISO strings, and dates
into canonical UTC format (YYYY-MM-DDTHH:MM:SSZ).
"""

from datetime import datetime, timezone
from databricks_cost_connector.normalizer import parse_timestamp_to_utc


def test_epoch_milliseconds_conversion():
    """Databricks clusters & jobs API return epoch milliseconds (e.g., 1727769600000)."""
    epoch_ms = 1727769600000  # 2024-10-01 08:00:00 UTC
    utc_str = parse_timestamp_to_utc(epoch_ms)
    assert utc_str == "2024-10-01T08:00:00Z"


def test_epoch_seconds_conversion():
    """Standard unix epoch seconds."""
    epoch_sec = 1727769600
    utc_str = parse_timestamp_to_utc(epoch_sec)
    assert utc_str == "2024-10-01T08:00:00Z"


def test_timezone_offset_conversion_to_utc():
    """Verifies non-UTC offsets are shifted to UTC."""
    # 2026-10-06 17:30:00 IST (+05:30) is 2026-10-06 12:00:00 UTC
    ist_str = "2026-10-06T17:30:00+05:30"
    utc_str = parse_timestamp_to_utc(ist_str)
    assert utc_str == "2026-10-06T12:00:00Z"

    # 2026-10-06 05:00:00 PDT (-07:00) is 2026-10-06 12:00:00 UTC
    pdt_str = "2026-10-06T05:00:00-07:00"
    utc_str2 = parse_timestamp_to_utc(pdt_str)
    assert utc_str2 == "2026-10-06T12:00:00Z"


def test_iso_utc_string_preserved():
    """Direct UTC string."""
    ts = "2026-10-01T08:00:00Z"
    assert parse_timestamp_to_utc(ts) == "2026-10-01T08:00:00Z"


def test_naive_datetime_object():
    """Naive datetime objects are assumed UTC and formatted."""
    dt = datetime(2026, 10, 1, 8, 0, 0)
    assert parse_timestamp_to_utc(dt) == "2026-10-01T08:00:00Z"


def test_invalid_and_empty_timestamps():
    """Confirms invalid formats return None without raising uncaught exceptions."""
    assert parse_timestamp_to_utc(None) is None
    assert parse_timestamp_to_utc("") is None
    assert parse_timestamp_to_utc("   ") is None
    assert parse_timestamp_to_utc("not-a-valid-date") is None

