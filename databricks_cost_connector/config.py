"""
Configuration loader and validator for Databricks connection.
Reads credentials from environment variables and supports .env file auto-loading.
Provides safe redaction utilities for logs and evidence.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict
from dotenv import load_dotenv


@dataclass
class DatabricksConfig:
    """
    Holds connection and execution parameters for Databricks workspace and account.
    """
    host: Optional[str] = None
    token: Optional[str] = None
    account_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    warehouse_id: Optional[str] = None
    cloud_provider: str = "AWS"
    output_dir: str = "output"
    log_level: str = "INFO"
    mock_mode: bool = False

    @classmethod
    def from_env(cls, env_file: Optional[str] = None, mock_mode: bool = False) -> "DatabricksConfig":
        """
        Load configuration from environment variables, optionally reading an env file.
        """
        if env_file and os.path.exists(env_file):
            load_dotenv(env_file, override=True)
        else:
            load_dotenv()

        host = os.getenv("DATABRICKS_HOST", "").strip() or None
        if host:
            # Clean protocol and trailing slash
            if not host.startswith("http://") and not host.startswith("https://"):
                host = f"https://{host}"
            host = host.rstrip("/")

        token = os.getenv("DATABRICKS_TOKEN", "").strip() or None
        account_id = os.getenv("DATABRICKS_ACCOUNT_ID", "").strip() or None
        client_id = os.getenv("DATABRICKS_CLIENT_ID", "").strip() or None
        client_secret = os.getenv("DATABRICKS_CLIENT_SECRET", "").strip() or None
        warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID", "").strip() or None
        output_dir = os.getenv("OUTPUT_DIR", "output").strip()
        log_level = os.getenv("LOG_LEVEL", "INFO").strip()

        # Cloud provider inference
        cloud_provider = os.getenv("DATABRICKS_CLOUD_PROVIDER", "").strip().upper()
        if not cloud_provider and host:
            if "azuredatabricks.net" in host.lower():
                cloud_provider = "AZURE"
            elif "gcp.databricks.com" in host.lower():
                cloud_provider = "GCP"
            else:
                cloud_provider = "AWS"
        elif not cloud_provider:
            cloud_provider = "AWS"

        return cls(
            host=host,
            token=token,
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
            warehouse_id=warehouse_id,
            cloud_provider=cloud_provider,
            output_dir=output_dir,
            log_level=log_level,
            mock_mode=mock_mode,
        )

    @property
    def has_workspace_auth(self) -> bool:
        """Checks if minimum credentials for workspace access are provided."""
        if self.mock_mode:
            return True
        return bool(self.host and (self.token or (self.client_id and self.client_secret)))

    @property
    def has_account_auth(self) -> bool:
        """Checks if credentials for account-level APIs are provided."""
        if self.mock_mode:
            return True
        return bool(self.account_id and (self.token or (self.client_id and self.client_secret)))

    @staticmethod
    def mask_string(val: Optional[str], show_prefix: int = 4, show_suffix: int = 4) -> str:
        """Safely masks sensitive identifiers and tokens."""
        if not val:
            return "<not set>"
        if len(val) <= (show_prefix + show_suffix + 2):
            return "***"
        return f"{val[:show_prefix]}...{val[-show_suffix:]}"

    def get_redacted_summary(self) -> Dict[str, str]:
        """Provides a safe dictionary for logging without leaking secrets."""
        host_masked = "<not set>"
        if self.host:
            # Mask workspace prefix
            parts = self.host.replace("https://", "").replace("http://", "").split(".")
            if len(parts) > 1:
                host_masked = f"https://dbc-***.{'.'.join(parts[1:])}"
            else:
                host_masked = "https://***"

        return {
            "host": host_masked,
            "token_configured": "True" if self.token else "False",
            "account_id": self.mask_string(self.account_id),
            "oauth_m2m_configured": "True" if (self.client_id and self.client_secret) else "False",
            "warehouse_id": self.mask_string(self.warehouse_id),
            "cloud_provider": self.cloud_provider,
            "mock_mode": str(self.mock_mode),
        }

