"""
Databricks Client Wrapper.
Provides robust workspace and account API access via the official Databricks SDK
and resilient direct REST calls for specialized billing and system endpoints.
Includes status code translation to assessment standard statuses and lazy SDK initialization.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import requests
from requests.exceptions import RequestException

from .config import DatabricksConfig
from .models import CategoryStatus

logger = logging.getLogger("databricks_cost_connector.client")

try:
    from databricks.sdk import WorkspaceClient, AccountClient
    from databricks.sdk.core import DatabricksError
    HAS_DATABRICKS_SDK = True
except ImportError:
    HAS_DATABRICKS_SDK = False
    WorkspaceClient = None
    AccountClient = None
    DatabricksError = Exception


class DatabricksClientWrapper:
    """
    Unified client for Databricks Workspace & Account APIs.
    Gracefully manages authentication, pagination, rate limits, and error status mapping.
    SDK clients are initialized lazily to avoid blocking on non-existent hosts or offline testing.
    """

    def __init__(self, config: DatabricksConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Databricks-Cost-Connector/1.0.0",
            "Content-Type": "application/json",
        })

        if self.config.token:
            self.session.headers["Authorization"] = f"Bearer {self.config.token}"

        self._workspace_client: Optional[Any] = None
        self._account_client: Optional[Any] = None

    @property
    def workspace_client(self) -> Optional[Any]:
        """Lazy-loaded official Databricks WorkspaceClient."""
        if self._workspace_client is None and HAS_DATABRICKS_SDK and not self.config.mock_mode:
            try:
                if self.config.host and self.config.token:
                    self._workspace_client = WorkspaceClient(
                        host=self.config.host,
                        token=self.config.token,
                    )
                elif self.config.host and self.config.client_id and self.config.client_secret:
                    self._workspace_client = WorkspaceClient(
                        host=self.config.host,
                        client_id=self.config.client_id,
                        client_secret=self.config.client_secret,
                    )
            except Exception as e:
                logger.warning(f"Could not initialize official WorkspaceClient: {e}")
        return self._workspace_client

    @property
    def account_client(self) -> Optional[Any]:
        """Lazy-loaded official Databricks AccountClient."""
        if self._account_client is None and HAS_DATABRICKS_SDK and not self.config.mock_mode:
            try:
                if self.config.account_id and self.config.token:
                    self._account_client = AccountClient(
                        account_id=self.config.account_id,
                        token=self.config.token,
                    )
                elif self.config.account_id and self.config.client_id and self.config.client_secret:
                    self._account_client = AccountClient(
                        account_id=self.config.account_id,
                        client_id=self.config.client_id,
                        client_secret=self.config.client_secret,
                    )
            except Exception as e:
                logger.warning(f"Could not initialize official AccountClient: {e}")
        return self._account_client

    def rest_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_account_api: bool = False,
        timeout: int = 15,
        max_retries: int = 3,
    ) -> Tuple[Optional[Dict[str, Any]], CategoryStatus, Optional[str]]:
        """
        Executes a direct REST API request to Databricks workspace or accounts endpoint.
        Maps HTTP response codes directly into CategoryStatus:
        - 200/201: COLLECTED or EMPTY (evaluated by caller based on record count)
        - 401/403: PERMISSION_DENIED
        - 404: UNAVAILABLE_IN_ACCOUNT
        - 501 / Unsupported feature message: UNSUPPORTED
        - 5xx / Connection errors: FAILED
        """
        if self.config.mock_mode:
            return None, CategoryStatus.COLLECTED, None

        base_url = self.config.host
        if is_account_api:
            # Databricks account API endpoint host
            if self.config.cloud_provider == "AZURE":
                base_url = "https://accounts.azuredatabricks.net"
            elif self.config.cloud_provider == "GCP":
                base_url = "https://accounts.gcp.databricks.com"
            else:
                base_url = "https://accounts.cloud.databricks.com"

        if not base_url:
            return None, CategoryStatus.FAILED, "No base URL configured for request"

        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data if method in ("POST", "PUT", "PATCH") else None,
                    timeout=timeout,
                )

                if response.status_code in (200, 201):
                    try:
                        return response.json(), CategoryStatus.COLLECTED, None
                    except ValueError:
                        # Non-JSON content (e.g. CSV stream)
                        return {"content_text": response.text}, CategoryStatus.COLLECTED, None

                elif response.status_code in (401, 403):
                    msg = f"HTTP {response.status_code} Permission Denied: {response.text[:200]}"
                    return None, CategoryStatus.PERMISSION_DENIED, msg

                elif response.status_code == 404:
                    msg = f"HTTP 404 Not Found: Feature or dataset not provisioned ({response.text[:200]})"
                    return None, CategoryStatus.UNAVAILABLE_IN_ACCOUNT, msg

                elif response.status_code == 429:
                    sleep_time = 2 ** attempt
                    logger.warning(f"Rate limited by Databricks (HTTP 429). Backing off for {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue

                elif response.status_code in (500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None, CategoryStatus.FAILED, f"HTTP {response.status_code} Server Error: {response.text[:200]}"

                else:
                    return None, CategoryStatus.FAILED, f"Unexpected HTTP {response.status_code}: {response.text[:200]}"

            except RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None, CategoryStatus.FAILED, f"Network connection error: {str(e)}"

        return None, CategoryStatus.FAILED, "Max retries exceeded"
    def execute_sql_statement(
    self,
    warehouse_id: str,
    statement: str,
    wait_timeout: str = "30s",
    timeout: int = 60,
    ) -> Tuple[Optional[Dict[str, Any]], CategoryStatus, Optional[str]]:
        """Execute a SQL statement and collect all result chunks.

        Uses Databricks Statement Execution API with EXTERNAL_LINKS so large
        result sets are not capped at an arbitrary row count or the 25 MiB
        inline-response limit.
        """
        payload = {
            "warehouse_id": warehouse_id,
            "statement": statement,
            "wait_timeout": wait_timeout,
            "format": "JSON_ARRAY",
            "disposition": "EXTERNAL_LINKS",
        }

        data, status, err = self.rest_request(
            "POST",
            "/api/2.0/sql/statements",
            data=payload,
            timeout=timeout,
        )

        if status != CategoryStatus.COLLECTED or data is None:
            return data, status, err

        manifest = data.get("manifest", {})
        result = data.get("result", {}) or {}
        all_rows: List[List[Any]] = []

        def append_result_chunk(chunk: Dict[str, Any]) -> None:
            inline_rows = chunk.get("data_array")

            if isinstance(inline_rows, list):
                all_rows.extend(inline_rows)

            for link_info in chunk.get("external_links", []) or []:
                link = (
                    link_info.get("external_link")
                    if isinstance(link_info, dict)
                    else None
                )

                if not link:
                    continue

                try:
                    # Signed external links already contain temporary credentials.
                    # Do not send the Databricks workspace bearer token.
                    response = requests.get(
                        link,
                        headers={
                            "User-Agent": "Databricks-Cost-Connector/1.0.0"
                        },
                        timeout=timeout,
                    )
                    response.raise_for_status()

                    payload = response.json()

                    if isinstance(payload, list):
                        all_rows.extend(payload)

                    elif (
                        isinstance(payload, dict)
                        and isinstance(payload.get("data_array"), list)
                    ):
                        all_rows.extend(payload["data_array"])

                except (RequestException, ValueError) as exc:
                    raise RuntimeError(
                        f"Failed to download SQL result chunk: {exc}"
                    ) from exc

        try:
            while result:
                append_result_chunk(result)

                next_link = result.get("next_chunk_internal_link")

                if not next_link:
                    break

                next_url = (
                    f"{self.config.host.rstrip('/')}/"
                    f"{next_link.lstrip('/')}"
                )

                response = self.session.get(
                    next_url,
                    timeout=timeout,
                )

                if response.status_code != 200:
                    return (
                        None,
                        CategoryStatus.FAILED,
                        (
                            f"Failed to fetch SQL result chunk: "
                            f"HTTP {response.status_code}: "
                            f"{response.text[:200]}"
                        ),
                    )

                result = response.json()

        except RuntimeError as exc:
            return None, CategoryStatus.FAILED, str(exc)

        except (RequestException, ValueError) as exc:
            return (
                None,
                CategoryStatus.FAILED,
                f"Failed to fetch SQL result chunks: {exc}",
            )

        combined = {
            "manifest": manifest,
            "result": {
                "data_array": all_rows,
            },
        }

        return combined, CategoryStatus.COLLECTED, None
    def paginate_rest_get(
        self,
        path: str,
        records_key: str,
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        max_pages: int = 50,
    ) -> Tuple[List[Dict[str, Any]], CategoryStatus, Optional[str]]:
        """
        Paginates through a Databricks GET endpoint until all records are retrieved.
        Handles both 'next_page_token' / 'page_token' and offset-based pagination.
        """
        all_records: List[Dict[str, Any]] = []
        current_params = dict(params or {})
        current_params["limit"] = page_size
        page_token = None

        for page in range(max_pages):
            if page_token:
                current_params["page_token"] = page_token

            data, status, err = self.rest_request("GET", path, params=current_params)
            if status != CategoryStatus.COLLECTED or data is None:
                return all_records, status, err

            page_items = data.get(records_key, [])
            if isinstance(page_items, list):
                all_records.extend(page_items)

            page_token = data.get("next_page_token")
            if not page_token:
                break

        if not all_records:
            return [], CategoryStatus.EMPTY, None

        return all_records, CategoryStatus.COLLECTED, None

