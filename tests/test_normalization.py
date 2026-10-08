"""
Unit tests for data normalization logic across Databricks cost entities.
Verifies compliance with the assessment normalization schema.
"""

from databricks_cost_connector.normalizer import CostRecordNormalizer
from databricks_cost_connector.models import NormalizedRecord


def test_normalize_billable_usage_complete(sample_raw_billable_record):
    """Verifies that all applicable fields in billable usage record are correctly mapped."""
    collection_time = "2026-10-06T12:00:00Z"
    record = CostRecordNormalizer.normalize_billable_usage(
        sample_raw_billable_record,
        platform="AWS",
        collection_time=collection_time,
    )

    assert isinstance(record, NormalizedRecord)
    assert record.platform == "Databricks AWS"
    assert record.billing_account_identifier == "c8a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c"
    assert record.workspace_identifier == "4920194810294810"
    assert record.source_category == "Billing and usage"
    assert record.source_record_identifier == "usg-rec-sample-001"
    assert record.resource_or_workload_identifier == "0924-110243-abc12345"
    assert record.resource_or_workload_name == "production-analytics-cluster"
    assert record.resource_or_workload_type == "cluster"
    assert record.service_or_product == "All-Purpose Compute"
    assert record.sku == "ENTERPRISE_ALL_PURPOSE_COMPUTE"
    assert record.usage_start == "2026-10-01T08:00:00Z"
    assert record.usage_end == "2026-10-01T09:00:00Z"
    assert record.consumed_quantity == "0.123456789012345678"
    assert record.consumed_unit == "DBU"
    assert record.list_unit_price == "0.5500"
    assert record.currency == "USD"
    assert record.user_or_service_principal_attribution == "test.engineer@example.com"
    assert record.tags_or_allocation_metadata == {
        "Department": "Engineering",
        "Environment": "Production",
    }
    assert record.source_update_time == "2026-10-01T09:30:00Z"
    assert record.collection_time == collection_time


def test_missing_fields_remain_null():
    """Verifies that inapplicable/missing fields remain None and are not fabricated."""
    minimal_record = {
        "record_id": "rec-min-123",
        "usage_quantity": "5.0",
        "usage_start_time": "2026-10-01T00:00:00Z",
    }
    norm = CostRecordNormalizer.normalize_billable_usage(
        minimal_record,
        platform="AWS",
        collection_time="2026-10-06T12:00:00Z",
    )

    assert norm.source_record_identifier == "rec-min-123"
    assert norm.consumed_quantity == "5.0"
    assert norm.billing_account_identifier is None
    assert norm.workspace_identifier is None
    assert norm.resource_or_workload_identifier is None
    assert norm.resource_or_workload_name is None
    assert norm.resource_or_workload_type is None
    assert norm.contracted_cost is None
    assert norm.effective_cost is None
    assert norm.billed_cost is None
    assert norm.user_or_service_principal_attribution is None
    assert norm.tags_or_allocation_metadata is None


def test_normalize_cluster():
    """Verifies cluster metadata normalization."""
    cluster_raw = {
        "cluster_id": "cl-5555",
        "cluster_name": "ETL-Worker",
        "creator_user_name": "ops@example.com",
        "start_time": 1727769600000,
        "terminated_time": 1727773200000,
        "cluster_source": "JOB",
        "node_type_id": "i3.xlarge",
        "num_workers": 4,
        "custom_tags": {"Owner": "Ops"},
    }
    norm = CostRecordNormalizer.normalize_cluster(
        cluster_raw,
        platform="AWS",
        workspace_id="998877",
        collection_time="2026-10-06T12:00:00Z",
    )

    assert norm.source_category == "Cluster and compute consumption"
    assert norm.resource_or_workload_identifier == "cl-5555"
    assert norm.resource_or_workload_name == "ETL-Worker"
    assert norm.resource_or_workload_type == "cluster"
    assert norm.workspace_identifier == "998877"
    assert norm.user_or_service_principal_attribution == "ops@example.com"
    assert norm.tags_or_allocation_metadata == {"Owner": "Ops"}
    assert norm.additional_source_metadata["node_type_id"] == "i3.xlarge"


def test_normalize_warehouse():
    """Verifies SQL warehouse normalization with serverless detection."""
    wh_raw = {
        "id": "wh-9900",
        "name": "BI-Serverless",
        "creator_name": "bi-lead@example.com",
        "enable_serverless_compute": True,
        "cluster_size": "Large",
        "auto_stop_mins": 10,
    }
    norm = CostRecordNormalizer.normalize_warehouse(
        wh_raw,
        platform="AWS",
        workspace_id="998877",
        collection_time="2026-10-06T12:00:00Z",
    )

    assert norm.source_category == "SQL warehouse consumption"
    assert norm.resource_or_workload_identifier == "wh-9900"
    assert norm.service_or_product == "Serverless SQL Warehouse"
    assert norm.sku == "ENTERPRISE_SERVERLESS_SQL"
    assert norm.additional_source_metadata["enable_serverless_compute"] is True

