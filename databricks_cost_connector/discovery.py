"""
Discovery module for Databricks cost-management capabilities.
Probes workspace identity, account admin capabilities, Unity Catalog system tables,
and specific workload APIs to map available cost vectors before collection.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import DatabricksClientWrapper
from .config import DatabricksConfig
from .models import CategoryStatus

logger = logging.getLogger("databricks_cost_connector.discovery")


@dataclass
class AccountWorkspaceDiscovery:
    """Discovered context for the current Databricks environment."""
    authenticated: bool = False
    current_user: Optional[str] = None
    workspace_id: Optional[str] = None
    account_id: Optional[str] = None
    cloud_provider: str = "AWS"
    capabilities: Dict[str, bool] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_redacted_dict(self) -> Dict[str, Any]:
        """Provides a safe dictionary for logs and reports."""
        def mask(s: Optional[str]) -> str:
            if not s:
                return "<none>"
            if len(s) <= 8:
                return "***"
            return f"{s[:3]}...{s[-3:]}"

        return {
            "authenticated": self.authenticated,
            "current_user": mask(self.current_user),
            "workspace_id": mask(self.workspace_id),
            "account_id": mask(self.account_id),
            "cloud_provider": self.cloud_provider,
            "capabilities": self.capabilities,
            "warnings": self.warnings,
        }


class EnvironmentDiscovery:
    """
    Conducts non-destructive discovery checks against Databricks APIs.
    Identifies what datasets are reachable with caller's permissions.
    """

    def __init__(self, client: DatabricksClientWrapper, config: DatabricksConfig):
        self.client = client
        self.config = config

    def discover(self) -> AccountWorkspaceDiscovery:
        """Run all discovery probes and return environment metadata."""
        discovery = AccountWorkspaceDiscovery(
            account_id=self.config.account_id,
            cloud_provider=self.config.cloud_provider,
        )

        if self.config.mock_mode:
            logger.info("[Mock Mode] Using synthetic environment discovery.")
            discovery.authenticated = True
            discovery.current_user = "finops-service-principal@example.com"
            discovery.workspace_id = "4920194810294810"
            discovery.account_id = self.config.account_id or "c8a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c"
            discovery.capabilities = {
                "clusters_api": True,
                "sql_warehouses_api": True,
                "jobs_api": True,
                "system_billing_usage": True,
                "system_billing_prices": True,
                "account_billable_usage_api": True,
                "budgets_api": True,
                "scim_users_api": True,
            }
            return discovery

        # 1. Probe Workspace Authentication & User Identity
        logger.info("Probing Databricks Workspace authentication...")
        user_data, status, err = self.client.rest_request("GET", "/api/2.0/preview/scim/v2/Me")
        if status == CategoryStatus.COLLECTED and user_data:
            discovery.authenticated = True
            discovery.current_user = user_data.get("userName") or user_data.get("displayName")
            logger.info(f"Successfully authenticated to workspace as: {self.config.mask_string(discovery.current_user)}")
        else:
            # Fallback check via spark-versions
            sp_data, sp_status, sp_err = self.client.rest_request("GET", "/api/2.0/clusters/spark-versions")
            if sp_status == CategoryStatus.COLLECTED:
                discovery.authenticated = True
                discovery.current_user = "workspace_token_holder"
                logger.info("Workspace authentication verified via compute API.")
            else:
                logger.warning(f"Workspace authentication probe failed: {err or sp_err}")
                discovery.warnings.append(f"Workspace authentication failed: {err or sp_err}")

        # 2. Probe Workspace ID from token / current status
        if discovery.authenticated and self.config.host:
            # Workspace ID can often be deduced from host or cluster probe
            cl_data, _, _ = self.client.rest_request("GET", "/api/2.0/clusters/list")
            if cl_data and "clusters" in cl_data:
                discovery.capabilities["clusters_api"] = True
                if cl_data["clusters"]:
                    discovery.workspace_id = cl_data["clusters"][0].get("cluster_id", "").split("-")[0]
            else:
                discovery.capabilities["clusters_api"] = (cl_data is not None)

        # 3. Probe SQL Warehouses API
        wh_data, wh_status, wh_err = self.client.rest_request("GET", "/api/2.0/sql/warehouses")
        discovery.capabilities["sql_warehouses_api"] = (wh_status == CategoryStatus.COLLECTED)
        if wh_status == CategoryStatus.PERMISSION_DENIED:
            discovery.warnings.append("SQL Warehouses API returned Permission Denied (Requires CAN_USE on SQL)")

        # 4. Probe Jobs API
        jobs_data, jobs_status, _ = self.client.rest_request("GET", "/api/2.1/jobs/list", params={"limit": 5})
        discovery.capabilities["jobs_api"] = (jobs_status == CategoryStatus.COLLECTED)

        # 5. Probe Account API access
        if self.config.account_id:
            logger.info("Probing Databricks Account API access...")
            acct_data, acct_status, acct_err = self.client.rest_request(
                "GET",
                f"/api/2.0/accounts/{self.config.account_id}/workspaces",
                is_account_api=True,
            )
            discovery.capabilities["account_api"] = (acct_status == CategoryStatus.COLLECTED)
            if acct_status == CategoryStatus.PERMISSION_DENIED:
                discovery.warnings.append(
                    "Account API access denied. Note: Standard workspace personal access tokens lack Account Admin privileges."
                )
        else:
            discovery.capabilities["account_api"] = False
            discovery.warnings.append("No DATABRICKS_ACCOUNT_ID configured; account-level usage collection will be skipped.")

        # 6. Probe Budgets API
        if self.config.account_id:
            budgets_data, b_status, _ = self.client.rest_request(
                "GET",
                f"/api/2.0/accounts/{self.config.account_id}/budget-policies",
                is_account_api=True,
            )
            discovery.capabilities["budgets_api"] = (b_status == CategoryStatus.COLLECTED)
        else:
            discovery.capabilities["budgets_api"] = False

        return discovery

