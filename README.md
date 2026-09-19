# Weather Prediction MCP Server

A Model Context Protocol (MCP) server that exposes weather-forecast and prediction tools, built with [FastMCP](https://gofastmcp.com/) and backed by the free [Open-Meteo API](https://open-meteo.com) (no API key required). Deploy as a Databricks App and wire an Agent Bricks agent to answer natural-language weather questions.

Based on the Day 3 pattern (`mcp_server/alpaca_mcp_server.py` + `alpaca_broker.py`).

## Architecture

```
Agent Bricks agent  --(MCP tool calls)-->  weather_mcp_server.py  --(calls)-->  weather_broker.py  --(HTTPS)-->  Open-Meteo API
                                                                                            (geocoding + forecast)
                                                                                              
                     (optional) database_tracker.py --(psycopg2)-->  Lakebase Postgres  (call logging)
```

- **`weather_mcp_server.py`** - FastMCP server with `@mcp.tool` decorators, streamable-HTTP transport (same pattern as `alcp_mcp_server.py`).
- **`weather_broker.py`** - Adapter module with all HTTP calls to Open-Meteo. No raw `requests`/`httpx` calls inside `@mcp.tool` functions.
- **`database_tracker.py`** - Optional Lakebase Postgres call logging. Silently disabled if `psycopg2` or `LAKEBASE_URL` is unavailable.
- **`mcp_server/`** and **`dashboard/`** - Original Day 3 Alpaca reference code (not part of the weather project).

## Tools Exposed

| Tool | Args | Description |
| --- | --- | --- |
| `get_current_weather` | `location: str` | Current temperature, humidity, wind, conditions for any city |
| `get_forecast` | `location: str, days: int = 7` | Multi-day forecast with high/low temps, conditions, precipitation chance |
| `predict_umbrella_needed` | `location: str, date: str = "today"` | Smart prediction: \>=60% precip → yes, 40-60% → maybe, <40% → no, with reasoning |
| `get_travel_recommendation` | `location: str, date: str = "today"` | Clothing/activity advice + travel suitability score (1-10) based on temp & precip |

## Weather Data Source

**API**: Open-Meteo (https://open-meteo.com)
- No signup, no API key, completely free for non-commercial use
- ~10,000 calls/day rate limit
- Global coverage with built-in geocoding
- Endpoints used:
  - Geocoding: `https://geocoding-api.open-meteo.com/v1/search`
  - Forecast: `https://api.open-meteo.com/v1/forecast`

## Files

| File | Purpose |
| --- | --- |
| `weather_mcp_server.py` | FastMCP server with 4 `@mcp.tool` functions |
| `weather_broker.py` | Open-Meteo API adapter (all HTTP calls + parsing) |
| `database_tracker.py` | Optional Lakebase Postgres call logging |
| `schema.sql` | Lakebase table schema for call tracking |
| `app.yaml` | Databricks App config (entry point: `weather_mcp_server.py`) |
| `requirements.txt` | Python dependencies |
| `setup_secrets.py` | One-time script to store Lakebase URL secret |
| `.env.example` | Local dev env var template |
| `mcp_server/` | Original Day 3 Alpaca reference (not part of weather project) |
| `dashboard/` | Original Day 3 dashboard reference (not part of weather project) |

## Setup & Deployment

### 1. Install Dependencies (local dev)

```bash
pip install -r requirements.txt
```

### 2. Run Locally

```bash
python weather_mcp_server.py
```

The server starts on `http://0.0.0.0:8000` with streamable HTTP transport.

### 3. Deploy as a Databricks App

1. Create a Git folder for this repo in Databricks.
2. Go to **Compute > Apps > Create app > Custom**.
3. Name it e.g. `weather-mcp-server`.
4. Point source at the Git folder root (so it picks up `app.yaml`).
5. Deploy and copy the app URL.

### 4. Register as External MCP

1. In your workspace, go to **AI Gateway > MCPs > Add MCP**.
2. Paste the app URL as the server endpoint (streamable HTTP).
3. Name it e.g. `weather-prediction` and save. Databricks will introspect the 4 tools.

### 5. Build the Agent Bricks Agent

1. Go to **Agent Bricks** and create a new agent.
2. Add the registered MCP server as an external tool.
3. Use this system prompt:

```
You are a weather assistant. You have access to weather tools via MCP.

Available tools:
- get_current_weather(location): Get real-time weather for a city
- get_forecast(location, days): Get a multi-day forecast
- predict_umbrella_needed(location, date): Get an umbrella recommendation
- get_travel_recommendation(location, date): Get travel/clothing advice

Rules:
1. ALWAYS call a tool to get real weather data before answering. Never guess or hallucinate weather.
2. For "today" or "now" questions, use get_current_weather.
3. For "tomorrow" or specific dates, use get_forecast or predict_umbrella_needed.
4. For "should I bring/pack" questions, use get_travel_recommendation or predict_umbrella_needed.
5. If a tool returns an error (e.g. location not found), tell the user and suggest they be more specific. Do not make up data.
6. Summarize the tool results in natural language for the user.
```

### 6. Optional: Enable Call Tracking (Lakebase)

To log all MCP tool calls to Lakebase Postgres:
1. Run `schema.sql` against your Lakebase database to create the `mcp_weather_tracking` table.
2. Run `python setup_secrets.py` to store the Lakebase URL as a Databricks secret.
3. Uncomment the `env` block in `app.yaml` to inject `LAKEBASE_URL`.
4. Redeploy the app.

## Example Agent Queries

1. **"Will it rain in Chicago tomorrow?"** → Agent calls `predict_umbrella_needed("Chicago", "tomorrow")`
2. **"What's the weather in Tokyo right now?"** → Agent calls `get_current_weather("Tokyo")`
3. **"Should I bring a jacket to Denver this weekend?"** → Agent calls `get_travel_recommendation("Denver", "2026-09-20")`

## Error Handling

- **Location not found**: Returns a clean error message suggesting a more specific name.
- **API outage**: Returns a clean error, agent can react sensibly (ask user to clarify).
- **Database unavailable**: Call tracking silently disabled, tools continue working.
- **Invalid date format**: Returns guidance to use "today", "tomorrow", or YYYY-MM-DD.

## References

- [Open-Meteo API Documentation](https://open-meteo.com/en/docs)
- [Databricks MCP Tools](https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp)
- [FastMCP](https://gofastmcp.com/)

