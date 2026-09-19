-- Weather MCP Server - Call Tracking Schema
-- Create this table in your Lakebase Postgres database before deploying the MCP server
--
-- This table logs every tool call made through the Weather MCP server,
-- tracking parameters, results, errors, and session context.
--
-- Usage:
--   1. Connect to your Lakebase database: psql <lakebase-url>
--   2. Run this script: \i schema.sql
--   3. Verify: SELECT COUNT(*) FROM mcp_weather_tracking;

CREATE TABLE IF NOT EXISTS mcp_weather_tracking (
    id SERIAL PRIMARY KEY,
    
    -- Session tracking
    session_id VARCHAR(255),                    -- Session identifier from Agent Bricks
    timestamp TIMESTAMP DEFAULT NOW(),          -- When the tool was called (UTC)
    
    -- Tool information
    tool_name VARCHAR(255) NOT NULL,            -- e.g., "get_current_weather", "get_forecast"
    parameters JSONB NOT NULL,                  -- Tool input parameters (location, days, date, etc.)
    
    -- Result tracking
    status VARCHAR(20) NOT NULL,                -- "success" or "error"
    result JSONB,                               -- Full result dict (weather data, recommendations)
    error_message TEXT,                         -- Error details if status = "error"
    
    -- Performance
    execution_time_ms INTEGER,                  -- Time taken to execute the tool (milliseconds)
    
    -- Metadata
    api_calls_made INTEGER DEFAULT 1,           -- Number of external API calls (geocoding + weather)
    created_at TIMESTAMP DEFAULT NOW()          -- Row creation time
);

-- Index for fast session lookups
CREATE INDEX IF NOT EXISTS idx_mcp_tracking_session ON mcp_weather_tracking(session_id);

-- Index for fast tool name lookups
CREATE INDEX IF NOT EXISTS idx_mcp_tracking_tool ON mcp_weather_tracking(tool_name);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_mcp_tracking_timestamp ON mcp_weather_tracking(timestamp DESC);

-- Index for status filtering (find all errors)
CREATE INDEX IF NOT EXISTS idx_mcp_tracking_status ON mcp_weather_tracking(status);

-- Helpful view: Recent calls summary
CREATE OR REPLACE VIEW mcp_tracking_summary AS
SELECT 
    tool_name,
    status,
    COUNT(*) as call_count,
    AVG(execution_time_ms) as avg_execution_ms,
    MAX(timestamp) as last_called_at
FROM mcp_weather_tracking
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY tool_name, status
ORDER BY call_count DESC;

-- Example queries:
--
-- View recent tool calls:
--   SELECT session_id, tool_name, status, timestamp 
--   FROM mcp_weather_tracking 
--   ORDER BY timestamp DESC LIMIT 20;
--
-- Find all errors in the last hour:
--   SELECT tool_name, error_message, parameters, timestamp
--   FROM mcp_weather_tracking
--   WHERE status = 'error' AND timestamp >= NOW() - INTERVAL '1 hour';
--
-- Get call summary:
--   SELECT * FROM mcp_tracking_summary;
--
-- Find slowest calls:
--   SELECT tool_name, execution_time_ms, parameters, timestamp
--   FROM mcp_weather_tracking
--   ORDER BY execution_time_ms DESC LIMIT 10;
