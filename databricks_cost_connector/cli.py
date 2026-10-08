"""
Command Line Interface (CLI) for Databricks Cost Connector.
Supports date range filtering, mock execution, custom output directories,
and live environment execution.
"""

import argparse
import logging
import sys
from typing import Optional

from .config import DatabricksConfig
from .orchestrator import CostCollectorOrchestrator
from .reporter import CoverageReporter


def setup_logging(level_name: str = "INFO") -> None:
    """Configures structured console logging."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args(args: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Databricks Cost Connector: Live extraction, collection, and normalization",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Path to custom .env configuration file",
    )
    parser.add_argument(
        "--start-time",
        "--start-date",
        type=str,
        default=None,
        dest="start_time",
        help="Start timestamp or date (e.g. '2026-10-01' or '2026-10-01T00:00:00Z')",
    )
    parser.add_argument(
        "--end-time",
        "--end-date",
        type=str,
        default=None,
        dest="end_time",
        help="End timestamp or date (e.g. '2026-10-31' or '2026-10-31T23:59:59Z')",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save raw payloads, normalized records, and coverage report",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock/offline mode using synthetic test fixtures without requiring live credentials",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    parser.add_argument(
        "--print-report",
        action="store_true",
        default=True,
        help="Print coverage report table to console upon completion",
    )
    return parser.parse_args(args)


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger("databricks_cost_connector.cli")

    config = DatabricksConfig.from_env(env_file=args.env_file, mock_mode=args.mock)
    if args.output_dir:
        config.output_dir = args.output_dir

    if not config.has_workspace_auth and not args.mock:
        logger.warning(
            "No Databricks credentials detected in environment. "
            "To test without live credentials, rerun with '--mock'."
        )
        # Attempt running anyway - discovery will record authentication failure
        # and category statuses will accurately reflect permission_denied or unavailable_in_account

    orchestrator = CostCollectorOrchestrator(config)
    results = orchestrator.run(start_time=args.start_time, end_time=args.end_time)

    if args.print_report:
        md_report = CoverageReporter.generate_markdown_report(results)
        print("\n" + "=" * 80)
        print(md_report)
        print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

