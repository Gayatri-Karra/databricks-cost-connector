"""
Jobs and pipelines consumption collector.
Paginates through Databricks Workflows / Jobs API (/api/2.1/jobs/list) and
Delta Live Tables Pipelines API (/api/2.0/pipelines) to attribute automated workload spend.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .base import BaseCostCollector
from ..models import CategoryStatus, CollectionResult, NormalizedRecord
from ..normalizer import CostRecordNormalizer

logger = logging.getLogger("databricks_cost_connector.collectors.jobs_pipelines")


class JobsAndPipelineCollector(BaseCostCollector):
    """Collector for 'Jobs and pipeline consumption' category."""

    @property
    def category_name(self) -> str:
        return "Jobs and pipeline consumption"

    @property
    def purpose(self) -> str:
        return "Map workload consumption to scheduled Jobs, Multi-Task DAGs, and Delta Live Tables (DLT) pipelines"

    @property
    def required_permission(self) -> str:
        return "Workspace Access (CAN_VIEW on Jobs and DLT Pipelines)"

    def collect(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> CollectionResult:
        collection_time = self.get_collection_time()

        if self.config.mock_mode:
            fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "jobs_response.json")
            with open(fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            jobs = data.get("jobs", [])
            normalized = [
                CostRecordNormalizer.normalize_job(j, self.config.cloud_provider, None, collection_time)
                for j in jobs
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
                raw_records=jobs,
                normalized_records=normalized,
            )

        # Retrieve jobs with pagination
        jobs, status, err = self.client.paginate_rest_get(
            path="/api/2.1/jobs/list",
            records_key="jobs",
            page_size=50,
        )

        if status != CategoryStatus.COLLECTED and status != CategoryStatus.EMPTY:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=status,
                required_permission=self.required_permission,
                explanation=err,
                error_details=err,
            )

        if not jobs:
            return CollectionResult(
                category_name=self.category_name,
                purpose=self.purpose,
                status=CategoryStatus.EMPTY,
                records_count=0,
                required_permission=self.required_permission,
                explanation="No jobs or scheduled pipelines configured in workspace",
            )

        normalized = [
            CostRecordNormalizer.normalize_job(j, self.config.cloud_provider, None, collection_time)
            for j in jobs
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
            raw_records=jobs,
            normalized_records=normalized,
        )

