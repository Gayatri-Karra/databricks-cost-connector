"""
Storage usage, data-transfer/network usage, and corrections/retractions collectors.
Extracts storage metrics, cloud network egress fees, and audit billing restatements.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base import BaseCostCollector
from .billable_usage import BillingAndUsageCollector
from ..models import CategoryStatus, CollectionResult, NormalizedRecord
from ..normalizer import CostRecordNormalizer

logger = logging.getLogger("databricks_cost_connector.collectors.storage_network")


class StorageUsageCollector(BaseCostCollector):
    """Collector for 'Storage-related usage' category."""

    @property
    def category_name(self) -> str:
        return "Storage-related usage"

    @property
    def purpose(self) -> str:
        return "Track DBFS, Unity Catalog managed storage, external volumes, and system metastore storage fees"

    @property
    def required_permission(self) -> str:
        return "Metastore Admin or System Tables Reader (system.billing.usage)"

    def collect(self, start_time=None, end_time=None) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(
                os.path.dirname(__file__), "..", "..",
                "fixtures", "billable_usage_records.json"
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
                    explanation="Live billing usage data was not available; storage usage was not inferred from fixtures.",
                    error_details=billing_result.error_details,
                )

            raw_data = billing_result.raw_records

        storage_records = [
            r for r in raw_data
            if "STORAGE" in str(r.get("sku_name", "")).upper()
            or "storage" in str(r.get("product_name", "")).lower()
        ]

        normalized = [
            CostRecordNormalizer.normalize_billable_usage(
                r, self.config.cloud_provider, collection_time
            )
            for r in storage_records
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
            raw_records=storage_records,
            normalized_records=normalized,
        )


class DataTransferNetworkCollector(BaseCostCollector):
    """Collector for 'Data-transfer or network-related usage' category."""

    @property
    def category_name(self) -> str:
        return "Data-transfer or network-related usage"

    @property
    def purpose(self) -> str:
        return "Track cross-region network egress, internet data transfer, and inter-cloud data movement fees"

    @property
    def required_permission(self) -> str:
        return "Account Administrator or Unity Catalog System Tables Reader"

    def collect(self, start_time=None, end_time=None) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(
                os.path.dirname(__file__), "..", "..",
                "fixtures", "billable_usage_records.json"
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
                    explanation="Live billing usage data was not available; network usage was not inferred from fixtures.",
                    error_details=billing_result.error_details,
                )

            raw_data = billing_result.raw_records

        network_records = [
            r for r in raw_data
            if "DATA_TRANSFER" in str(r.get("sku_name", "")).upper()
            or "EGRESS" in str(r.get("sku_name", "")).upper()
            or "network" in str(r.get("product_name", "")).lower()
        ]

        normalized = [
            CostRecordNormalizer.normalize_billable_usage(
                r, self.config.cloud_provider, collection_time
            )
            for r in network_records
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
            raw_records=network_records,
            normalized_records=normalized,
        )


class CorrectionsRetractionsCollector(BaseCostCollector):
    """Collector for 'Corrections, retractions, or restatements' category."""

    @property
    def category_name(self) -> str:
        return "Corrections, retractions, or restatements"

    @property
    def purpose(self) -> str:
        return "Identify historical usage adjustments, billing corrections, and negative DBU restatements"

    @property
    def required_permission(self) -> str:
        return "Account Billing Auditor (system.billing.usage or usage download)"

    def collect(self, start_time=None, end_time=None) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(
                os.path.dirname(__file__), "..", "..",
                "fixtures", "billable_usage_records.json"
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
                    explanation="Live billing usage data was not available; corrections were not inferred from fixtures.",
                    error_details=billing_result.error_details,
                )

            raw_data = billing_result.raw_records

        retractions = [
            r for r in raw_data
            if str(r.get("record_type", "")).upper() == "RETRACTION"
            or (
                r.get("usage_quantity")
                and str(r.get("usage_quantity")).startswith("-")
            )
        ]

        normalized = [
            CostRecordNormalizer.normalize_billable_usage(
                r, self.config.cloud_provider, collection_time
            )
            for r in retractions
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
            explanation=(
                "Successfully captured billing retractions/adjustments"
                if normalized
                else "No billing restatements recorded in period"
            ),
            raw_records=retractions,
            normalized_records=normalized,
        )