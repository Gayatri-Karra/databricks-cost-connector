"""
Budgets, cost controls, and contract/commitment information collectors.
Probes account budget policies and enterprise contract/commitment endpoints.
Accurately reports permissions and capabilities when features are unavailable on trial tiers.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base import BaseCostCollector
from ..models import CategoryStatus, CollectionResult, NormalizedRecord
from ..normalizer import CostRecordNormalizer

logger = logging.getLogger("databricks_cost_connector.collectors.governance")


class BudgetsCostControlsCollector(BaseCostCollector):
    """Collector for 'Budgets, alerts, and cost controls' category."""

    @property
    def category_name(self) -> str:
        return "Budgets, alerts, and cost controls"

    @property
    def purpose(self) -> str:
        return "Retrieve spending budgets, policy threshold alerts, and cost control limits"

    @property
    def required_permission(self) -> str:
        return "Account Administrator or Budget Policy Manager"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "budgets_response.json")
            with open(fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            budgets = data.get("budget_policies", [])
            normalized = [
                CostRecordNormalizer.normalize_budget(b, self.config.cloud_provider, collection_time)
                for b in budgets
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
                raw_records=budgets,
                normalized_records=normalized,
            )

        if not self.config.account_id:
            # Workspace level budgets probe
            data, status, err = self.client.rest_request("GET", "/api/2.0/budgets")
            if status == CategoryStatus.COLLECTED and data:
                budgets = data.get("budgets", [])
                normalized = [
                    CostRecordNormalizer.normalize_budget(b, self.config.cloud_provider, collection_time)
                    for b in budgets
                ]
                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=CategoryStatus.COLLECTED if normalized else CategoryStatus.EMPTY,
                    records_count=len(normalized),
                    required_permission=self.required_permission,
                    raw_records=budgets,
                    normalized_records=normalized,
                )
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.UNAVAILABLE_IN_ACCOUNT,
                required_permission=self.required_permission,
                explanation="Budgets API unavailable in standard workspace tier without Account Administrator credentials",
                error_details=err,
            )

        # Account level budgets endpoint
        res, status, err = self.client.rest_request(
            "GET",
            f"/api/2.0/accounts/{self.config.account_id}/budget-policies",
            is_account_api=True,
        )
        if status == CategoryStatus.COLLECTED and res:
            budgets = res.get("budget_policies", [])
            normalized = [
                CostRecordNormalizer.normalize_budget(b, self.config.cloud_provider, collection_time)
                for b in budgets
            ]
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.COLLECTED if normalized else CategoryStatus.EMPTY,
                records_count=len(normalized),
                required_permission=self.required_permission,
                raw_records=budgets,
                normalized_records=normalized,
            )

        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=status,
            required_permission=self.required_permission,
            explanation=err or "Account budget policies endpoint could not be queried",
            error_details=err,
        )


class ContractCommitmentCollector(BaseCostCollector):
    """Collector for 'Contract, commitment, or discount information where available' category."""

    @property
    def category_name(self) -> str:
        return "Contract, commitment, or discount information where available"

    @property
    def purpose(self) -> str:
        return "Identify committed use discounts, enterprise agreements (EDP/EA), and custom contracted rates"

    @property
    def required_permission(self) -> str:
        return "Enterprise Account Master Agreement / Billing Portal Access"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        # In Databricks, custom commit terms & EDP contracts are negotiated under Master Services
        # Agreements or billed through cloud provider marketplaces (AWS Marketplace / Azure Enterprise).
        # They are not exposed via standard public REST API endpoints on trial or pay-as-you-go accounts.

        if self.config.mock_mode:
            # Report accurately as unavailable_in_account or provide explanation
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.UNAVAILABLE_IN_ACCOUNT,
                records_count=0,
                required_permission=self.required_permission,
                explanation=(
                    "Contract and commitment terms are managed through cloud provider enterprise agreements "
                    "(e.g., AWS EDP, Azure EA) and are not exposed via the public Databricks REST API on trial accounts."
                ),
            )

        # In live mode, probe account contracts endpoint
        if self.config.account_id:
            _, status, err = self.client.rest_request(
                "GET",
                f"/api/2.0/accounts/{self.config.account_id}/contracts",
                is_account_api=True,
            )
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.UNAVAILABLE_IN_ACCOUNT if status in (CategoryStatus.UNAVAILABLE_IN_ACCOUNT, CategoryStatus.PERMISSION_DENIED) else status,
                records_count=0,
                required_permission=self.required_permission,
                explanation=(
                    "Contract/commitment endpoint returned unavailable or access denied. "
                    "Custom commitment contracts are only exposed for enterprise commercial accounts."
                ),
                error_details=err,
            )

        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.UNAVAILABLE_IN_ACCOUNT,
            records_count=0,
            required_permission=self.required_permission,
            explanation=(
                "Contract/commitment data requires enterprise account administration. "
                "Trial accounts operate under standard on-demand list pricing without custom committed spend."
            ),
        )

