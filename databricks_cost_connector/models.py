"""
Data models and enumeration types for Databricks cost connector.
All models preserve decimal precision and follow the assessment normalization schema.
"""

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class CategoryStatus(str, Enum):
    """
    Standard status classification required by assessment specification:
    - collected: Records were successfully retrieved and normalized.
    - empty: Endpoint/table exists and query succeeded, but 0 records were returned.
    - permission_denied: Authentication succeeded, but caller lacks necessary permissions (403/401).
    - unavailable_in_account: Feature or table is not provisioned or configured in this workspace/tier (404/Not Found).
    - unsupported: API or table is not supported on this cloud provider or workspace architecture.
    - failed: Unexpected runtime or network error occurred during collection (5xx, connection timeout).
    """
    COLLECTED = "collected"
    EMPTY = "empty"
    PERMISSION_DENIED = "permission_denied"
    UNAVAILABLE_IN_ACCOUNT = "unavailable_in_account"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass
class NormalizedRecord:
    """
    Normalized cost or usage record following assessment specification.
    Fields that do not apply must remain None (null) - values are never invented.
    Numeric values are formatted preserving full source precision without float rounding errors.
    """
    platform: Optional[str] = None
    billing_account_identifier: Optional[str] = None
    workspace_identifier: Optional[str] = None
    source_category: str = ""
    source_record_identifier: Optional[str] = None
    resource_or_workload_identifier: Optional[str] = None
    resource_or_workload_name: Optional[str] = None
    resource_or_workload_type: Optional[str] = None
    service_or_product: Optional[str] = None
    sku: Optional[str] = None
    usage_start: Optional[str] = None  # ISO 8601 UTC
    usage_end: Optional[str] = None    # ISO 8601 UTC
    billing_period_start: Optional[str] = None
    billing_period_end: Optional[str] = None
    consumed_quantity: Optional[str] = None  # Exact decimal string
    consumed_unit: Optional[str] = None
    pricing_quantity: Optional[str] = None
    pricing_unit: Optional[str] = None
    list_unit_price: Optional[str] = None
    list_cost: Optional[str] = None
    contracted_cost: Optional[str] = None
    effective_cost: Optional[str] = None
    billed_cost: Optional[str] = None
    currency: Optional[str] = None
    user_or_service_principal_attribution: Optional[str] = None
    tags_or_allocation_metadata: Optional[Dict[str, Any]] = None
    source_update_time: Optional[str] = None
    collection_time: str = ""  # ISO 8601 UTC
    additional_source_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary preserving exact keys and values."""
        return asdict(self)


@dataclass
class CollectionResult:
    """
    Result metadata for a single investigated cost-management category.
    Includes status, counts, timestamp bounds, permissions, and raw/normalized payloads.
    """
    category_name: str
    purpose: str
    status: CategoryStatus
    records_count: int = 0
    earliest_timestamp: Optional[str] = None
    latest_timestamp: Optional[str] = None
    required_permission: str = "Workspace Access"
    explanation: Optional[str] = None
    raw_records: List[Dict[str, Any]] = field(default_factory=list)
    normalized_records: List[NormalizedRecord] = field(default_factory=list)
    error_details: Optional[str] = None

    def to_summary_dict(self) -> Dict[str, Any]:
        """Summary representation suitable for coverage reporting."""
        return {
            "category_name": self.category_name,
            "purpose": self.purpose,
            "status": self.status.value,
            "records_count": self.records_count,
            "earliest_timestamp": self.earliest_timestamp,
            "latest_timestamp": self.latest_timestamp,
            "required_permission": self.required_permission,
            "explanation": self.explanation or ("Successfully retrieved" if self.status == CategoryStatus.COLLECTED else ""),
        }

