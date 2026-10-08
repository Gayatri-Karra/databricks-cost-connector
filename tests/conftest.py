"""
Pytest configuration and shared fixtures for Databricks cost connector test suite.
All tests run hermetically without external network access or live credentials.
"""

from decimal import Decimal
import pytest

from databricks_cost_connector.config import DatabricksConfig
from databricks_cost_connector.client import DatabricksClientWrapper
from databricks_cost_connector.models import CategoryStatus, NormalizedRecord


@pytest.fixture
def mock_config():
    """Provides a DatabricksConfig configured for mock mode."""
    return DatabricksConfig(
        host="https://dbc-test-workspace.cloud.databricks.com",
        token="dapi_test_dummy_token_12345",
        account_id="00000000-0000-0000-0000-000000000000",
        warehouse_id="test-warehouse-id",
        cloud_provider="AWS",
        output_dir="output",
        mock_mode=True,
    )


@pytest.fixture
def mock_client(mock_config):
    """Provides a client instance with mock mode enabled."""
    return DatabricksClientWrapper(mock_config)


@pytest.fixture
def sample_raw_billable_record():
    """Provides a realistic single billable usage record."""
    return {
        "record_id": "usg-rec-sample-001",
        "account_id": "c8a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
        "workspace_id": "4920194810294810",
        "cluster_id": "0924-110243-abc12345",
        "cluster_name": "production-analytics-cluster",
        "sku_name": "ENTERPRISE_ALL_PURPOSE_COMPUTE",
        "product_name": "All-Purpose Compute",
        "cloud": "AWS",
        "region": "us-east-1",
        "usage_start_time": "2026-10-01T08:00:00Z",
        "usage_end_time": "2026-10-01T09:00:00Z",
        "usage_quantity": "0.123456789012345678",
        "usage_unit": "DBU",
        "list_unit_price": "0.5500",
        "list_cost": "0.0679012339567891229",
        "currency": "USD",
        "identity_metadata": {
            "run_as": "test.engineer@example.com"
        },
        "custom_tags": {
            "Department": "Engineering",
            "Environment": "Production"
        },
        "updated_at": "2026-10-01T09:30:00Z",
        "record_type": "USAGE"
    }

