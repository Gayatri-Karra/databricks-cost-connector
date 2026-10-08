# Databricks Cost Connector

A production-grade Python connector that connects to Databricks accounts and workspaces, discovers available cost-management vectors, exhaustively collects all accessible datasets across 17 distinct categories, and normalizes them into a unified schema with strict decimal precision and UTC standardization.

---

## Key Features

1. **Full 17-Category Coverage**:
   Investigates every cost-management category specified in the assessment:
   - Billing and usage
   - Account and workspace consumption
   - Cluster and compute consumption
   - SQL warehouse consumption
   - Jobs and pipeline consumption
   - Serverless consumption
   - Storage-related usage
   - Data-transfer or network-related usage
   - SKU and pricing information
   - List-cost calculations
   - Resource and workload attribution
   - User and service-principal attribution
   - Tags and allocation metadata
   - Budgets, alerts, and cost controls
   - Corrections, retractions, or restatements
   - Optimization and cost-saving information
   - Contract, commitment, or discount information

2. **Accurate Status Categorization**:
   Distinguishes between:
   - `collected`: Data successfully extracted and normalized.
   - `empty`: Category query succeeded, but 0 records currently exist.
   - `permission_denied`: Valid authentication, but caller lacks necessary privileges (HTTP 401/403).
   - `unavailable_in_account`: Feature, table, or schema not provisioned in this workspace/tier (HTTP 404).
   - `unsupported`: Feature not supported by this cloud provider or workspace architecture.
   - `failed`: Unexpected network or runtime error.
   *No category is ever silently omitted.*

3. **Strict Decimal Precision & UTC Formatting**:
   - Uses Python's standard `decimal.Decimal` module to avoid binary IEEE-754 floating-point drift on micro-DBU quantities (e.g. `0.123456789012345678` DBUs) and unit pricing.
   - Normalizes all epoch timestamps and localized strings to canonical ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`).
   - Fields that do not apply remain `null` (`None`); missing data is never fabricated.

4. **Resilient & Fault-Tolerant Execution**:
   - Sequential, isolated collector execution ensures that permission denials or unavailable optional endpoints do not terminate the collection of subsequent categories.
   - Lazy SDK initialization ensures the client never hangs on unresolved endpoints or during offline evaluation.

5. **Multi-Mode Support**:
   - **Live Mode**: Authenticates with real Databricks workspaces and accounts using PAT or OAuth M2M credentials.
   - **Mock/Offline Mode**: Allows reviewers and automated CI test suites to evaluate the complete end-to-end pipeline using realistic synthetic fixtures without needing live Databricks credentials.

---

## Project Structure

```text
├── databricks_cost_connector/        # Core connector package
│   ├── __init__.py
│   ├── config.py                     # Environment variables, validation, and safe redaction
│   ├── client.py                     # Official Databricks SDK wrapper & resilient REST client
│   ├── discovery.py                  # Environment and capability discovery engine
│   ├── models.py                     # NormalizedRecord, CategoryStatus, CollectionResult
│   ├── normalizer.py                 # Decimal and UTC normalization logic
│   ├── orchestrator.py               # Fault-tolerant collection orchestrator
│   ├── reporter.py                   # Markdown & JSON coverage report generator
│   ├── cli.py                        # Command-line interface
│   └── collectors/                   # 17 Category-specific collector implementations
│       ├── __init__.py               # Registry of all 17 collectors
│       ├── base.py                   # BaseCostCollector abstract class
│       ├── billable_usage.py         # Billing, workspace aggregation, serverless
│       ├── compute_usage.py          # Clusters, SQL warehouses, cost optimization
│       ├── jobs_pipelines.py         # Jobs, multi-task workflows, DLT pipelines
│       ├── pricing.py                # SKU list prices, list-cost calculations
│       ├── attribution.py            # Workload, SCIM user/principal, tags
│       ├── governance.py             # Budgets, alerts, commitment contracts
│       └── storage_network.py        # Storage metrics, network egress, retractions
│
├── fixtures/                         # Realistic synthetic Databricks API payloads
│   ├── billable_usage_records.json
│   ├── clusters_response.json
│   ├── warehouses_response.json
│   ├── jobs_response.json
│   ├── list_prices.json
│   └── budgets_response.json
│
├── output/                           # Generated sample artifacts
│   ├── raw/                          # Source JSON payloads per category
│   ├── normalized/                   # Normalized JSONs & all_normalized.jsonl
│   ├── coverage_report.md            # Markdown coverage table
│   └── coverage_report.json          # Machine-readable coverage report
│
├── tests/                            # Automated test suite (24 tests)
│   ├── conftest.py
│   ├── test_normalization.py
│   ├── test_decimal_precision.py
│   ├── test_timestamp_handling.py
│   ├── test_empty_results.py
│   ├── test_malformed_records.py
│   └── test_auth_and_permissions.py
│
├── main.py                           # Convenient root execution script
├── requirements.txt                  # Pinned dependencies
├── .env.example                      # Safe environment variable template
├── coverage_report.md                # Root copy of coverage report
├── execution_evidence.md             # Redacted live execution evidence
├── AI_DISCLOSURE.md                  # AI tools usage disclosure note
├── pytest.ini                        # Pytest configuration
└── .gitignore                        # Git ignore file
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, 3.13)

