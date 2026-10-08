"""
Billable usage, account/workspace consumption, and serverless compute collectors.
Queries Databricks system.billing.usage via SQL Statement Execution API or
Account Billable Usage API (/api/2.0/accounts/{account_id}/usage/download).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base import BaseCostCollector
from ..models import CategoryStatus, CollectionResult, NormalizedRecord
from ..normalizer import CostRecordNormalizer

logger = logging.getLogger("databricks_cost_connector.collectors.billable_usage")


class BillingAndUsageCollector(BaseCostCollector):
    """Collector for primary 'Billing and usage' category."""

    @property
    def category_name(self) -> str:
        return "Billing and usage"

    @property
    def purpose(self) -> str:
        return "Collect granular DBU consumption, SKU breakdowns, and hourly billable usage records"

    @property
    def required_permission(self) -> str:
        return "Account Administrator (for usage download) or Unity Catalog system schema access (system.billing.usage)"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "billable_usage_records.json")
            try:
                with open(fixture_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load fixture: {e}")
                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=CategoryStatus.FAILED,
                    required_permission=self.required_permission,
                    error_details=str(e),
                )

            # Filter USAGE records
            records = [r for r in raw_data if r.get("record_type") != "RETRACTION"]
            normalized = [
                CostRecordNormalizer.normalize_billable_usage(r, self.config.cloud_provider, collection_time)
                for r in records
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
                raw_records=records,
                normalized_records=normalized,
            )

        # Live collection attempt
        # 1. Attempt Unity Catalog system.billing.usage via SQL statement execution if warehouse_id is configured
        if self.config.warehouse_id:
            logger.info("Attempting collection via system.billing.usage SQL Statement API...")

            query = "SELECT * FROM system.billing.usage"

            if start_time and end_time:
                query += (
                    f" WHERE usage_start_time >= '{start_time}'"
                    f" AND usage_end_time <= '{end_time}'"
                )

            # No fixed LIMIT is used here.
            # execute_sql_statement() uses EXTERNAL_LINKS and follows
            # Databricks result chunks so large billing datasets can be collected.
            res, status, err = self.client.execute_sql_statement(
                self.config.warehouse_id,
                query,
                wait_timeout="30s",
            )

            if status == CategoryStatus.COLLECTED and res and "result" in res:
                rows = res.get("result", {}).get("data_array", [])
                cols = [
                    c.get("name")
                    for c in res.get("manifest", {})
                    .get("schema", {})
                    .get("columns", [])
                ]

                raw_records = [dict(zip(cols, row)) for row in rows]

                normalized = [
                    CostRecordNormalizer.normalize_billable_usage(
                        r,
                        self.config.cloud_provider,
                        collection_time,
                    )
                    for r in raw_records
                ]

                earliest, latest = self.find_timestamp_bounds(normalized)

                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=(
                        CategoryStatus.COLLECTED
                        if normalized
                        else CategoryStatus.EMPTY
                    ),
                    records_count=len(normalized),
                    earliest_timestamp=earliest,
                    latest_timestamp=latest,
                    required_permission=self.required_permission,
                    raw_records=raw_records,
                    normalized_records=normalized,
                )

            elif status == CategoryStatus.PERMISSION_DENIED:
                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=CategoryStatus.PERMISSION_DENIED,
                    required_permission=self.required_permission,
                    explanation=(
                        "Access to system.billing.usage schema denied "
                        "by Unity Catalog permissions"
                    ),
                    error_details=err,
                )

        # 2. Attempt Account API billable usage download endpoint
        if self.config.account_id:
            logger.info("Attempting collection via Account Billable Usage Download API...")
            path = f"/api/2.0/accounts/{self.config.account_id}/usage/download"
            res, status, err = self.client.rest_request("GET", path, is_account_api=True)
            if status == CategoryStatus.COLLECTED:
                # Handle CSV/JSON records
                pass
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=status,
                required_permission=self.required_permission,
                explanation="Account Administrator role required to download billable usage files directly" if status == CategoryStatus.PERMISSION_DENIED else (err or "Endpoint inaccessible"),
                error_details=err,
            )

        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.UNAVAILABLE_IN_ACCOUNT,
            required_permission=self.required_permission,
            explanation="Neither Unity Catalog system schema nor Account API credentials configured",
        )


class AccountWorkspaceConsumptionCollector(BaseCostCollector):
    """Collector for 'Account and workspace consumption' category."""

    @property
    def category_name(self) -> str:
        return "Account and workspace consumption"

    @property
    def purpose(self) -> str:
        return "Aggregate billing and compute consumption across workspace IDs and tenant accounts"

    @property
    def required_permission(self) -> str:
        return "Account Administrator / Workspace Owner"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "billable_usage_records.json")
            with open(fixture_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Filter valid usage
            records = [r for r in raw_data if r.get("workspace_id")]
            normalized = [
                CostRecordNormalizer.normalize_billable_usage(r, self.config.cloud_provider, collection_time)
                for r in records
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
                raw_records=records,
                normalized_records=normalized,
            )

        if not self.config.account_id:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.UNAVAILABLE_IN_ACCOUNT,
                required_permission=self.required_permission,
                explanation="DATABRICKS_ACCOUNT_ID not configured; workspace-to-account aggregation requires account-level context",
            )

        res, status, err = self.client.rest_request(
            "GET",
            f"/api/2.0/accounts/{self.config.account_id}/workspaces",
            is_account_api=True,
        )
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=status,
            required_permission=self.required_permission,
            explanation=err or "Account administrator access required to view cross-workspace consumption",
            error_details=err,
        )


class ServerlessConsumptionCollector(BaseCostCollector):
    """Collector for 'Serverless consumption' category."""

    @property
    def category_name(self) -> str:
        return "Serverless consumption"

    @property
    def purpose(self) -> str:
        return "Collect and isolate consumption specifically generated by serverless SQL, model serving, and workflows"

    @property
    def required_permission(self) -> str:
        return "Serverless Compute Entitlement / System Tables Reader"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "billable_usage_records.json")
            with open(fixture_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            serverless_records = [
                r for r in raw_data
                if "SERVERLESS" in str(r.get("sku_name", "")).upper()
                or "serverless" in str(r.get("product_name", "")).lower()
            ]
            normalized = [
                CostRecordNormalizer.normalize_billable_usage(r, self.config.cloud_provider, collection_time)
                for r in serverless_records
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
                raw_records=serverless_records,
                normalized_records=normalized,
            )

        # Check warehouses for serverless compute
        wh_data, wh_status, wh_err = self.client.rest_request("GET", "/api/2.0/sql/warehouses")
        if wh_status == CategoryStatus.COLLECTED and wh_data:
            warehouses = wh_data.get("warehouses", [])
            serverless_wh = [w for w in warehouses if w.get("enable_serverless_compute") is True]
            if serverless_wh:
                normalized = [
                    CostRecordNormalizer.normalize_warehouse(w, self.config.cloud_provider, None, collection_time)
                    for w in serverless_wh
                ]
                for n in normalized:
                    n.source_category = self.category_name
                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=CategoryStatus.COLLECTED,
                    records_count=len(normalized),
                    required_permission=self.required_permission,
                    raw_records=serverless_wh,
                    normalized_records=normalized,
                )
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.EMPTY,
                records_count=0,
                required_permission=self.required_permission,
                explanation="No serverless SQL warehouses or workloads currently provisioned in workspace",
            )

        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=wh_status,
            required_permission=self.required_permission,
            explanation=wh_err or "Serverless compute information could not be retrieved",
            error_details=wh_err,
        )

