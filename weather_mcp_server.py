"""
Weather Prediction MCP Server.

Exposes weather forecast and recommendation tools over MCP (Model Context Protocol)
so a Databricks Agent Bricks agent can answer natural-language weather questions:
    - get_current_weather(location): Current conditions for a location
    - get_forecast(location, days): Multi-day forecast
    - predict_umbrella_needed(location, date): Smart recommendation based on precipitation
    - get_travel_recommendation(location, date): Travel planning advice based on conditions

These tools are backed by Open-Meteo's free weather API (see weather_broker.py),
which provides global coverage with no API key required.

Deploy this as a Databricks App (see app.yaml) so an Agent Bricks agent can
register its URL as an external MCP server.

Run locally for development:
    fastmcp dev weather_mcp_server.py

Run as production server:
    python weather_mcp_server.py
"""

import logging
import os
import time
import uuid
from datetime import datetime, timedelta

from fastmcp import FastMCP

import weather_broker

# Optional: import database tracker for MCP call logging to Lakebase.
# If psycopg2 is not installed or LAKEBASE_URL is not set, tracking is
# silently disabled and the server runs normally.
try:
    from database_tracker import log_tool_call
except Exception:
    def log_tool_call(*args, **kwargs):
        """No-op fallback when database tracking is unavailable."""
        return False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-mcp-server")

mcp = FastMCP("weather-prediction")

logger.info("🌤️  Starting Weather Prediction MCP server")


@mcp.tool
def get_current_weather(location: str) -> dict:
    """
    Get current weather conditions for a location.
    
    This tool accepts natural-language location names (e.g., "Chicago",
    "Paris, France", "Tokyo") and returns real-time weather data including
    temperature, humidity, wind speed, and conditions.
    
    Args:
        location: City name or address (e.g., "Chicago", "London, UK", "New York")
    
    Returns:
        A dict with tool_name, status, message, and result (current weather data).
        Result includes: location, temperature_f, humidity_percent, wind_speed_mph,
        conditions, timestamp.
    """
    start_time = time.time()
    session_id = str(uuid.uuid4())  # Generate session ID for this call
    
    try:
        # Step 1: Geocode location to lat/lon
        geo = weather_broker.geocode_location(location)
        
        # Step 2: Fetch current weather
        weather = weather_broker.fetch_current_weather(
            latitude=geo["latitude"],
            longitude=geo["longitude"],
            location_name=f"{geo['name']}, {geo['country']}",
        )
        
        result = {
            "tool_name": "get_current_weather",
            "status": "success",
            "message": f"Retrieved current weather for {weather['location']}: "
                      f"{weather['temperature_f']}°F, {weather['conditions']}",
            "result": weather,
        }
        
        # Log to database
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_current_weather",
            parameters={"location": location},
            status="success",
            result=weather,
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except ValueError as e:
        # Clean error from broker (location not found, API error, etc.)
        result = {
            "tool_name": "get_current_weather",
            "status": "error",
            "message": f"Failed to get current weather: {str(e)}",
        }
        
        # Log error to database
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_current_weather",
            parameters={"location": location},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Unexpected error in get_current_weather for '{location}'")
        result = {
            "tool_name": "get_current_weather",
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
        }
        
        # Log error to database
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_current_weather",
            parameters={"location": location},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result


@mcp.tool
def get_forecast(location: str, days: int = 7) -> dict:
    """
    Get multi-day weather forecast for a location.
    
    Returns daily forecasts including high/low temperatures, conditions, and
    precipitation probability. Useful for planning ahead.
    
    Args:
        location: City name or address (e.g., "Chicago", "Austin, TX")
        days: Number of forecast days (1-16, default 7)
    
    Returns:
        A dict with tool_name, status, message, and result (forecast data).
        Result includes: location, forecast_days, and daily_forecast array.
        Each daily entry has: date, conditions, temp_high_f, temp_low_f,
        precipitation_probability_percent.
    """
    start_time = time.time()
    session_id = str(uuid.uuid4())
    
    try:
        # Validate days parameter
        if days < 1 or days > 16:
            result = {
                "tool_name": "get_forecast",
                "status": "error",
                "message": "Days must be between 1 and 16",
            }
            
            # Log validation error
            execution_time_ms = int((time.time() - start_time) * 1000)
            log_tool_call(
                tool_name="get_forecast",
                parameters={"location": location, "days": days},
                status="error",
                error_message="Days must be between 1 and 16",
                execution_time_ms=execution_time_ms,
                session_id=session_id,
            )
            
            return result
        
        # Step 1: Geocode location to lat/lon
        geo = weather_broker.geocode_location(location)
        
        # Step 2: Fetch forecast
        forecast = weather_broker.fetch_forecast(
            latitude=geo["latitude"],
            longitude=geo["longitude"],
            location_name=f"{geo['name']}, {geo['country']}",
            days=days,
        )
        
        result = {
            "tool_name": "get_forecast",
            "status": "success",
            "message": f"Retrieved {forecast['forecast_days']}-day forecast for {forecast['location']}",
            "result": forecast,
        }
        
        # Log to database
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_forecast",
            parameters={"location": location, "days": days},
            status="success",
            result=forecast,
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except ValueError as e:
        result = {
            "tool_name": "get_forecast",
            "status": "error",
            "message": f"Failed to get forecast: {str(e)}",
        }
        
        # Log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_forecast",
            parameters={"location": location, "days": days},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Unexpected error in get_forecast for '{location}'")
        result = {
            "tool_name": "get_forecast",
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
        }
        
        # Log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_forecast",
            parameters={"location": location, "days": days},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result


