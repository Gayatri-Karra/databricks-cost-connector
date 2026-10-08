"""
SKU pricing and list-cost calculation collectors.
Extracts SKU list pricing rates and performs exact decimal precision calculations
for unadjusted list cost = consumed_quantity * list_unit_price.
"""

from decimal import Decimal, InvalidOperation
import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base import BaseCostCollector
from .billable_usage import BillingAndUsageCollector
from ..models import CategoryStatus, CollectionResult, NormalizedRecord
from ..normalizer import CostRecordNormalizer

logger = logging.getLogger("databricks_cost_connector.collectors.pricing")


class SkuPricingCollector(BaseCostCollector):
    """Collector for 'SKU and pricing information' category."""

    @property
    def category_name(self) -> str:
        return "SKU and pricing information"

    @property
    def purpose(self) -> str:
        return "Fetch public and account list prices, SKU unit rates, and pricing models per cloud region"

    @property
    def required_permission(self) -> str:
        return "Unity Catalog system schema access (system.billing.list_prices) or Pricing Catalog reader"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "list_prices.json")
            with open(fixture_path, "r", encoding="utf-8") as f:
                pricing_data = json.load(f)
            normalized = [
                CostRecordNormalizer.normalize_list_price(p, self.config.cloud_provider, collection_time)
                for p in pricing_data
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
                raw_records=pricing_data,
                normalized_records=normalized,
            )

        # In live mode, query system.billing.list_prices if warehouse_id is configured
        if self.config.warehouse_id:
            query = "SELECT * FROM system.billing.list_prices LIMIT 500"
            res, status, err = self.client.rest_request(
                "POST",
                "/api/2.0/sql/statements",
                data={"warehouse_id": self.config.warehouse_id, "statement": query, "wait_timeout": "30s"},
            )
            if status == CategoryStatus.COLLECTED and res and "result" in res:
                rows = res.get("result", {}).get("data_array", [])
                cols = [c.get("name") for c in res.get("manifest", {}).get("schema", {}).get("columns", [])]
                raw_records = [dict(zip(cols, row)) for row in rows]
                normalized = [
                    CostRecordNormalizer.normalize_list_price(p, self.config.cloud_provider, collection_time)
                    for p in raw_records
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
                    raw_records=raw_records,
                    normalized_records=normalized,
                )
            elif status == CategoryStatus.PERMISSION_DENIED:
                return CollectionResult(
                    category_name=self.category_name,
                    purpose=self.purpose,
                    status=CategoryStatus.PERMISSION_DENIED,
                    required_permission=self.required_permission,
                    explanation="Access to system.billing.list_prices denied by Unity Catalog permissions",
                    error_details=err,
                )

        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.UNAVAILABLE_IN_ACCOUNT,
            required_permission=self.required_permission,
            explanation="Unity Catalog system.billing.list_prices table is not provisioned or warehouse ID is not configured",
        )


class ListCostCalculationsCollector(BaseCostCollector):
    """Collector for 'List-cost calculations' category."""

    @property
    def category_name(self) -> str:
        return "List-cost calculations"

    @property
    def purpose(self) -> str:
        return "Calculate unadjusted list cost (consumed quantity * list unit price) preserving strict decimal precision"

    @property
    def required_permission(self) -> str:
        return "Billing Data Reader"

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
                        "list-cost calculations were not inferred from fixtures."
                    ),
                    error_details=billing_result.error_details,
                )

            raw_data = billing_result.raw_records

        calculated_records: List[NormalizedRecord] = []
        raw_calcs: List[Dict[str, Any]] = []

        for item in raw_data:
            qty_str = item.get("usage_quantity")
            price_str = item.get("list_unit_price")
            if qty_str and price_str:
                try:
                    qty = Decimal(str(qty_str))
                    price = Decimal(str(price_str))
                    cost = qty * price

                    calc_entry = {
                        "record_id": item.get("record_id"),
                        "sku_name": item.get("sku_name"),
                        "consumed_quantity": str(qty),
                        "list_unit_price": str(price),
                        "calculated_list_cost": f"{cost:f}",
                        "formula": "consumed_quantity * list_unit_price",
                        "currency": item.get("currency", "USD"),
                    }
                    raw_calcs.append(calc_entry)

                    record = CostRecordNormalizer.normalize_billable_usage(item, self.config.cloud_provider, collection_time)
                    record.source_category = self.category_name
                    record.list_cost = f"{cost:f}"
                    calculated_records.append(record)
                except (InvalidOperation, TypeError):
                    continue

        earliest, latest = self.find_timestamp_bounds(calculated_records)
        return CollectionResult(
            category_name=self.category_name,
            purpose=self.purpose,
            status=CategoryStatus.COLLECTED if calculated_records else CategoryStatus.EMPTY,
            records_count=len(calculated_records),
            earliest_timestamp=earliest,
            latest_timestamp=latest,
            required_permission=self.required_permission,
            raw_records=raw_calcs,
            normalized_records=calculated_records,
        )

