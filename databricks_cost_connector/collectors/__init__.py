"""
Registry of all Databricks cost-management collectors.
Covers all 17 categories required by the assessment specification.
"""

from typing import List, Type
from .base import BaseCostCollector
from .billable_usage import (
    BillingAndUsageCollector,
    AccountWorkspaceConsumptionCollector,
    ServerlessConsumptionCollector,
)
from .compute_usage import (
    ClusterComputeCollector,
    SQLWarehouseCollector,
    OptimizationCostSavingCollector,
)
from .jobs_pipelines import JobsAndPipelineCollector
from .pricing import SkuPricingCollector, ListCostCalculationsCollector
from .attribution import (
    ResourceWorkloadAttributionCollector,
    UserPrincipalAttributionCollector,
    TagsAllocationCollector,
)
from .governance import BudgetsCostControlsCollector, ContractCommitmentCollector
from .storage_network import (
    StorageUsageCollector,
    DataTransferNetworkCollector,
    CorrectionsRetractionsCollector,
)

ALL_COLLECTOR_CLASSES: List[Type[BaseCostCollector]] = [
    BillingAndUsageCollector,
    AccountWorkspaceConsumptionCollector,
    ClusterComputeCollector,
    SQLWarehouseCollector,
    JobsAndPipelineCollector,
    ServerlessConsumptionCollector,
    StorageUsageCollector,
    DataTransferNetworkCollector,
    SkuPricingCollector,
    ListCostCalculationsCollector,
    ResourceWorkloadAttributionCollector,
    UserPrincipalAttributionCollector,
    TagsAllocationCollector,
    BudgetsCostControlsCollector,
    CorrectionsRetractionsCollector,
    OptimizationCostSavingCollector,
    ContractCommitmentCollector,
]

__all__ = [
    "BaseCostCollector",
    "BillingAndUsageCollector",
    "AccountWorkspaceConsumptionCollector",
    "ClusterComputeCollector",
    "SQLWarehouseCollector",
    "JobsAndPipelineCollector",
    "ServerlessConsumptionCollector",
    "StorageUsageCollector",
    "DataTransferNetworkCollector",
    "SkuPricingCollector",
    "ListCostCalculationsCollector",
    "ResourceWorkloadAttributionCollector",
    "UserPrincipalAttributionCollector",
    "TagsAllocationCollector",
    "BudgetsCostControlsCollector",
    "CorrectionsRetractionsCollector",
    "OptimizationCostSavingCollector",
    "ContractCommitmentCollector",
    "ALL_COLLECTOR_CLASSES",
]

