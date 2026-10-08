"""
Unit tests for handling empty results across collectors.
Verifies that 0 records are reported with status 'empty' rather than failure.
"""

from unittest.mock import MagicMock
from databricks_cost_connector.models import CategoryStatus
from databricks_cost_connector.collectors.compute_usage import ClusterComputeCollector, SQLWarehouseCollector
from databricks_cost_connector.collectors.jobs_pipelines import JobsAndPipelineCollector


def test_cluster_collector_empty_results(mock_config):
    """When clusters list API returns empty array, status is CategoryStatus.EMPTY."""
    mock_client = MagicMock()
    mock_client.rest_request.return_value = ({"clusters": []}, CategoryStatus.COLLECTED, None)

    # Disable mock mode for unit test to use mocked client
    mock_config.mock_mode = False
    collector = ClusterComputeCollector(mock_client, mock_config)

    result = collector.collect()
    assert result.status == CategoryStatus.EMPTY
    assert result.records_count == 0
    assert len(result.normalized_records) == 0
    assert "No clusters present" in (result.explanation or "")


def test_sql_warehouse_empty_results(mock_config):
    """When warehouses API returns empty list, status is CategoryStatus.EMPTY."""
    mock_client = MagicMock()
    mock_client.rest_request.return_value = ({"warehouses": []}, CategoryStatus.COLLECTED, None)

    mock_config.mock_mode = False
    collector = SQLWarehouseCollector(mock_client, mock_config)

    result = collector.collect()
    assert result.status == CategoryStatus.EMPTY
    assert result.records_count == 0
    assert "No SQL warehouses configured" in (result.explanation or "")


def test_jobs_collector_empty_results(mock_config):
    """When jobs API returns empty list, status is CategoryStatus.EMPTY."""
    mock_client = MagicMock()
    mock_client.paginate_rest_get.return_value = ([], CategoryStatus.EMPTY, None)

    mock_config.mock_mode = False
    collector = JobsAndPipelineCollector(mock_client, mock_config)

    result = collector.collect()
    assert result.status == CategoryStatus.EMPTY
    assert result.records_count == 0
    assert "No jobs or scheduled pipelines" in (result.explanation or "")

