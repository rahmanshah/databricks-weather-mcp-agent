"""
weather_mcp_server.py

FastMCP server exposing weather-prediction tools over streamable HTTP,
the transport Databricks' MCP client/gateway expects when you host your
own MCP server as a Databricks App. All HTTP calls/parsing live in
weather_broker.py — these @mcp.tool functions stay thin.
"""

import os

from fastmcp import FastMCP

import weather_broker as broker

mcp = FastMCP("weather-mcp-server")


def _resolve(location: str) -> dict:
    return broker.geocode_location(location)


@mcp.tool()
def get_current_weather(location: str) -> dict:
    """
    Get current weather conditions for a location.

    Args:
        location: City name, e.g. "Austin", "Chicago, US", "Helsinki, Finland".

    Returns temperature, feels-like temperature, humidity, precipitation,
    a plain-text condition, and wind for right now.
    """
    place = _resolve(location)
    current = broker.get_current_conditions(place["latitude"], place["longitude"], place["timezone"])
    return {"location": place, "current": current}


@mcp.tool()
def get_forecast(location: str, days: int = 5) -> dict:
    """
    Get a multi-day weather forecast for a location.

    Args:
        location: City name, e.g. "Austin", "Chicago, US".
        days: Number of days to forecast, 1-16 (default 5).

    Returns a list of daily entries with high/low temp, precipitation
    probability, and condition text for each day.
    """
    place = _resolve(location)
    forecast = broker.get_daily_forecast(place["latitude"], place["longitude"], days, place["timezone"])
    return {"location": place, "forecast": forecast}


@mcp.tool()
def get_travel_recommendation(location: str, date: str) -> dict:
    """
    Get a reasoned travel recommendation (umbrella / jacket) for a location
    on a specific date, derived from the forecast rather than a raw
    passthrough of the API response.

    Args:
        location: City name, e.g. "Austin", "Chicago, US".
        date: Target date in YYYY-MM-DD format. Must be today or within the
              next 16 days (Open-Meteo's free forecast horizon).

    Reasoning applied:
        - Umbrella recommended if precipitation probability > 40%.
        - Jacket recommended if the day's low temperature is under 10C.
    """
    place = _resolve(location)
    day = broker.get_forecast_for_date(place["latitude"], place["longitude"], date, place["timezone"])

    precip_prob = day["precipitation_probability_pct"] or 0
    temp_min = day["temp_min_c"]

    bring_umbrella = precip_prob > 40
    bring_jacket = temp_min is not None and temp_min < 10

    reasoning = [
        f"Precipitation chance is {precip_prob}% "
        f"({'>' if bring_umbrella else '<='} 40% threshold) -> "
        f"{'bring an umbrella' if bring_umbrella else 'umbrella not needed'}.",
        f"Forecast low is {temp_min}C "
        f"({'<' if bring_jacket else '>='} 10C threshold) -> "
        f"{'pack a jacket' if bring_jacket else 'jacket not needed'}.",
    ]

    return {
        "location": place,
        "date": date,
        "forecast_summary": f"{day['condition']}, {day['temp_min_c']} to {day['temp_max_c']}C",
        "bring_umbrella": bring_umbrella,
        "bring_jacket": bring_jacket,
        "reasoning": reasoning,
        "raw_forecast": day,
    }


if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
