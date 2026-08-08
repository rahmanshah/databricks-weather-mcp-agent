# Weather-Prediction MCP Server + Agent

Homework submission — Day 3 pattern (Agent Bricks + external MCP server),
applied to a free weather API instead of Alpaca Markets.

## Architecture

```
Agent Bricks agent  --(MCP tool calls)-->  mcp_server/weather_mcp_server.py  --(REST)-->  Open-Meteo (free, no key)
```

- `mcp_server/` is a single Databricks App exposing 3 weather tools over
  streamable HTTP — the transport Databricks' MCP gateway expects.
- `mcp_server/weather_broker.py` is the adapter module: every HTTP call to
  Open-Meteo and all response parsing happens here. `weather_mcp_server.py`
  only resolves a location, calls the broker, and returns a clean dict —
  no raw `requests` calls inside the `@mcp.tool` functions.
- No dashboard, no Lakebase, no secrets — nothing here needs persistent
  state, so there's nothing to configure beyond the code itself.

## Weather API + auth

**[Open-Meteo](https://open-meteo.com/)** — free, no signup, no API key,
up to 10,000 non-commercial calls/day. Two endpoints are used:

- Geocoding (`geocoding-api.open-meteo.com/v1/search`) — resolves a city
  name to lat/lon.
- Forecast (`api.open-meteo.com/v1/forecast`) — current conditions and
  daily forecast, up to 16 days out.

No secrets to store — this is why the assignment recommends starting here
instead of a key-based API.

## Tools

| Tool | Description |
|---|---|
| `get_current_weather(location)` | Current temperature, feels-like, humidity, precipitation, condition, wind. |
| `get_forecast(location, days)` | Daily high/low, precipitation probability, and condition for the next N days (max 16). |
| `get_travel_recommendation(location, date)` | Derived judgment for a specific date: recommends an umbrella if precipitation probability > 40%, and a jacket if the day's low is under 10°C. Returns the reasoning, not just raw numbers. |

## Run locally

```bash
cd mcp_server
pip install -r requirements.txt
python weather_mcp_server.py   # serves MCP on :8000
```

Sanity-check with `curl` or an [MCP Inspector](https://docs.databricks.com/aws/en/agents/mcp-tools/connect-clients)
against `http://localhost:8000/mcp` before deploying.

## Deploy to Databricks Apps (Free Edition)

1. Create a Git folder in your workspace pointing at this repo (Workspace
   > Git folder > add repo, no CLI needed).
2. Compute > Apps > **Create app** > Custom. Name it something starting
   with `mcp-` (e.g. `mcp-weather-server`) — Databricks uses that prefix
   to recognize it as an MCP server in the AI Playground.
3. Point the app's source at this Git folder's `mcp_server/` subfolder so
   it picks up `mcp_server/app.yaml`.
4. Deploy, then copy the app's URL — the MCP endpoint will be at
   `https://<app-url>/mcp`.

## Register as an external MCP

1. In your workspace: **AI Gateway** > **MCPs** > **Add MCP** / **Register
   external MCP**.
2. Paste the app URL from the previous step as the streamable-HTTP
   endpoint.
3. Name it (e.g. `weather-mcp`) and save — Databricks will introspect the
   server and list the 3 tools above.

## Build the Agent Bricks agent

1. **Agents** > **Agent Bricks** > **Create agent** > Custom LLM.
2. Under **Tools**, add the `weather-mcp` MCP server (all 3 tools).
3. System prompt:

   > You are a weather-prediction assistant. Use `get_current_weather` for
   > "right now" questions, `get_forecast` for multi-day questions, and
   > `get_travel_recommendation` for anything about what to bring or wear
   > on a specific date. Only answer for locations you can resolve — if a
   > tool call fails because a location can't be found or the API is
   > unreachable, say so plainly rather than guessing. Always state the
   > reasoning behind a recommendation (the precipitation chance or
   > temperature that triggered it), not just the yes/no answer.

4. Deploy and test with natural-language questions, e.g.:
   - "Will it rain in Chicago tomorrow?"
   - "Should I bring a jacket to Austin this weekend?"
   - "What's the 5-day forecast for Helsinki?"

Capture screenshots of at least 3 different questions and the agent's
tool calls + final answers for the submission.

## Not in this version (possible next steps)

- **Dashboard app** (optional, for extra credit) — a small read-only page
  showing recent agent queries. Deferred for now to keep the submission
  simple; would need a shared store (e.g. Lakebase) between the MCP server
  and the dashboard, since they'd be separate processes.
- Stretch tools: severe weather alerts (NWS API), historical lookups,
  multi-city comparison.
