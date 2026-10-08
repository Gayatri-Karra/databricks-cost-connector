"""
Unit tests for resilient handling of malformed and corrupted source records.
Ensures connector doesn't crash on unexpected schemas, null values, or bad types.
"""

from databricks_cost_connector.normalizer import CostRecordNormalizer
from databricks_cost_connector.models import NormalizedRecord


def test_malformed_billable_usage_record_corrupted_types():
    """Tests usage record with corrupted numbers, invalid timestamps, and non-dict tags."""
    corrupted_raw = {
        "record_id": 12345,  # int instead of string
        "usage_quantity": "invalid_number_xyz",  # corrupted decimal string
        "list_unit_price": ["unexpected", "list"],  # list instead of float/string
        "usage_start_time": "32nd-Of-Undecimber",  # gibberish timestamp
        "custom_tags": "not_a_dictionary",  # string instead of dict
        "identity_metadata": None,
    }

    norm = CostRecordNormalizer.normalize_billable_usage(
        corrupted_raw,
        platform="AWS",
        collection_time="2026-10-06T12:00:00Z",
    )

    assert isinstance(norm, NormalizedRecord)
    assert norm.source_record_identifier == "12345"
    assert norm.consumed_quantity is None  # Safely fell back to None
    assert norm.list_unit_price is None    # Safely fell back to None
    assert norm.usage_start is None        # Safely fell back to None
    assert norm.tags_or_allocation_metadata is None  # Non-dict rejected safely


def test_completely_empty_record():
    """Tests empty dictionary."""
    norm = CostRecordNormalizer.normalize_billable_usage(
        {},
        platform="AWS",
        collection_time="2026-10-06T12:00:00Z",
    )
    assert isinstance(norm, NormalizedRecord)
    assert norm.source_record_identifier is None
    assert norm.collection_time == "2026-10-06T12:00:00Z"


def test_malformed_cluster_record():
    """Cluster record missing name and containing string timestamps."""
    raw = {
        "cluster_id": "c-999",
        "start_time": "invalid_time",
        "custom_tags": 12345,
    }
    norm = CostRecordNormalizer.normalize_cluster(
        raw,
        platform="AWS",
        workspace_id=None,
        collection_time="2026-10-06T12:00:00Z",
    )
    assert norm.source_record_identifier == "c-999"
    assert norm.usage_start is None
    assert norm.tags_or_allocation_metadata is None

