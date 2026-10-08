"""
Collection orchestrator.
Coordinates environment discovery, sequential category collection, fault-tolerant execution,
and persistence of raw and normalized datasets.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional

from .client import DatabricksClientWrapper
from .config import DatabricksConfig
from .discovery import EnvironmentDiscovery, AccountWorkspaceDiscovery
from .models import CategoryStatus, CollectionResult
from .reporter import CoverageReporter
from .collectors import ALL_COLLECTOR_CLASSES

logger = logging.getLogger("databricks_cost_connector.orchestrator")


class CostCollectorOrchestrator:
    """
    Main execution coordinator for the Databricks Cost Connector.
    Ensures that failures or permission denials in optional categories
    do not abort the execution of subsequent categories.
    """

    def __init__(self, config: DatabricksConfig):
        self.config = config
        self.client = DatabricksClientWrapper(config)
        self.discovery_engine = EnvironmentDiscovery(self.client, config)
        self.discovery: Optional[AccountWorkspaceDiscovery] = None
        self.results: List[CollectionResult] = []

    def run(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[CollectionResult]:
        """
        Executes complete discovery and collection lifecycle.
        """
        run_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(f"=== Starting Databricks Cost Collection run at {run_start} ===")
        redacted_cfg = self.config.get_redacted_summary()
        logger.info(f"Configuration: Host={redacted_cfg['host']}, Cloud={redacted_cfg['cloud_provider']}, Account={redacted_cfg['account_id']}")

        # 1. Environment Discovery
        logger.info("Executing environment discovery...")
        self.discovery = self.discovery_engine.discover()
        logger.info(f"Discovery complete. Authenticated={self.discovery.authenticated}, Capabilities={list(self.discovery.capabilities.keys())}")
        if self.discovery.warnings:
            for w in self.discovery.warnings:
                logger.warning(f"[Discovery Advisory] {w}")

        # 2. Iterate through all 17 category collectors
        logger.info(f"Instantiating and executing {len(ALL_COLLECTOR_CLASSES)} category collectors...")
        self.results = []

        for collector_cls in ALL_COLLECTOR_CLASSES:
            collector = collector_cls(self.client, self.config)
            logger.info(f"--> Collecting category: '{collector.category_name}'...")

            try:
                result = collector.collect(start_time=start_time, end_time=end_time)
                self.results.append(result)
                logger.info(
                    f"    Result for '{result.category_name}': status={result.status.value}, records={result.records_count}"
                )
            except Exception as e:
                logger.error(f"    Unexpected failure in '{collector.category_name}': {e}", exc_info=True)
                # Continue collecting subsequent categories
                failed_res = CollectionResult(
                    category_name=collector.category_name,
                    purpose=collector.purpose,
                    status=CategoryStatus.FAILED,
                    records_count=0,
                    required_permission=collector.required_permission,
                    explanation=f"Runtime error during execution: {str(e)}",
                    error_details=str(e),
                )
                self.results.append(failed_res)

        # 3. Save raw and normalized output files
        logger.info(f"Persisting collected datasets to '{self.config.output_dir}'...")
        saved_paths = CoverageReporter.save_outputs(self.results, self.config.output_dir)
        logger.info(f"Outputs successfully generated: {saved_paths}")

        run_end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(f"=== Collection run finished at {run_end} ===")

        return self.results

