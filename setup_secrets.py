"""
One-time setup script: creates the Databricks secret scope and stores
secrets for the Weather MCP Server.

NOTE: Open-Meteo (default) requires NO secrets. Run this only if you need:
  - Lakebase URL (for optional MCP call tracking)
  - WeatherAPI.com key (if upgrading from Open-Meteo)

Usage:
    python setup_secrets.py
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass

w = WorkspaceClient()

# Lakebase URL (optional - for MCP call tracking)
w.secrets.put_secret(
    scope="database",
    key="lakebase-url",
    string_value=getpass.getpass("Paste your Lakebase URL: ")
)

w.secrets.put_acl(
    scope="database",
    principal="users",
    permission=workspace.AclPermission.READ,
)

# WeatherAPI.com key (optional - only if upgrading from Open-Meteo)
# Uncomment these lines if you want to use WeatherAPI.com:
# w.secrets.create_scope(scope="weather")
# w.secrets.put_secret(
#     scope="weather",
#     key="weatherapi-key",
#     string_value=getpass.getpass("Paste your WeatherAPI.com key: ")
# )
# w.secrets.put_acl(
#     scope="weather",
#     principal="users",
#     permission=workspace.AclPermission.READ,
# )