@mcp.tool
def predict_umbrella_needed(location: str, date: str = "today") -> dict:
    """
    Predict whether you'll need an umbrella based on precipitation forecast.
    
    This tool applies a simple decision rule: if precipitation probability
    exceeds 40%, recommend bringing an umbrella. It explains its reasoning
    based on the actual forecast data.
    
    Args:
        location: City name or address
        date: Which day to check ("today", "tomorrow", or YYYY-MM-DD)
    
    Returns:
        A dict with tool_name, status, message, and result (recommendation).
        Result includes: date, location, precipitation_probability_percent,
        conditions, recommendation ("yes"/"no"/"maybe"), reasoning.
    """
    start_time = time.time()
    session_id = str(uuid.uuid4())
    
    try:
        # Step 1: Geocode location
        geo = weather_broker.geocode_location(location)
        
        # Step 2: Get forecast (7 days to cover various date inputs)
        forecast_data = weather_broker.fetch_forecast(
            latitude=geo["latitude"],
            longitude=geo["longitude"],
            location_name=f"{geo['name']}, {geo['country']}",
            days=7,
        )
        
        # Step 3: Parse date and find matching forecast day
        target_date = _parse_date_input(date)
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        # Find the matching day in forecast
        day_forecast = None
        for day in forecast_data["daily_forecast"]:
            if day["date"] == target_date_str:
                day_forecast = day
                break
        
        if not day_forecast:
            return {
                "tool_name": "predict_umbrella_needed",
                "status": "error",
                "message": f"Forecast not available for {target_date_str}. Try a date within the next 7 days.",
            }
        
        # Step 4: Apply decision logic
        precip_prob = day_forecast["precipitation_probability_percent"]
        conditions = day_forecast["conditions"]
        
        if precip_prob >= 60:
            recommendation = "yes"
            reasoning = f"High chance of precipitation ({precip_prob}%). Definitely bring an umbrella."
        elif precip_prob >= 40:
            recommendation = "maybe"
            reasoning = f"Moderate chance of precipitation ({precip_prob}%). Consider bringing an umbrella to be safe."
        else:
            recommendation = "no"
            reasoning = f"Low chance of precipitation ({precip_prob}%). You probably won't need an umbrella."
        
        result_data = {
            "date": target_date_str,
            "location": forecast_data["location"],
            "conditions": conditions,
            "precipitation_probability_percent": precip_prob,
            "recommendation": recommendation,
            "reasoning": reasoning,
        }
        
        result = {
            "tool_name": "predict_umbrella_needed",
            "status": "success",
            "message": f"Umbrella recommendation for {forecast_data['location']} on {target_date_str}: {recommendation.upper()}",
            "result": result_data,
        }
        
        # Log to database
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="predict_umbrella_needed",
            parameters={"location": location, "date": date},
            status="success",
            result=result_data,
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except ValueError as e:
        result = {
            "tool_name": "predict_umbrella_needed",
            "status": "error",
            "message": f"Failed to predict umbrella need: {str(e)}",
        }
        
        # Log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="predict_umbrella_needed",
            parameters={"location": location, "date": date},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Unexpected error in predict_umbrella_needed for '{location}' on '{date}'")
        result = {
            "tool_name": "predict_umbrella_needed",
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
        }
        
        # Log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="predict_umbrella_needed",
            parameters={"location": location, "date": date},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result


