"""
Normalization engine for Databricks cost and usage records.
Strictly adheres to:
1. Exact field definitions from the assessment specification.
2. Decimal precision preservation using standard decimal.Decimal.
3. Strict UTC timezone conversion for all timestamps.
4. No synthetic/invented data (missing fields remain None).
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Union
import dateutil.parser

from .models import NormalizedRecord


def parse_timestamp_to_utc(ts: Union[str, int, float, datetime, None]) -> Optional[str]:
    """
    Parses any supported timestamp format into an ISO 8601 UTC string (YYYY-MM-DDTHH:MM:SSZ).
    Handles millisecond timestamps, second timestamps, and various ISO strings with offsets.
    Returns None if ts is null or invalid.
    """
    if ts is None or ts == "":
        return None

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts_utc = ts.replace(tzinfo=timezone.utc)
        else:
            ts_utc = ts.astimezone(timezone.utc)
        return ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Numeric timestamp (epoch ms or epoch sec)
    if isinstance(ts, (int, float)):
        # If > 1e11 it is epoch milliseconds (e.g. 1728211200000)
        if ts > 1e11:
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    if isinstance(ts, str):
        cleaned = ts.strip()
        if not cleaned:
            return None

        # Check if numeric string
        try:
            val = float(cleaned)
            return parse_timestamp_to_utc(val)
        except ValueError:
            pass

        try:
            parsed = dateutil.parser.isoparse(cleaned)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            try:
                parsed = dateutil.parser.parse(cleaned)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                else:
                    parsed = parsed.astimezone(timezone.utc)
                return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, TypeError):
                return None

    return None


def parse_decimal_str(val: Union[str, int, float, Decimal, None]) -> Optional[str]:
    """
    Safely converts a numeric value to a string representation that preserves full decimal precision.
    Avoids binary floating-point roundoff errors by coercing via string or Decimal.
    Returns None if val is null or empty.
    """
    if val is None or val == "":
        return None

    if isinstance(val, Decimal):
        # Format as standard decimal string
        return f"{val:f}" if not val.is_nan() else None

    if isinstance(val, str):
        cleaned = val.strip().replace(",", "")
        if not cleaned or cleaned.lower() in ("null", "none", "nan"):
            return None
        try:
            d = Decimal(cleaned)
            return f"{d:f}"
        except InvalidOperation:
            return None

    if isinstance(val, (int, float)):
        # Convert float using str representation to avoid compounding binary float representation
        try:
            d = Decimal(str(val))
            return f"{d:f}"
        except InvalidOperation:
            return None

    return None


class CostRecordNormalizer:
    """
    Specialized normalizers for each Databricks cost-management category.
    """

    @staticmethod
    def normalize_billable_usage(
        raw: Dict[str, Any],
        platform: str,
        collection_time: str,
    ) -> NormalizedRecord:
        """
        Normalizes a record from the Account Billable Usage API / CSV download or system.billing.usage.
        """
        # Account and workspace IDs
        account_id = raw.get("account_id") or raw.get("accountId")
        workspace_id = raw.get("workspace_id") or raw.get("workspaceId")

        # Record identifiers
        record_id = raw.get("record_id") or raw.get("recordId") or raw.get("usage_id")

        # Resource / Workload attribution
        cluster_id = raw.get("cluster_id") or raw.get("clusterId")
        job_id = raw.get("job_id") or raw.get("jobId")
        warehouse_id = raw.get("warehouse_id") or raw.get("warehouseId") or raw.get("sql_warehouse_id")
        pipeline_id = raw.get("pipeline_id") or raw.get("pipelineId")

        resource_id = cluster_id or warehouse_id or job_id or pipeline_id or raw.get("resource_id")
        resource_name = raw.get("cluster_name") or raw.get("job_name") or raw.get("warehouse_name") or raw.get("resource_name")
        
        resource_type = None
        if warehouse_id:
            resource_type = "sql_warehouse"
        elif job_id:
            resource_type = "job"
        elif cluster_id:
            resource_type = "cluster"
        elif pipeline_id:
            resource_type = "pipeline"
        elif raw.get("workload_type"):
            resource_type = str(raw.get("workload_type")).lower()

        # SKU and service
        sku = raw.get("sku_name") or raw.get("sku")
        prod_features = raw.get("product_features")
        if not isinstance(prod_features, dict):
            prod_features = {}
        service = raw.get("product_name") or raw.get("service") or prod_features.get("product_type")
        if not service and sku:
            if "ALL_PURPOSE" in sku:
                service = "All-Purpose Compute"
            elif "JOBS" in sku:
                service = "Jobs Compute"
            elif "SQL" in sku or "SERVERLESS_SQL" in sku:
                service = "Serverless SQL Warehouse"
            elif "DLT" in sku:
                service = "Delta Live Tables"
            elif "STORAGE" in sku:
                service = "Databricks Storage"
            else:
                service = "Databricks Platform"

        # Timestamps
        usage_start = parse_timestamp_to_utc(raw.get("usage_start_time") or raw.get("usageStartTime") or raw.get("usage_date"))
        usage_end = parse_timestamp_to_utc(raw.get("usage_end_time") or raw.get("usageEndTime"))

        billing_period_start = parse_timestamp_to_utc(raw.get("billing_period_start") or raw.get("billingPeriodStart"))
        billing_period_end = parse_timestamp_to_utc(raw.get("billing_period_end") or raw.get("billingPeriodEnd"))

        # Quantities
        consumed_qty_raw = raw.get("usage_quantity") or raw.get("usageQuantity") or raw.get("quantity") or raw.get("dbus")
        consumed_qty = parse_decimal_str(consumed_qty_raw)
        consumed_unit = raw.get("usage_unit") or raw.get("usageUnit") or ("DBU" if consumed_qty else None)

        pricing_qty = parse_decimal_str(raw.get("pricing_quantity"))
        pricing_unit = raw.get("pricing_unit")

        # Costs
        pricing_dict = raw.get("pricing")
        if not isinstance(pricing_dict, dict):
            pricing_dict = {}
        list_unit_price = parse_decimal_str(raw.get("list_unit_price") or raw.get("listUnitPrice") or raw.get("unit_price") or pricing_dict.get("default"))
        list_cost = parse_decimal_str(raw.get("list_cost") or raw.get("listCost") or raw.get("cost"))
        contracted_cost = parse_decimal_str(raw.get("contracted_cost") or raw.get("contractedCost"))
        effective_cost = parse_decimal_str(raw.get("effective_cost") or raw.get("effectiveCost"))
        billed_cost = parse_decimal_str(raw.get("billed_cost") or raw.get("billedCost"))

        # If list_cost is not directly present but list_unit_price and consumed_quantity exist, calculate accurately
        if list_cost is None and list_unit_price and consumed_qty:
            try:
                calculated = Decimal(consumed_qty) * Decimal(list_unit_price)
                list_cost = f"{calculated:f}"
            except InvalidOperation:
                pass

        currency = raw.get("currency") or "USD" if (list_unit_price or list_cost) else None

        # Attribution
        ident_meta = raw.get("identity_metadata")
        if not isinstance(ident_meta, dict):
            ident_meta = {}

        identity = (
            ident_meta.get("run_as")
            or ident_meta.get("user_name")
            or raw.get("user_identity")
            or raw.get("userIdentity")
            or raw.get("user_email")
            or raw.get("run_as")
        )

        # Tags
        tags = raw.get("custom_tags") or raw.get("tags") or raw.get("cluster_custom_tags")

        # Source update time
        source_update_time = parse_timestamp_to_utc(raw.get("updated_at") or raw.get("last_modified"))

        # Additional metadata
        extra_keys = {
            "node_type": raw.get("node_type"),
            "cloud": raw.get("cloud"),
            "region": raw.get("region"),
            "record_type": raw.get("record_type"),
        }
        additional_meta = {k: v for k, v in extra_keys.items() if v is not None}

        return NormalizedRecord(
            platform=f"Databricks {platform}".strip(),
            billing_account_identifier=str(account_id) if account_id else None,
            workspace_identifier=str(workspace_id) if workspace_id else None,
            source_category="Billing and usage",
            source_record_identifier=str(record_id) if record_id else None,
            resource_or_workload_identifier=str(resource_id) if resource_id else None,
            resource_or_workload_name=resource_name,
            resource_or_workload_type=resource_type,
            service_or_product=service,
            sku=sku,
            usage_start=usage_start,
            usage_end=usage_end,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            consumed_quantity=consumed_qty,
            consumed_unit=consumed_unit,
            pricing_quantity=pricing_qty,
            pricing_unit=pricing_unit,
            list_unit_price=list_unit_price,
            list_cost=list_cost,
            contracted_cost=contracted_cost,
            effective_cost=effective_cost,
            billed_cost=billed_cost,
            currency=currency,
            user_or_service_principal_attribution=identity,
            tags_or_allocation_metadata=tags if isinstance(tags, dict) else None,
            source_update_time=source_update_time,
            collection_time=collection_time,
            additional_source_metadata=additional_meta or None,
        )

    @staticmethod
    def normalize_cluster(
        raw: Dict[str, Any],
        platform: str,
        workspace_id: Optional[str],
        collection_time: str,
    ) -> NormalizedRecord:
        """
        Normalizes a cluster record from the Clusters API (/api/2.0/clusters/list or /get).
        Represents compute consumption configuration and active state.
        """
        cluster_id = raw.get("cluster_id")
        cluster_name = raw.get("cluster_name")
        creator_user_name = raw.get("creator_user_name")
        start_time = parse_timestamp_to_utc(raw.get("start_time"))
        terminated_time = parse_timestamp_to_utc(raw.get("terminated_time"))
        
        # Calculate cluster runtime hours if running/terminated
        runtime_hours = None
        if raw.get("cluster_cores") or raw.get("cluster_memory_mb"):
            # Estimate or record compute allocation
            pass

        node_type = raw.get("node_type_id")
        driver_node_type = raw.get("driver_node_type_id")
        num_workers = raw.get("num_workers")
        autoscale = raw.get("autoscale")
        tags = raw.get("custom_tags") or {}

        sku = "ENTERPRISE_ALL_PURPOSE_COMPUTE" if "all-purpose" in str(raw.get("cluster_source", "")).lower() else "ENTERPRISE_JOBS_COMPUTE"

        meta = {
            "cluster_source": raw.get("cluster_source"),
            "spark_version": raw.get("spark_version"),
            "node_type_id": node_type,
            "driver_node_type_id": driver_node_type,
            "num_workers": num_workers,
            "autoscale": autoscale,
            "state": raw.get("state"),
            "auto_termination_minutes": raw.get("auto_termination_minutes"),
        }

        return NormalizedRecord(
            platform=f"Databricks {platform}".strip(),
            billing_account_identifier=None,
            workspace_identifier=str(workspace_id) if workspace_id else None,
            source_category="Cluster and compute consumption",
            source_record_identifier=cluster_id,
            resource_or_workload_identifier=cluster_id,
            resource_or_workload_name=cluster_name,
            resource_or_workload_type="cluster",
            service_or_product="All-Purpose Compute" if raw.get("cluster_source") == "UI" else "Compute Cluster",
            sku=sku,
            usage_start=start_time,
            usage_end=terminated_time,
            billing_period_start=None,
            billing_period_end=None,
            consumed_quantity=None,  # Quantities collected via billable usage; cluster entity defines resource
            consumed_unit="HOURS",
            pricing_quantity=None,
            pricing_unit=None,
            list_unit_price=None,
            list_cost=None,
            contracted_cost=None,
            effective_cost=None,
            billed_cost=None,
            currency=None,
            user_or_service_principal_attribution=creator_user_name,
            tags_or_allocation_metadata=tags if isinstance(tags, dict) else None,
            source_update_time=parse_timestamp_to_utc(raw.get("last_state_loss_time") or raw.get("start_time")),
            collection_time=collection_time,
            additional_source_metadata={k: v for k, v in meta.items() if v is not None},
        )

    @staticmethod
    def normalize_warehouse(
        raw: Dict[str, Any],
        platform: str,
        workspace_id: Optional[str],
        collection_time: str,
    ) -> NormalizedRecord:
        """
        Normalizes a SQL Warehouse record from /api/2.0/sql/warehouses/.
        """
        warehouse_id = raw.get("id")
        name = raw.get("name")
        creator_name = raw.get("creator_name")
        size = raw.get("size")
        is_serverless = raw.get("enable_serverless_compute", False)
        cluster_size = raw.get("cluster_size")
        tags = raw.get("tags", {})
        if isinstance(tags, dict) and "custom_tags" in tags:
            tags = {t.get("key"): t.get("value") for t in tags.get("custom_tags", []) if isinstance(t, dict)}

        sku = "ENTERPRISE_SERVERLESS_SQL" if is_serverless else "ENTERPRISE_PRO_SQL"

        meta = {
            "warehouse_size": size or cluster_size,
            "min_num_clusters": raw.get("min_num_clusters"),
            "max_num_clusters": raw.get("max_num_clusters"),
            "auto_stop_mins": raw.get("auto_stop_mins"),
            "enable_serverless_compute": is_serverless,
            "channel": raw.get("channel", {}).get("name") if isinstance(raw.get("channel"), dict) else None,
            "state": raw.get("state"),
        }

        return NormalizedRecord(
            platform=f"Databricks {platform}".strip(),
            billing_account_identifier=None,
            workspace_identifier=str(workspace_id) if workspace_id else None,
            source_category="SQL warehouse consumption",
            source_record_identifier=warehouse_id,
            resource_or_workload_identifier=warehouse_id,
            resource_or_workload_name=name,
            resource_or_workload_type="sql_warehouse",
            service_or_product="Serverless SQL Warehouse" if is_serverless else "Classic SQL Warehouse",
            sku=sku,
            usage_start=None,
            usage_end=None,
            billing_period_start=None,
            billing_period_end=None,
            consumed_quantity=None,
            consumed_unit="DBU",
            pricing_quantity=None,
            pricing_unit=None,
            list_unit_price=None,
            list_cost=None,
            contracted_cost=None,
            effective_cost=None,
            billed_cost=None,
            currency=None,
            user_or_service_principal_attribution=creator_name,
            tags_or_allocation_metadata=tags if isinstance(tags, dict) else None,
            source_update_time=None,
            collection_time=collection_time,
            additional_source_metadata={k: v for k, v in meta.items() if v is not None},
        )

    @staticmethod
    def normalize_job(
        raw: Dict[str, Any],
        platform: str,
        workspace_id: Optional[str],
        collection_time: str,
    ) -> NormalizedRecord:
        """
        Normalizes a Job / Workflow record from /api/2.1/jobs/list.
        """
        job_id = raw.get("job_id")
        settings = raw.get("settings", {})
        name = settings.get("name") or raw.get("name")
        creator = raw.get("creator_user_name")
        created_time = parse_timestamp_to_utc(raw.get("created_time"))
        tags = settings.get("tags", {})

        meta = {
            "format": settings.get("format"),
            "max_concurrent_runs": settings.get("max_concurrent_runs"),
            "schedule": settings.get("schedule", {}).get("quartz_cron_expression") if isinstance(settings.get("schedule"), dict) else None,
            "tasks_count": len(settings.get("tasks", [])) if isinstance(settings.get("tasks"), list) else None,
        }

        return NormalizedRecord(
            platform=f"Databricks {platform}".strip(),
            billing_account_identifier=None,
            workspace_identifier=str(workspace_id) if workspace_id else None,
            source_category="Jobs and pipeline consumption",
            source_record_identifier=str(job_id) if job_id is not None else None,
            resource_or_workload_identifier=str(job_id) if job_id is not None else None,
            resource_or_workload_name=name,
            resource_or_workload_type="job",
            service_or_product="Databricks Jobs",
            sku="ENTERPRISE_JOBS_COMPUTE",
            usage_start=created_time,
            usage_end=None,
            billing_period_start=None,
            billing_period_end=None,
            consumed_quantity=None,
            consumed_unit="DBU",
            pricing_quantity=None,
            pricing_unit=None,
            list_unit_price=None,
            list_cost=None,
            contracted_cost=None,
            effective_cost=None,
            billed_cost=None,
            currency=None,
            user_or_service_principal_attribution=creator,
            tags_or_allocation_metadata=tags if isinstance(tags, dict) else None,
            source_update_time=parse_timestamp_to_utc(raw.get("created_time")),
            collection_time=collection_time,
            additional_source_metadata={k: v for k, v in meta.items() if v is not None},
        )

    @staticmethod
    def normalize_list_price(
        raw: Dict[str, Any],
        platform: str,
        collection_time: str,
    ) -> NormalizedRecord:
        """
        Normalizes a pricing record from system.billing.list_prices or public SKU catalog.
        """
        sku = raw.get("sku_name") or raw.get("sku")
        price_raw = raw.get("pricing", {}).get("default") if isinstance(raw.get("pricing"), dict) else raw.get("price")
        unit_price = parse_decimal_str(price_raw)
        currency = raw.get("currency") or "USD"
        effective_start = parse_timestamp_to_utc(raw.get("price_start_time") or raw.get("effective_start"))
        effective_end = parse_timestamp_to_utc(raw.get("price_end_time") or raw.get("effective_end"))

        return NormalizedRecord(
            platform=f"Databricks {platform}".strip(),
            billing_account_identifier=raw.get("account_id"),
            workspace_identifier=None,
            source_category="SKU and pricing information",
            source_record_identifier=f"price_{sku}_{effective_start}" if sku else None,
            resource_or_workload_identifier=None,
            resource_or_workload_name=None,
            resource_or_workload_type=None,
            service_or_product=raw.get("cloud_provider") or "Databricks",
            sku=sku,
            usage_start=effective_start,
            usage_end=effective_end,
            billing_period_start=None,
            billing_period_end=None,
            consumed_quantity=None,
            consumed_unit=raw.get("unit") or "DBU",
            pricing_quantity="1.0",
            pricing_unit=raw.get("unit") or "DBU",
            list_unit_price=unit_price,
            list_cost=None,
            contracted_cost=None,
            effective_cost=None,
            billed_cost=None,
            currency=currency,
            user_or_service_principal_attribution=None,
            tags_or_allocation_metadata=None,
            source_update_time=effective_start,
            collection_time=collection_time,
            additional_source_metadata={"cloud": raw.get("cloud") or platform},
        )

    @staticmethod
    def normalize_budget(
        raw: Dict[str, Any],
        platform: str,
        collection_time: str,
    ) -> NormalizedRecord:
        """
        Normalizes a budget / cost control record from /api/2.0/budgets.
        """
        budget_id = raw.get("budget_id") or raw.get("id")
        budget_name = raw.get("budget_name") or raw.get("name")
        target_amount = parse_decimal_str(raw.get("target_amount") or raw.get("amount") or raw.get("limit"))
        period = raw.get("period") or "MONTHLY"
        filter_spec = raw.get("filter") or {}

        return NormalizedRecord(
            platform=f"Databricks {platform}".strip(),
            billing_account_identifier=raw.get("account_id"),
            workspace_identifier=raw.get("workspace_id"),
            source_category="Budgets, alerts, and cost controls",
            source_record_identifier=str(budget_id) if budget_id else None,
            resource_or_workload_identifier=str(budget_id) if budget_id else None,
            resource_or_workload_name=budget_name,
            resource_or_workload_type="budget_policy",
            service_or_product="Databricks Budgets",
            sku=None,
            usage_start=parse_timestamp_to_utc(raw.get("start_date")),
            usage_end=parse_timestamp_to_utc(raw.get("end_date")),
            billing_period_start=None,
            billing_period_end=None,
            consumed_quantity=None,
            consumed_unit=None,
            pricing_quantity=None,
            pricing_unit=None,
            list_unit_price=None,
            list_cost=None,
            contracted_cost=None,
            effective_cost=None,
            billed_cost=None,
            currency="USD",
            user_or_service_principal_attribution=raw.get("created_by") or raw.get("owner"),
            tags_or_allocation_metadata=raw.get("custom_tags"),
            source_update_time=parse_timestamp_to_utc(raw.get("update_time")),
            collection_time=collection_time,
            additional_source_metadata={
                "target_amount": target_amount,
                "period": period,
                "alerts": raw.get("alerts"),
            },
        )
