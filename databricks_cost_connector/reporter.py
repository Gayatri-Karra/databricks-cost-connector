"""
Reporting and output generation engine for Databricks cost connector.
Generates:
1. Markdown and JSON coverage reports matching the 7 required columns.
2. Formatted terminal execution summaries.
3. Raw JSON payloads and normalized JSON/JSONL output files.
"""

from dataclasses import asdict
import json
import logging
import os
from typing import Any, Dict, List

from .models import CollectionResult, CategoryStatus

logger = logging.getLogger("databricks_cost_connector.reporter")


class CoverageReporter:
    """Formats and exports collection results and coverage reports."""

    @staticmethod
    def generate_markdown_report(results: List[CollectionResult]) -> str:
        """
        Generates standard Markdown table matching assessment specification:
        - Category or dataset name
        - Purpose
        - Status
        - Number of records
        - Earliest and latest source timestamps
        - Required permission or account capability
        - Explanation when records were not collected
        """
        lines = [
            "# Databricks Cost-Management Coverage Report",
            "",
            "| Category or dataset name | Purpose | Status | Number of records | Earliest and latest source timestamps | Required permission or account capability | Explanation when records were not collected |",
            "| :--- | :--- | :--- | :---: | :--- | :--- | :--- |",
        ]

        for r in results:
            # Format timestamps
            if r.earliest_timestamp and r.latest_timestamp:
                ts_str = f"`{r.earliest_timestamp}` to `{r.latest_timestamp}`"
            elif r.earliest_timestamp:
                ts_str = f"`{r.earliest_timestamp}`"
            else:
                ts_str = "N/A"

            explanation = (r.explanation or "").replace("|", "\\|").replace("\n", " ").strip()
            if not explanation and r.status == CategoryStatus.COLLECTED:
                explanation = "Records successfully collected and normalized"
            elif not explanation:
                explanation = "N/A"

            purpose = r.purpose.replace("|", "\\|")
            perm = r.required_permission.replace("|", "\\|")

            status_badge = f"`{r.status.value}`"

            row = f"| **{r.category_name}** | {purpose} | {status_badge} | {r.records_count} | {ts_str} | {perm} | {explanation} |"
            lines.append(row)

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def generate_json_report(results: List[CollectionResult]) -> Dict[str, Any]:
        """Generates machine-readable JSON coverage report."""
        summary = {
            "total_categories_investigated": len(results),
            "status_counts": {
                CategoryStatus.COLLECTED.value: sum(1 for r in results if r.status == CategoryStatus.COLLECTED),
                CategoryStatus.EMPTY.value: sum(1 for r in results if r.status == CategoryStatus.EMPTY),
                CategoryStatus.PERMISSION_DENIED.value: sum(1 for r in results if r.status == CategoryStatus.PERMISSION_DENIED),
                CategoryStatus.UNAVAILABLE_IN_ACCOUNT.value: sum(1 for r in results if r.status == CategoryStatus.UNAVAILABLE_IN_ACCOUNT),
                CategoryStatus.UNSUPPORTED.value: sum(1 for r in results if r.status == CategoryStatus.UNSUPPORTED),
                CategoryStatus.FAILED.value: sum(1 for r in results if r.status == CategoryStatus.FAILED),
            },
            "categories": [r.to_summary_dict() for r in results],
        }
        return summary

    @staticmethod
    def save_outputs(
        results: List[CollectionResult],
        output_dir: str,
    ) -> Dict[str, str]:
        """
        Saves raw records, normalized records, and coverage reports to disk.
        Produces:
        - output/raw/<sanitized_category>.json
        - output/normalized/<sanitized_category>.json
        - output/normalized/all_normalized.jsonl
        - coverage_report.md
        - coverage_report.json
        """
        raw_dir = os.path.join(output_dir, "raw")
        norm_dir = os.path.join(output_dir, "normalized")
        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(norm_dir, exist_ok=True)

        all_normalized_path = os.path.join(norm_dir, "all_normalized.jsonl")
        total_normalized = 0

        with open(all_normalized_path, "w", encoding="utf-8") as jsonl_file:
            for r in results:
                cat_slug = r.category_name.lower().replace(" ", "_").replace(",", "").replace("-", "_")

                # Save raw
                raw_path = os.path.join(raw_dir, f"{cat_slug}.json")
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(r.raw_records, f, indent=2)

                # Save normalized
                norm_path = os.path.join(norm_dir, f"{cat_slug}.json")
                norm_dicts = [rec.to_dict() for rec in r.normalized_records]
                with open(norm_path, "w", encoding="utf-8") as f:
                    json.dump(norm_dicts, f, indent=2)

                # Append to JSONL
                for rec in r.normalized_records:
                    jsonl_file.write(json.dumps(rec.to_dict()) + "\n")
                    total_normalized += 1

        # Save Coverage Reports
        md_content = CoverageReporter.generate_markdown_report(results)
        md_path = os.path.join(output_dir, "coverage_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        json_summary = CoverageReporter.generate_json_report(results)
        json_path = os.path.join(output_dir, "coverage_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_summary, f, indent=2)

        return {
            "markdown_report": md_path,
            "json_report": json_path,
            "jsonl_normalized": all_normalized_path,
            "total_normalized_records": str(total_normalized),
        }
