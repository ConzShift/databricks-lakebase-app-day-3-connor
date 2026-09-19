"""
Database tracking module for Weather MCP Server.

Logs all MCP tool calls to a Lakebase Postgres table (mcp_weather_tracking)
for auditing, debugging, and analytics.

The tracker captures:
  - Tool name and parameters
  - Execution status (success/error)
  - Full result or error message
  - Session ID for tracing agent conversations
  - Execution time for performance monitoring

Usage in weather_mcp_server.py:
    from database_tracker import log_tool_call
    
    @mcp.tool
    def get_current_weather(location: str) -> dict:
        result = ...
        log_tool_call(
            tool_name="get_current_weather",
            parameters={"location": location},
            status=result["status"],
            result=result.get("result"),
            error_message=result.get("message") if result["status"] == "error" else None,
            execution_time_ms=...
        )
        return result
"""

import json
import logging
import os
from typing import Any, Optional

import psycopg2
from psycopg2.extras import Json

logger = logging.getLogger("database-tracker")

# Global connection pool (initialized lazily)
_db_connection = None


def _get_db_connection():
    """
    Get or create a persistent database connection.
    
    Reads the Lakebase URL from environment variables set in app.yaml:
      - LAKEBASE_URL: Full connection string from secrets
    
    Returns:
        psycopg2.connection or None if tracking is disabled
    """
    global _db_connection
    
    if _db_connection is not None:
        return _db_connection
    
    # Check if tracking is enabled
    lakebase_url = os.getenv("LAKEBASE_URL")
    
    if not lakebase_url:
        logger.warning("LAKEBASE_URL not set - MCP call tracking disabled")
        return None
    
    try:
        _db_connection = psycopg2.connect(lakebase_url)
        logger.info("✅ Connected to Lakebase for MCP call tracking")
        return _db_connection
    except Exception as e:
        logger.error(f"Failed to connect to Lakebase: {e}")
        logger.warning("MCP call tracking disabled due to connection failure")
        return None


def log_tool_call(
    tool_name: str,
    parameters: dict,
    status: str,
    result: Optional[dict] = None,
    error_message: Optional[str] = None,
    execution_time_ms: Optional[int] = None,
    session_id: Optional[str] = None,
) -> bool:
    """
    Log a tool call to the mcp_weather_tracking table.
    
    Args:
        tool_name: Name of the MCP tool (e.g., "get_current_weather")
        parameters: Input parameters passed to the tool
        status: "success" or "error"
        result: Full result dict (if successful)
        error_message: Error details (if status = "error")
        execution_time_ms: Time taken to execute (milliseconds)
        session_id: Session identifier from Agent Bricks
    
    Returns:
        True if logged successfully, False if tracking is disabled or failed
    """
    conn = _get_db_connection()
    
    if conn is None:
        # Tracking disabled - fail silently
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mcp_weather_tracking (
                    session_id,
                    tool_name,
                    parameters,
                    status,
                    result,
                    error_message,
                    execution_time_ms
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    session_id,
                    tool_name,
                    Json(parameters),  # Convert dict to JSONB
                    status,
                    Json(result) if result else None,
                    error_message,
                    execution_time_ms,
                )
            )
        conn.commit()
        logger.debug(f"Logged tool call: {tool_name} ({status})")
        return True
    except Exception as e:
        logger.error(f"Failed to log tool call to database: {e}")
        # Don't let tracking failures break the tool - fail gracefully
        return False


def close_connection():
    """
    Close the database connection (call on shutdown).
    """
    global _db_connection
    if _db_connection:
        try:
            _db_connection.close()
            logger.info("Closed Lakebase connection")
        except Exception as e:
            logger.error(f"Error closing Lakebase connection: {e}")
        finally:
            _db_connection = None
