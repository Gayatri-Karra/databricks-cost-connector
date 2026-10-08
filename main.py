#!/usr/bin/env python3
"""
Databricks Cost Connector - Entrypoint script.
Run with:
    python main.py --mock                # Offline mode with synthetic data
    python main.py                      # Live mode using .env credentials
"""

import sys
from databricks_cost_connector.cli import main

if __name__ == "__main__":
    sys.exit(main())

