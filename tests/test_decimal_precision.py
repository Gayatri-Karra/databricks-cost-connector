"""
Unit tests for decimal precision preservation.
Verifies that DBU quantities, rates, and costs maintain micro-precision
without binary IEEE-754 floating-point truncation or drift.
"""

from decimal import Decimal
from databricks_cost_connector.normalizer import parse_decimal_str, CostRecordNormalizer


def test_parse_decimal_preserves_high_precision_string():
    """Confirms 18 decimal places of DBU allocation are preserved exactly as string."""
    precise_str = "0.123456789012345678"
    result = parse_decimal_str(precise_str)
    assert result == "0.123456789012345678"


def test_parse_decimal_handles_scientific_notation():
    """Confirms scientific notation strings parse into standard decimal representation."""
    sci_val = "1.5e-5"
    result = parse_decimal_str(sci_val)
    assert result == "0.000015"


def test_parse_decimal_avoids_binary_float_imprecision():
    """Confirms conversion from Decimal and formatted string maintains exact equality."""
    d = Decimal("0.1000000000") + Decimal("0.2000000000")
    result = parse_decimal_str(d)
    assert result == "0.3000000000"
    assert result != "0.30000000000000004"


def test_calculate_list_cost_exact_arithmetic():
    """Verifies unadjusted list cost calculation uses exact Decimal multiplication."""
    raw = {
        "record_id": "prec-test-01",
        "usage_quantity": "3.3333333333",
        "list_unit_price": "0.150000",
        "usage_start_time": "2026-10-01T00:00:00Z",
    }
    record = CostRecordNormalizer.normalize_billable_usage(
        raw,
        platform="AWS",
        collection_time="2026-10-06T12:00:00Z",
    )

    expected_cost = Decimal("3.3333333333") * Decimal("0.150000")
    assert record.list_cost == f"{expected_cost:f}"
    assert record.consumed_quantity == "3.3333333333"
    assert record.list_unit_price == "0.150000"


def test_parse_decimal_none_and_empty():
    """Confirms None, empty string, or invalid non-numbers safely return None."""
    assert parse_decimal_str(None) is None
    assert parse_decimal_str("") is None
    assert parse_decimal_str("   ") is None
    assert parse_decimal_str("invalid_number") is None

