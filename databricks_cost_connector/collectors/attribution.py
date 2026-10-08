"""
Workload attribution, user/service-principal attribution, and allocation tags collectors.
Maps consumption to business dimensions, owners, service principals, and cost centers.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
from .billable_usage import BillingAndUsageCollector
from .base import BaseCostCollector
from ..models import CategoryStatus, CollectionResult, NormalizedRecord
from ..normalizer import CostRecordNormalizer

logger = logging.getLogger("databricks_cost_connector.collectors.attribution")


class ResourceWorkloadAttributionCollector(BaseCostCollector):
    """Collector for 'Resource and workload attribution' category."""

    @property
    def category_name(self) -> str:
        return "Resource and workload attribution"

    @property
    def purpose(self) -> str:
        return "Map cost and usage records directly to cluster, job, SQL warehouse, and notebook workload identifiers"

    @property
    def required_permission(self) -> str:
        return "Workspace Access"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(
                os.path.dirname(__file__),
                "..", "..", "fixtures", "billable_usage_records.json"
            )
            try:
                with open(fixture_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception:
                raw_data = []
        else:
            billing_result = BillingAndUsageCollector(
                self.client, self.config
            ).collect(start_time, end_time)

            if billing_result.status != CategoryStatus.COLLECTED:
                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=billing_result.status,
                    records_count=0,
                    required_permission=self.required_permission,
                    explanation=(
                        "Live billing usage data was not available; "
                        "workload attribution was not inferred from fixtures."
                    ),
                    error_details=billing_result.error_details,
                )

            raw_data = billing_result.raw_records
        attributed = [
            r for r in raw_data
            if r.get("cluster_id") or r.get("job_id") or r.get("warehouse_id") or r.get("pipeline_id")
        ]
        normalized = [
            CostRecordNormalizer.normalize_billable_usage(r, self.config.cloud_provider, collection_time)
            for r in attributed
        ]
        for n in normalized:
            n.source_category = self.category_name

        earliest, latest = self.find_timestamp_bounds(normalized)
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.COLLECTED if normalized else CategoryStatus.EMPTY,
            records_count=len(normalized),
            earliest_timestamp=earliest,
            latest_timestamp=latest,
            required_permission=self.required_permission,
            raw_records=attributed,
            normalized_records=normalized,
        )


class UserPrincipalAttributionCollector(BaseCostCollector):
    """Collector for 'User and service-principal attribution' category."""

    @property
    def category_name(self) -> str:
        return "User and service-principal attribution"

    @property
    def purpose(self) -> str:
        return "Attribute resource creation and compute execution to individual users and automated service principals"

    @property
    def required_permission(self) -> str:
        return "Workspace SCIM Reader or Workspace Admin"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            identities = [
                {
                    "id": "usr-101",
                    "userName": "developer.alice@example.com",
                    "displayName": "Alice Developer",
                    "active": True,
                    "type": "User",
                },
                {
                    "id": "usr-102",
                    "userName": "analyst.bob@example.com",
                    "displayName": "Bob Analyst",
                    "active": True,
                    "type": "User",
                },
                {
                    "id": "sp-201",
                    "applicationId": "sp-etl-nightly-01",
                    "displayName": "Nightly ETL Service Principal",
                    "active": True,
                    "type": "ServicePrincipal",
                },
            ]
            normalized = [
                NormalizedRecord(
                    platform=f"Databricks {self.config.cloud_provider}",
                    billing_account_identifier=self.config.account_id,
                    workspace_identifier=None,
                    source_category=self.category_name,
                    source_record_identifier=i["id"],
                    user_or_service_principal_attribution=i.get("userName") or i.get("applicationId"),
                    service_or_product="Identity & Access Management",
                    collection_time=collection_time,
                    additional_source_metadata={
                        "display_name": i.get("displayName"),
                        "principal_type": i.get("type"),
                        "active": i.get("active"),
                    },
                )
                for i in identities
            ]
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.COLLECTED,
                records_count=len(normalized),
                required_permission=self.required_permission,
                raw_records=identities,
                normalized_records=normalized,
            )

        data, status, err = self.client.rest_request("GET", "/api/2.0/preview/scim/v2/Users", params={"count": 100})
        if status != CategoryStatus.COLLECTED or data is None:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=status,
                required_permission=self.required_permission,
                explanation=err,
                error_details=err,
            )

        users = data.get("Resources", [])
        normalized = [
            NormalizedRecord(
                platform=f"Databricks {self.config.cloud_provider}",
                billing_account_identifier=self.config.account_id,
                workspace_identifier=None,
                source_category=self.category_name,
                source_record_identifier=u.get("id"),
                user_or_service_principal_attribution=u.get("userName"),
                service_or_product="Identity & Access Management",
                collection_time=collection_time,
                additional_source_metadata={"display_name": u.get("displayName"), "active": u.get("active")},
            )
            for u in users
        ]
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.COLLECTED if normalized else CategoryStatus.EMPTY,
            records_count=len(normalized),
            required_permission=self.required_permission,
            raw_records=users,
            normalized_records=normalized,
        )


class TagsAllocationCollector(BaseCostCollector):
    """Collector for 'Tags and allocation metadata' category."""

    @property
    def category_name(self) -> str:
        return "Tags and allocation metadata"

    @property
    def purpose(self) -> str:
        return "Extract custom tags, cost centers, project codes, and organizational chargeback metadata"

    @property
    def required_permission(self) -> str:
        return "Workspace Access"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(
                os.path.dirname(__file__),
                "..", "..", "fixtures", "billable_usage_records.json"
            )
            try:
                with open(fixture_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception:
                raw_data = []
        else:
            billing_result = BillingAndUsageCollector(
                self.client, self.config
            ).collect(start_time, end_time)

            if billing_result.status != CategoryStatus.COLLECTED:
                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=billing_result.status,
                    records_count=0,
                    required_permission=self.required_permission,
                    explanation=(
                        "Live billing usage data was not available; "
                        "tags were not inferred from fixtures."
                    ),
                    error_details=billing_result.error_details,
                )

            raw_data = billing_result.raw_records

        tagged_records = [r for r in raw_data if r.get("custom_tags")]
        normalized = []
        for r in tagged_records:
            norm = CostRecordNormalizer.normalize_billable_usage(r, self.config.cloud_provider, collection_time)
            norm.source_category = self.category_name
            normalized.append(norm)

        earliest, latest = self.find_timestamp_bounds(normalized)
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.COLLECTED if normalized else CategoryStatus.EMPTY,
            records_count=len(normalized),
            earliest_timestamp=earliest,
            latest_timestamp=latest,
            required_permission=self.required_permission,
            raw_records=tagged_records,
            normalized_records=normalized,
        )

