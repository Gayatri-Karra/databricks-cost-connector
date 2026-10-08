"""
Compute, SQL warehouse, and cost-optimization collectors.
Interacts with Workspace Clusters API (/api/2.0/clusters/list),
SQL Warehouses API (/api/2.0/sql/warehouses), and Cluster Policies (/api/2.0/policies/clusters/list).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base import BaseCostCollector
from ..models import CategoryStatus, CollectionResult, NormalizedRecord
from ..normalizer import CostRecordNormalizer

logger = logging.getLogger("databricks_cost_connector.collectors.compute_usage")


class ClusterComputeCollector(BaseCostCollector):
    """Collector for 'Cluster and compute consumption' category."""

    @property
    def category_name(self) -> str:
        return "Cluster and compute consumption"

    @property
    def purpose(self) -> str:
        return "Discover cluster compute configurations, active node counts, runtime hours, and worker specs"

    @property
    def required_permission(self) -> str:
        return "Workspace Access (CAN_ATTACH_TO or Cluster Admin)"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "clusters_response.json")
            with open(fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            clusters = data.get("clusters", [])
            normalized = [
                CostRecordNormalizer.normalize_cluster(c, self.config.cloud_provider, None, collection_time)
                for c in clusters
            ]
            earliest, latest = self.find_timestamp_bounds(normalized)
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.COLLECTED if normalized else CategoryStatus.EMPTY,
                records_count=len(normalized),
                earliest_timestamp=earliest,
                latest_timestamp=latest,
                required_permission=self.required_permission,
                raw_records=clusters,
                normalized_records=normalized,
            )

        data, status, err = self.client.rest_request("GET", "/api/2.0/clusters/list")
        if status != CategoryStatus.COLLECTED or data is None:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=status,
                required_permission=self.required_permission,
                explanation=err,
                error_details=err,
            )

        clusters = data.get("clusters", [])
        if not clusters:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.EMPTY,
                records_count=0,
                required_permission=self.required_permission,
                explanation="No clusters present in workspace",
            )

        normalized = [
            CostRecordNormalizer.normalize_cluster(c, self.config.cloud_provider, None, collection_time)
            for c in clusters
        ]
        earliest, latest = self.find_timestamp_bounds(normalized)
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.COLLECTED,
            records_count=len(normalized),
            earliest_timestamp=earliest,
            latest_timestamp=latest,
            required_permission=self.required_permission,
            raw_records=clusters,
            normalized_records=normalized,
        )


class SQLWarehouseCollector(BaseCostCollector):
    """Collector for 'SQL warehouse consumption' category."""

    @property
    def category_name(self) -> str:
        return "SQL warehouse consumption"

    @property
    def purpose(self) -> str:
        return "Collect SQL warehouse endpoints, cluster sizing, serverless properties, and auto-stop configs"

    @property
    def required_permission(self) -> str:
        return "Workspace SQL Access (CAN_USE or SQL Admin)"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "warehouses_response.json")
            with open(fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            warehouses = data.get("warehouses", [])
            normalized = [
                CostRecordNormalizer.normalize_warehouse(w, self.config.cloud_provider, None, collection_time)
                for w in warehouses
            ]
            earliest, latest = self.find_timestamp_bounds(normalized)
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.COLLECTED if normalized else CategoryStatus.EMPTY,
                records_count=len(normalized),
                earliest_timestamp=earliest,
                latest_timestamp=latest,
                required_permission=self.required_permission,
                raw_records=warehouses,
                normalized_records=normalized,
            )

        data, status, err = self.client.rest_request("GET", "/api/2.0/sql/warehouses")
        if status != CategoryStatus.COLLECTED or data is None:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=status,
                required_permission=self.required_permission,
                explanation=err,
                error_details=err,
            )

        warehouses = data.get("warehouses", [])
        if not warehouses:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.EMPTY,
                records_count=0,
                required_permission=self.required_permission,
                explanation="No SQL warehouses configured in workspace",
            )

        normalized = [
            CostRecordNormalizer.normalize_warehouse(w, self.config.cloud_provider, None, collection_time)
            for w in warehouses
        ]
        earliest, latest = self.find_timestamp_bounds(normalized)
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.COLLECTED,
            records_count=len(normalized),
            earliest_timestamp=earliest,
            latest_timestamp=latest,
            required_permission=self.required_permission,
            raw_records=warehouses,
            normalized_records=normalized,
        )


class OptimizationCostSavingCollector(BaseCostCollector):
    """Collector for 'Optimization and cost-saving information' category."""

    @property
    def category_name(self) -> str:
        return "Optimization and cost-saving information"

    @property
    def purpose(self) -> str:
        return "Discover cluster policies, auto-termination configurations, idle timeouts, and spot instance rules"

    @property
    def required_permission(self) -> str:
        return "Workspace Access (CAN_USE on Cluster Policies)"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            # Synthetic cluster policy and auto-termination optimization data
            policies = [
                {
                    "policy_id": "pol-auto-term-default",
                    "name": "Cost-Controlled Interactive Cluster Policy",
                    "definition": json.dumps({
                        "autotermination_minutes": {"type": "fixed", "value": 20},
                        "spark_conf.spark.databricks.cluster.profile": {"type": "fixed", "value": "singleNode"},
                        "aws_attributes.spot_bid_price_percent": {"type": "range", "maxValue": 100}
                    }),
                    "created_at_timestamp": 1727740800000,
                }
            ]
            normalized = [
                NormalizedRecord(
                    platform=f"Databricks {self.config.cloud_provider}",
                    billing_account_identifier=self.config.account_id,
                    workspace_identifier=None,
                    source_category=self.category_name,
                    source_record_identifier=p["policy_id"],
                    resource_or_workload_identifier=p["policy_id"],
                    resource_or_workload_name=p["name"],
                    resource_or_workload_type="cluster_policy",
                    service_or_product="Governance & Cost Optimization",
                    collection_time=collection_time,
                    additional_source_metadata={"policy_definition": p["definition"]},
                )
                for p in policies
            ]
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.COLLECTED,
                records_count=len(normalized),
                required_permission=self.required_permission,
                raw_records=policies,
                normalized_records=normalized,
            )

        data, status, err = self.client.rest_request("GET", "/api/2.0/policies/clusters/list")
        if status != CategoryStatus.COLLECTED or data is None:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=status,
                required_permission=self.required_permission,
                explanation=err,
                error_details=err,
            )

        policies = data.get("policies", [])
        if not policies:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.EMPTY,
                records_count=0,
                required_permission=self.required_permission,
                explanation="No custom cluster policies or cost controls found",
            )

        normalized = [
            NormalizedRecord(
                platform=f"Databricks {self.config.cloud_provider}",
                billing_account_identifier=self.config.account_id,
                workspace_identifier=None,
                source_category=self.category_name,
                source_record_identifier=p.get("policy_id"),
                resource_or_workload_identifier=p.get("policy_id"),
                resource_or_workload_name=p.get("name"),
                resource_or_workload_type="cluster_policy",
                service_or_product="Governance & Cost Optimization",
                collection_time=collection_time,
                additional_source_metadata={"policy_definition": p.get("definition")},
            )
            for p in policies
        ]
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.COLLECTED,
            records_count=len(normalized),
            required_permission=self.required_permission,
            raw_records=policies,
            normalized_records=normalized,
        )