@mcp.tool
def get_travel_recommendation(location: str, date: str = "today") -> dict:
    """
    Get travel planning advice based on weather conditions.
    
    This tool provides actionable recommendations for outdoor activities,
    clothing, and travel considerations based on temperature, precipitation,
    and weather conditions. Goes beyond raw data to offer practical guidance.
    
    Args:
        location: City name or address
        date: Which day to plan for ("today", "tomorrow", or YYYY-MM-DD)
    
    Returns:
        A dict with tool_name, status, message, and result (travel advice).
        Result includes: date, location, weather summary, clothing_advice,
        activity_advice, travel_suitability (1-10 scale).
    """
    start_time = time.time()
    session_id = str(uuid.uuid4())
    
    try:
        # Step 1: Geocode location
        geo = weather_broker.geocode_location(location)
        
        # Step 2: Get forecast
        forecast_data = weather_broker.fetch_forecast(
            latitude=geo["latitude"],
            longitude=geo["longitude"],
            location_name=f"{geo['name']}, {geo['country']}",
            days=7,
        )
        
        # Step 3: Parse date and find matching forecast
        target_date = _parse_date_input(date)
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        day_forecast = None
        for day in forecast_data["daily_forecast"]:
            if day["date"] == target_date_str:
                day_forecast = day
                break
        
        if not day_forecast:
            return {
                "tool_name": "get_travel_recommendation",
                "status": "error",
                "message": f"Forecast not available for {target_date_str}. Try a date within the next 7 days.",
            }
        
        # Step 4: Generate recommendations based on conditions
        temp_high = day_forecast["temp_high_f"]
        temp_low = day_forecast["temp_low_f"]
        precip_prob = day_forecast["precipitation_probability_percent"]
        conditions = day_forecast["conditions"].lower()
        
        # Clothing advice based on temperature
        if temp_high >= 80:
            clothing_advice = "Light, breathable clothing. Bring sunscreen and a hat."
        elif temp_high >= 65:
            clothing_advice = "Comfortable layers. A light jacket might be useful for cooler moments."
        elif temp_high >= 50:
            clothing_advice = "Jacket or sweater recommended. Consider long pants."
        else:
            clothing_advice = "Warm layers essential. Coat, gloves, and warm clothing recommended."
        
        # Activity advice based on conditions and precipitation
        if "thunderstorm" in conditions or "heavy" in conditions:
            activity_advice = "Indoor activities recommended. Avoid outdoor plans or have backup options."
            suitability = 3
        elif precip_prob >= 60 or "rain" in conditions or "snow" in conditions:
            activity_advice = "Light rain/snow expected. Indoor activities preferred, but short outdoor trips OK with proper gear."
            suitability = 5
        elif precip_prob >= 40:
            activity_advice = "Mostly suitable for outdoor activities, but keep an eye on the weather."
            suitability = 7
        elif temp_high > 95 or temp_low < 20:
            activity_advice = "Extreme temperatures. Limit outdoor exposure and stay hydrated/warm."
            suitability = 6
        else:
            activity_advice = "Great conditions for outdoor activities and sightseeing!"
            suitability = 9
        
        weather_summary = (
            f"{conditions.capitalize()}, high {temp_high}°F / low {temp_low}°F, "
            f"{precip_prob}% chance of precipitation"
        )
        
        result_data = {
            "date": target_date_str,
            "location": forecast_data["location"],
            "weather_summary": weather_summary,
            "clothing_advice": clothing_advice,
            "activity_advice": activity_advice,
            "travel_suitability": suitability,
            "suitability_explanation": f"Travel suitability: {suitability}/10 (10 = perfect conditions)",
        }
        
        result = {
            "tool_name": "get_travel_recommendation",
            "status": "success",
            "message": f"Travel recommendations for {forecast_data['location']} on {target_date_str}",
            "result": result_data,
        }
        
        # Log to database
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_travel_recommendation",
            parameters={"location": location, "date": date},
            status="success",
            result=result_data,
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except ValueError as e:
        result = {
            "tool_name": "get_travel_recommendation",
            "status": "error",
            "message": f"Failed to get travel recommendation: {str(e)}",
        }
        
        # Log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_travel_recommendation",
            parameters={"location": location, "date": date},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Unexpected error in get_travel_recommendation for '{location}' on '{date}'")
        result = {
            "tool_name": "get_travel_recommendation",
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
        }
        
        # Log error
        execution_time_ms = int((time.time() - start_time) * 1000)
        log_tool_call(
            tool_name="get_travel_recommendation",
            parameters={"location": location, "date": date},
            status="error",
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            session_id=session_id,
        )
        
        return result


def _parse_date_input(date: str) -> datetime:
    """
    Parse flexible date input ("today", "tomorrow", or YYYY-MM-DD).
    
    Returns:
        datetime object for the target date
    """
    date_lower = date.lower().strip()
    
    if date_lower == "today":
        return datetime.now()
    elif date_lower == "tomorrow":
        return datetime.now() + timedelta(days=1)
    else:
        # Try to parse as YYYY-MM-DD
        try:
            return datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid date format: '{date}'. Use 'today', 'tomorrow', or YYYY-MM-DD."
            )

if __name__ == "__main__":
    # Databricks Apps route external HTTP traffic to this port via app.yaml;
    # streamable-http is the transport Databricks' MCP client/gateway expects
    # (same pattern as the alpaca_mcp_server.py reference).
    # For local development with Claude Desktop, use: mcp.run(transport="stdio")
    port = int(os.getenv("DATABRICKS_APP_PORT", os.getenv("PORT", 8000)))

    # Build the FastMCP streamable-HTTP ASGI app, then mount a health check
    # route at "/" so visiting the app URL in a browser shows a status page
    # instead of a bare 404. The MCP endpoint remains at /mcp.
    import json
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse

    async def health_check(request):
        return JSONResponse({
            "status": "ok",
            "service": "weather-mcp-server",
            "tools": ["get_current_weather", "get_forecast", "predict_umbrella_needed", "get_travel_recommendation"],
            "mcp_endpoint": "/mcp",
            "description": "Weather Prediction MCP Server backed by Open-Meteo API",
        })

    mcp_app = mcp.http_app(transport="streamable-http")

    # Insert the health check route before the MCP routes
    mcp_app.routes.insert(0, Route("/", health_check, methods=["GET"]))

    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=port)
