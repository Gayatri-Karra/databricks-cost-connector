"""
Unit tests for authentication, authorization, and permission failure handling.
Ensures that HTTP 401/403 are mapped to 'permission_denied', HTTP 404 to 'unavailable_in_account',
and that the orchestrator continues executing remaining categories without aborting.
"""

from unittest.mock import MagicMock, patch
from databricks_cost_connector.models import CategoryStatus
from databricks_cost_connector.config import DatabricksConfig
from databricks_cost_connector.client import DatabricksClientWrapper
from databricks_cost_connector.orchestrator import CostCollectorOrchestrator
from databricks_cost_connector.collectors.base import BaseCostCollector


def test_client_status_code_mapping_permission_denied():
    """Confirms HTTP 403 Forbidden is mapped to CategoryStatus.PERMISSION_DENIED."""
    config = DatabricksConfig(host="https://test.cloud.databricks.com", token="token")
    client = DatabricksClientWrapper(config)

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "User lacks CAN_MANAGE entitlement"

    with patch.object(client.session, "request", return_value=mock_resp):
        _, status, err = client.rest_request("GET", "/api/2.0/clusters/list")
        assert status == CategoryStatus.PERMISSION_DENIED
        assert "Permission Denied" in err


def test_client_status_code_mapping_unavailable_in_account():
    """Confirms HTTP 404 Not Found is mapped to CategoryStatus.UNAVAILABLE_IN_ACCOUNT."""
    config = DatabricksConfig(host="https://test.cloud.databricks.com", token="token")
    client = DatabricksClientWrapper(config)

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Schema 'system.billing' does not exist"

    with patch.object(client.session, "request", return_value=mock_resp):
        _, status, err = client.rest_request("GET", "/api/2.0/sql/statements")
        assert status == CategoryStatus.UNAVAILABLE_IN_ACCOUNT
        assert "Not Found" in err


def test_orchestrator_fault_tolerance_continues_on_failure(tmp_path):
    """
    Verifies assessment requirement:
    'Continue collecting other categories when one optional category is unavailable.'
    """
    config = DatabricksConfig(
        host="https://test.cloud.databricks.com",
        token="test-token",
        output_dir=str(tmp_path),
        mock_mode=False,
    )
    orchestrator = CostCollectorOrchestrator(config)

    # Mock discovery to succeed
    orchestrator.discovery_engine.discover = MagicMock(return_value=MagicMock(authenticated=True, capabilities={}))

    # Create dummy collectors: one fails with permission denied, one succeeds
    class FailingCollector(BaseCostCollector):
        @property
        def category_name(self): return "Failing Category"
        @property
        def purpose(self): return "Test Failure"
        @property
        def required_permission(self): return "Admin"
        def collect(self, start_time=None, end_time=None):
            raise PermissionError("Access Denied to billing endpoint")

    class SucceedingCollector(BaseCostCollector):
        @property
        def category_name(self): return "Succeeding Category"
        @property
        def purpose(self): return "Test Success"
        @property
        def required_permission(self): return "User"
        def collect(self, start_time=None, end_time=None):
            from databricks_cost_connector.models import CollectionResult
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.COLLECTED,
                records_count=5,
            )

    with patch("databricks_cost_connector.orchestrator.ALL_COLLECTOR_CLASSES", [FailingCollector, SucceedingCollector]):
        results = orchestrator.run()

        assert len(results) == 2
        # First one failed gracefully without crashing orchestrator
        assert results[0].status == CategoryStatus.FAILED
        assert "Access Denied" in (results[0].explanation or "")

        # Second one executed successfully
        assert results[1].status == CategoryStatus.COLLECTED
        assert results[1].records_count == 5
