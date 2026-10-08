# Live Execution Evidence — Databricks Cost Connector

This document records the latest live execution of the Databricks Cost Connector against a real Databricks trial workspace. Sensitive authentication details, workspace identifiers, account identifiers, and user identity information are intentionally omitted.

---

## 1. Execution Command & Environment

The connector was executed in live mode using the configured Databricks workspace credentials:

```text
.venv\Scripts\python.exe main.py --start-time 2026-10-06T00:00:00Z --end-time 2026-10-06T23:59:59Z
```

The configured credentials were loaded from the local environment and were not included in this evidence document.

---

## 2. Test and Live Execution Results
Live execution date: 2026-10-07
Collection window: 2026-10-06T00:00:00Z to 2026-10-06T23:59:59Z

Focused automated tests were executed before the live collection:

```text
24 passed in 0.09s
```

The live execution then successfully authenticated to the Databricks workspace and completed environment discovery.

Sensitive workspace host, user identity, token, and account identifiers are intentionally omitted from this document.

```text
Authentication: successful
Environment discovery: completed
Detected capabilities:
- clusters_api
- sql_warehouses_api
- jobs_api
- account_api
- budgets_api

Total category collectors executed: 17
Total normalized records generated: 8
```

The live run completed successfully and generated the requested coverage and normalized output files.

---

## 3. Live Coverage Results

The following table records the result of every investigated cost-management category.

| Category | Status | Records | Evidence / Explanation |
|---|---|---:|---|
| Billing and usage | `unavailable_in_account` | 0 | Live billing usage was not accessible in the configured trial workspace. No fixture data was substituted. |
| Account and workspace consumption | `unavailable_in_account` | 0 | Account/workspace-level consumption was not available with the configured workspace access. |
| Cluster and compute consumption | `empty` | 0 | The accessible cluster API returned no records for the requested time window. |
| SQL warehouse consumption | `collected` | 1 | One live SQL warehouse record was collected. |
| Jobs and pipeline consumption | `empty` | 0 | The accessible Jobs API returned no records for the requested time window. |
| Serverless consumption | `collected` | 1 | One live serverless-related record was collected. |
| Storage-related usage | `unavailable_in_account` | 0 | Required live billing/storage usage data was not accessible. No fixture inference was used. |
| Data-transfer or network-related usage | `unavailable_in_account` | 0 | Required live billing/network usage data was not accessible. No fixture inference was used. |
| SKU and pricing information | `unavailable_in_account` | 0 | Required live pricing information was not accessible in the configured account/workspace context. |
| List-cost calculations | `unavailable_in_account` | 0 | Required live usage/pricing inputs were unavailable, so list cost was not fabricated or inferred from fixtures. |
| Resource and workload attribution | `unavailable_in_account` | 0 | Required live billing/resource attribution data was unavailable. |
| User and service-principal attribution | `collected` | 1 | One live user/service-principal attribution record was collected. |
| Tags and allocation metadata | `unavailable_in_account` | 0 | Required live billing/tag allocation data was unavailable. |
| Budgets, alerts, and cost controls | `unavailable_in_account` | 0 | Budget information was not available in the configured trial account. |
| Corrections, retractions, or restatements | `unavailable_in_account` | 0 | Required live billing correction data was unavailable. |
| Optimization and cost-saving information | `collected` | 5 | Five live optimization-related records were collected. |
| Contract, commitment, or discount information | `unavailable_in_account` | 0 | Contract/commitment information was not available in the configured trial account. |

### Coverage Summary

- **Total categories investigated:** 17
- **Collected:** 4
- **Empty:** 2
- **Unavailable in account:** 11
- **Permission denied:** 0
- **Unsupported:** 0
- **Failed:** 0
- **Total normalized records:** 8

Categories that were inaccessible or empty were explicitly reported rather than silently omitted.

---

## 4. Environment and Permission Findings

The live discovery phase verified successful workspace authentication and identified the following accessible API capabilities:

```text
clusters_api
sql_warehouses_api
jobs_api
account_api
budgets_api
```

The configured workspace credentials were sufficient to authenticate to the workspace and access several workspace-level APIs.

Account-level and billing-dependent functionality was not fully available in the configured trial workspace. In particular, the connector did not treat inaccessible billing data as zero usage and did not substitute fixture records during live execution.

The account identifier was not configured for account-level usage collection, so account-level consumption could not be collected.

---

## 5. Output Evidence

The live execution generated the following outputs:

```text
output/coverage_report.md
output/coverage_report.json
output/normalized/all_normalized.jsonl
```

The collection run produced:

```text
total_normalized_records: 8
```

Raw category-level records are retained under the raw output directory, while normalized records are retained under the normalized output directory.

The normalized combined JSONL contains the successfully collected live records in the connector's normalized schema.

---

## 6. Data Integrity and Fixture Isolation

The latest live run was performed against the configured Databricks workspace.

Fixture data is used only for mock/offline execution and testing. During the live execution, categories whose required Databricks data was unavailable were reported with an appropriate status and zero records rather than being populated from fixtures.

This ensures that the live evidence represents actual accessible Databricks data and account/workspace limitations.

---

## 7. Final Execution Status

The connector completed the latest live run successfully.

```text
Automated tests: 24 passed
Categories investigated: 17
Live categories collected: 4
Empty categories: 2
Unavailable categories: 11
Normalized records: 8
Execution failures: 0
```

All sensitive authentication and workspace information has been excluded from this document.