"""
weather_broker.py

Adapter module for the Open-Meteo API (free, no API key required).
All HTTP calls and response parsing live here — weather_mcp_server.py
only calls these functions and returns clean dicts. This mirrors the
alpaca_broker.py pattern from the Day 3 reference repo.
"""

from datetime import datetime, date as date_cls
from typing import Optional

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 10  # seconds
MAX_FORECAST_DAYS = 16  # Open-Meteo's free forecast horizon

# WMO weather interpretation codes -> human-readable text
# https://open-meteo.com/en/docs (see "WMO Weather interpretation codes")
WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}


class WeatherBrokerError(Exception):
    """Raised when a location can't be resolved or the API can't be reached."""


def describe_code(code: Optional[int]) -> str:
    if code is None:
        return "unknown"
    return WMO_CODES.get(code, f"unrecognized condition (code {code})")


def geocode_location(location: str) -> dict:
    """Resolve a free-text location (city name, 'City, Country') to lat/lon."""
    try:
        resp = requests.get(
            GEOCODING_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise WeatherBrokerError(f"Geocoding request failed: {e}") from e

    results = resp.json().get("results")
    if not results:
        raise WeatherBrokerError(f"Could not resolve location: '{location}'")

    top = results[0]
    return {
        "name": top.get("name"),
        "country": top.get("country"),
        "admin1": top.get("admin1"),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "timezone": top.get("timezone", "auto"),
    }


def get_current_conditions(latitude: float, longitude: float, timezone: str = "auto") -> dict:
    """Fetch current weather conditions for a lat/lon pair."""
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                           "precipitation,weather_code,wind_speed_10m,wind_direction_10m",
                "timezone": timezone,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise WeatherBrokerError(f"Forecast request failed: {e}") from e

    current = resp.json().get("current")
    if not current:
        raise WeatherBrokerError("No current-conditions data returned by Open-Meteo")

    return {
        "time": current.get("time"),
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "condition": describe_code(current.get("weather_code")),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
    }


def get_daily_forecast(latitude: float, longitude: float, days: int = 5, timezone: str = "auto") -> list:
    """Fetch a multi-day daily forecast for a lat/lon pair."""
    days = max(1, min(days, MAX_FORECAST_DAYS))
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                         "precipitation_sum,weather_code,wind_speed_10m_max",
                "forecast_days": days,
                "timezone": timezone,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise WeatherBrokerError(f"Forecast request failed: {e}") from e

    daily = resp.json().get("daily")
    if not daily:
        raise WeatherBrokerError("No daily forecast data returned by Open-Meteo")

    out = []
    for i, day in enumerate(daily.get("time", [])):
        out.append({
            "date": day,
            "temp_max_c": daily["temperature_2m_max"][i],
            "temp_min_c": daily["temperature_2m_min"][i],
            "precipitation_probability_pct": daily["precipitation_probability_max"][i],
            "precipitation_sum_mm": daily["precipitation_sum"][i],
            "condition": describe_code(daily["weather_code"][i]),
            "wind_speed_max_kmh": daily["wind_speed_10m_max"][i],
        })
    return out


def get_forecast_for_date(latitude: float, longitude: float, target_date: str, timezone: str = "auto") -> dict:
    """Fetch the forecast entry for one specific date (YYYY-MM-DD)."""
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError as e:
        raise WeatherBrokerError(f"Date must be in YYYY-MM-DD format, got '{target_date}'") from e

    delta_days = (target - date_cls.today()).days
    if delta_days < 0:
        raise WeatherBrokerError(f"'{target_date}' is in the past; only current/future dates are supported")
    if delta_days > MAX_FORECAST_DAYS - 1:
        raise WeatherBrokerError(
            f"'{target_date}' is more than {MAX_FORECAST_DAYS} days out; "
            "Open-Meteo's free forecast doesn't reach that far"
        )

    forecast = get_daily_forecast(latitude, longitude, days=delta_days + 1, timezone=timezone)
    for day in forecast:
        if day["date"] == target_date:
            return day

    raise WeatherBrokerError(f"No forecast entry found for '{target_date}'")
