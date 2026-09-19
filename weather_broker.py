"""
Weather API adapter for Open-Meteo.

This module handles all HTTP calls to the Open-Meteo API and returns
clean dicts. The MCP server (weather_mcp_server.py) calls these functions
and never makes raw HTTP requests directly.

Open-Meteo API:
- No API key required (free tier, non-commercial use)
- Documentation: https://open-meteo.com/en/docs
- Rate limit: ~10,000 calls/day
- Global coverage (geocoding + weather data)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger("weather-broker")

# Open-Meteo API endpoints
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# HTTP client with reasonable timeout
_http_client = httpx.Client(timeout=10.0)


def geocode_location(location: str) -> dict:
    """
    Convert a natural-language location (city name, address) to lat/lon
    coordinates using Open-Meteo's geocoding API.
    
    Args:
        location: Location string (e.g., "Chicago", "Paris, France", "Tokyo")
    
    Returns:
        Dict with latitude, longitude, name, country, timezone.
        Raises ValueError if location cannot be found.
    """
    try:
        response = _http_client.get(
            GEOCODING_URL,
            params={
                "name": location,
                "count": 1,  # Return only the best match
                "language": "en",
                "format": "json",
            },
        )
        response.raise_for_status()
        data = response.json()
        
        if "results" not in data or not data["results"]:
            raise ValueError(f"Location '{location}' not found. Please try a more specific name.")
        
        result = data["results"][0]
        return {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "name": result["name"],
            "country": result.get("country", "Unknown"),
            "timezone": result.get("timezone", "UTC"),
        }
    except httpx.HTTPError as e:
        logger.error(f"HTTP error geocoding location '{location}': {e}")
        raise ValueError(f"Failed to geocode location: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error geocoding location '{location}': {e}")
        raise ValueError(f"Geocoding error: {str(e)}")


def fetch_current_weather(latitude: float, longitude: float, location_name: str) -> dict:
    """
    Get current weather conditions from Open-Meteo.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        location_name: Human-readable location name (for response)
    
    Returns:
        Dict with temperature, conditions, humidity, wind_speed, timestamp.
    """
    try:
        response = _http_client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
        )
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current", {})
        weather_code = current.get("weather_code", 0)
        
        return {
            "location": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "temperature_f": current.get("temperature_2m"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_mph": current.get("wind_speed_10m"),
            "conditions": _weather_code_to_description(weather_code),
            "timestamp": current.get("time"),
        }
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching current weather: {e}")
        raise ValueError(f"Failed to fetch current weather: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching current weather: {e}")
        raise ValueError(f"Current weather error: {str(e)}")


def fetch_forecast(
    latitude: float,
    longitude: float,
    location_name: str,
    days: int = 7
) -> dict:
    """
    Get multi-day weather forecast from Open-Meteo.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        location_name: Human-readable location name (for response)
        days: Number of forecast days (1-16, default 7)
    
    Returns:
        Dict with location info and daily forecast array.
    """
    try:
        # Clamp days to valid range
        days = max(1, min(16, days))
        
        response = _http_client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
                "forecast_days": days,
            },
        )
        response.raise_for_status()
        data = response.json()
        
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        weather_codes = daily.get("weather_code", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        precip_prob = daily.get("precipitation_probability_max", [])
        
        # Build daily forecast array
        forecast = []
        for i in range(len(dates)):
            forecast.append({
                "date": dates[i],
                "conditions": _weather_code_to_description(weather_codes[i]),
                "temp_high_f": temp_max[i],
                "temp_low_f": temp_min[i],
                "precipitation_probability_percent": precip_prob[i] if i < len(precip_prob) else 0,
            })
        
        return {
            "location": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": len(forecast),
            "daily_forecast": forecast,
        }
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching forecast: {e}")
        raise ValueError(f"Failed to fetch forecast: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error fetching forecast: {e}")
        raise ValueError(f"Forecast error: {str(e)}")


def _weather_code_to_description(code: int) -> str:
    """
    Convert WMO weather code to human-readable description.
    Based on: https://open-meteo.com/en/docs
    """
    code_map = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return code_map.get(code, f"Unknown (code {code})")