### 2. Create Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Credentials (For Live Runs)
Copy `.env.example` to `.env` and fill in your Databricks connection details:
```bash
cp .env.example .env
```

Key environment variables:
- `DATABRICKS_HOST`: Workspace URL (e.g. `https://dbc-xxxx.cloud.databricks.com` or `https://adb-xxxx.azuredatabricks.net`)
- `DATABRICKS_TOKEN`: Personal Access Token (dapi...)
- `DATABRICKS_ACCOUNT_ID`: Databricks Account UUID (for account-level usage & budgets)
- `DATABRICKS_WAREHOUSE_ID`: Optional SQL Warehouse ID for Unity Catalog system tables

---

## Running the Connector

### Offline Evaluation Mode (No credentials required)
Reviewers can verify the entire pipeline, data normalization, and report generation immediately:
```bash
python main.py --mock
```

### Live Connection Run
When `.env` credentials are configured:
```bash
python main.py --start-date 2026-10-01 --end-date 2026-10-06
```

### Command-Line Arguments
- `--mock`: Run with synthetic fixtures without connecting to Databricks.
- `--start-date` / `--start-time`: Beginning of collection window (e.g., `2026-10-01`).
- `--end-date` / `--end-time`: End of collection window (e.g., `2026-10-31`).
- `--output-dir`: Output directory path (defaults to `output`).
- `--log-level`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- `--env-file`: Custom path to `.env` file.

---

## Running Automated Tests

All tests run hermetically and offline without requiring network access or external credentials:

```bash
pytest -v
```

### Test Coverage Highlights
- `test_normalization.py`: Verifies accurate mapping against the 29-field normalized schema. Ensures unmapped fields remain `null`.
- `test_decimal_precision.py`: Verifies micro-precision retention and exact arithmetic multiplication (`consumed_quantity * list_unit_price`).
- `test_timestamp_handling.py`: Tests epoch milliseconds, epoch seconds, localized ISO strings with offsets, and UTC conversion.
- `test_empty_results.py`: Verifies HTTP 200 with 0 records maps to `CategoryStatus.EMPTY`.
- `test_malformed_records.py`: Verifies robust recovery from bad types, non-dict nested structures, and missing keys without crashing.
- `test_auth_and_permissions.py`: Verifies HTTP 401/403 maps to `permission_denied`, HTTP 404 to `unavailable_in_account`, and orchestrator fault-tolerance when optional categories fail.

---

## Output Datasets

Running the connector populates the `output/` folder:
- `output/raw/<category>.json`: Verbatim source payload from the Databricks API or query.
- `output/normalized/<category>.json`: Normalized records adhering strictly to the assessment schema.
- `output/normalized/all_normalized.jsonl`: Stream of all normalized records in newline-delimited JSON format.
- `output/coverage_report.md`: Markdown table detailing all 17 categories.
- `output/coverage_report.json`: JSON summary of category statuses and record counts.

---

## Deliverables Summary

- [requirements.txt](file:///c:/Users/GAYATRI/OneDrive/Desktop/Geak%20minds/requirements.txt): Pinned dependencies.
- [.env.example](file:///c:/Users/GAYATRI/OneDrive/Desktop/Geak%20minds/.env.example): Safe environment variable template.
- [coverage_report.md](file:///c:/Users/GAYATRI/OneDrive/Desktop/Geak%20minds/coverage_report.md): Complete 17-category coverage audit.
- [execution_evidence.md](file:///c:/Users/GAYATRI/OneDrive/Desktop/Geak%20minds/execution_evidence.md): Redacted live execution logs.
- [AI_DISCLOSURE.md](file:///c:/Users/GAYATRI/OneDrive/Desktop/Geak%20minds/AI_DISCLOSURE.md): Note describing AI tools used.

