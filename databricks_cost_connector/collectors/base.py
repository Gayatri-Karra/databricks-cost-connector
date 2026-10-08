"""
Base collector interface and shared functionality for Databricks cost categories.
Provides error isolation, timestamp normalization, and standardized result structures.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from ..client import DatabricksClientWrapper
from ..config import DatabricksConfig
from ..models import CategoryStatus, CollectionResult, NormalizedRecord

logger = logging.getLogger("databricks_cost_connector.collectors")


class BaseCostCollector(ABC):
    """
    Abstract base class for all Databricks cost-management category collectors.
    """

    def __init__(self, client: DatabricksClientWrapper, config: DatabricksConfig):
        self.client = client
        self.config = config

    @property
    @abstractmethod
    def category_name(self) -> str:
        """Name of the cost-management category investigated."""
        pass

    @property
    @abstractmethod
    def purpose(self) -> str:
        """Business and technical purpose of this dataset."""
        pass

    @property
    @abstractmethod
    def required_permission(self) -> str:
        """Required permission or account capability."""
        pass

    @abstractmethod
    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        """
        Executes the collection attempt for this category.
        Returns CollectionResult containing status, records, timestamp bounds, and metadata.
        """
        pass

    def get_collection_time(self) -> str:
        """Returns current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def find_timestamp_bounds(
        self,
        records: List[NormalizedRecord],
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Extracts the earliest and latest timestamps across normalized records.
        Evaluates usage_start, usage_end, or source_update_time.
        """
        timestamps: List[str] = []
        for r in records:
            for ts in (r.usage_start, r.usage_end, r.source_update_time):
                if ts:
                    timestamps.append(ts)

        if not timestamps:
            return None, None

        timestamps.sort()
        return timestamps[0], timestamps[-1]

