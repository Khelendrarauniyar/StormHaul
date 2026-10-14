# StormHaul

**Weather-aware truck routing.** StormHaul compares three route alternatives by
sampling the forecast at each checkpoint's *estimated arrival time* and scoring
load-aware wind, rain and snow risk, then recommends a route using a strict
risk-mileage priority order.

Built for the Spotter AI Full Stack Developer assessment: a Django REST API
(routing + weather orchestration, risk engine, ranking) and a React + TypeScript
+ MapLibre GL frontend (map, checkpoint inspector, corridor heatmap and a 0-48
hour forecast slider).

---

## 1. Features

- **Three route alternatives** from a routing provider (OpenRouteService when an
  API key is present; otherwise the public OSRM demo server; otherwise a clearly
  labelled synthetic demo dataset).
- **Distance-based checkpoints** at a selectable 10 / 25 / 50 mile spacing, with
  the destination always included even when the final segment is shorter.
- **Arrival-time weather.** Each checkpoint gets a weather sample for the hour
  bucket containing its interpolated ETA.
- **Load-aware risk classification** using the exact thresholds in the brief,
  including the load overrides for wind.
- **Risk mileage and average risk per route**, weighted by the distance each
  checkpoint represents.
- **Lexicographic recommendation**: fewest Severe miles -> fewest High miles ->
  lowest average risk -> shortest travel time, with a deterministic tie-break.
- **Interactive map**: three coloured route lines, selectable checkpoint markers
  with popups, origin/destination markers, and a per-route corridor heatmap.
- **0-48 hour forecast slider** with a wind / rain / snow variable selector and a
  legend tied to the active variable.
- **Clear UI states**: loading, empty, validation, provider failure, partial
  forecast coverage, and no-feasible-route handling.

---

## 2. Architecture

| Layer | Responsibility | Implementation |
| --- | --- | --- |
| React UI | Form, route cards, checkpoint table, map, legend, forecast slider, states | React 18 + TypeScript + Vite |
| Map rendering | Route polylines, checkpoint markers, corridor heatmap | MapLibre GL JS (keyless OpenFreeMap style) |
| Django API | Validation, orchestration, response schema, safe error shape | Django 5.2 + DRF |
| Routing adapter | Geocoding + three alternative route geometries/durations | OpenRouteService -> OSRM demo -> synthetic |
| Weather adapter | Hourly wind/rain/snow for a coordinate + estimated arrival time | Open-Meteo (no API key) |
| Domain services | Checkpoint generation, ETA interpolation, risk classification, ranking | Pure Python functions + unit tests |

### Data flow (one request, end to end)

1. Validate origin, destination, departure time, positive load weight and
   checkpoint spacing (`routing/serializers.py`).
2. Geocode origin/destination (Open-Meteo geocoding, or literal `lat,lon`).
3. Fetch three alternative routes and normalise them to a stable internal schema.
4. Compute cumulative distance along each geometry and place checkpoints at the
   chosen interval (`services/checkpoints.py`).
5. Interpolate each checkpoint ETA proportionally to cumulative distance.
6. Fetch hourly weather for every unique checkpoint/corridor coordinate in
   batched Open-Meteo requests (`services/weather_provider.py`).
7. Classify wind/rain/snow per checkpoint and apply load overrides
   (`services/risk.py`).
8. Aggregate risk mileage and distance-weighted average risk per route.
9. Rank routes and build recommendation reasons
   (`services/recommendation.py`).
10. Return geometry, checkpoints, summaries, corridor forecast, assumptions and
    warnings (`services/pipeline.py`).

---

## 3. Repository structure

```
StormHaul/
├── backend/
│   ├── config/                 # Django settings, urls, WSGI/ASGI
│   ├── routing/                # API view, serializers, urls, error handler
│   ├── services/
│   │   ├── models.py           # internal dataclasses + risk enum
│   │   ├── geo.py              # haversine, cumulative distance, interpolation
│   │   ├── checkpoints.py      # distance-based checkpoint sampling
│   │   ├── risk.py             # thresholds, load rules, risk mileage
│   │   ├── recommendation.py   # ranking + explanation
│   │   ├── routing_provider.py # geocoding + ORS/OSRM/synthetic routing
│   │   ├── weather_provider.py # Open-Meteo hourly client
│   │   └── pipeline.py         # orchestration and response assembly
│   ├── tests/                  # risk, checkpoint, geo, ranking, API tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                # typed API client
│   │   ├── components/         # form, place typeahead, cards, legend, slider, banners
│   │   ├── map/                # MapLibre setup, layers, heatmap
│   │   ├── hooks/              # request state
│   │   ├── lib/                # formatting, risk + variable metadata
│   │   └── types/              # shared API types
│   └── .env.example
├── README.md
└── .gitignore
```

---

## 4. Prerequisites

- Python 3.12+ (developed on 3.14)
- Node.js 18+ (developed on 22)
- No API keys are required for a working demo.

---

## 5. Local setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env    # optional; defaults work
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

The API is then available at `http://127.0.0.1:8000/api/`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. In development the Vite dev server proxies `/api`
to `http://127.0.0.1:8000`, so CORS is not needed locally.

### Environment variables

**backend/.env**

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | dev key | Django secret; set in production. |
| `DJANGO_DEBUG` | `true` | Debug mode. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Allowed hosts. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Browser origins allowed to call the API. |
| `ORS_API_KEY` | empty | Enables OpenRouteService HGV routing. |
| `PROVIDER_TIMEOUT_SECONDS` | `12` | Routing/geocoding request timeout (seconds). |
| `WEATHER_TIMEOUT_SECONDS` | `20` | Weather request timeout (seconds). |

**frontend/.env**

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | empty | Backend base URL (empty uses the dev proxy). |
| `VITE_MAP_STYLE_URL` | OpenFreeMap `liberty` | MapLibre style URL. |

Secrets live only on the server. Only `.env.example` files are committed.

---

## 6. API contract

`POST /api/route-plans/`

```json
{
  "origin": "Denver, CO",
  "destination": "Salt Lake City, UT",
  "departure_at": "2026-10-20T08:00:00-06:00",
  "load_weight_lb": 32000,
  "checkpoint_interval_miles": 25
}
```

`origin` and `destination` may include optional coordinates
(`origin_latitude`/`origin_longitude`, `destination_latitude`/`destination_longitude`)
when the user picks a suggestion; when present, geocoding is skipped and those
exact coordinates are used. Provide both or neither for each endpoint.

Response (selected fields):

- `request_id`, `generated_at`, `units`, `data_sources`, `origin`, `destination`
- `forecast_coverage`, `forecast_times[]`, `corridor[]` (hourly per sample point)
- `routes[]`: `id`, `label`, `geometry`, `distance_miles`, `duration_seconds`,
  `arrival_at`, `feasible`, `risk_summary`, `checkpoints[]`
- `routes[].checkpoints[]`: `sequence`, `coordinate`, `cumulative_miles`,
  `arrival_at`, `weather`, `hazards`, `combined_risk`, `no_travel_reason`
- `routes[].risk_summary`: `low/moderate/high/severe/no_travel/unknown_miles`,
  `average_risk`, `total_miles`
- `recommended_route_id`, `recommendation_reasons[]`, `assumptions[]`, `warnings[]`

Errors use a single shape:

```json
{ "error": { "code": "validation_error", "message": "...", "details": { } } }
```

`GET /api/health/` returns `{"status": "ok", "service": "stormhaul"}`.

`GET /api/locations/?q=<partial name>` returns up to six place suggestions for the
typeahead inputs:

```json
{ "results": [ { "label": "Springfield, Illinois, United States", "latitude": 39.8, "longitude": -89.64 } ] }
```

Queries shorter than two characters, or provider failures, return an empty
`results` list (never an error) so typing never breaks. Error codes include
`validation_error` (400), `location_not_found` (422) and `provider_error` (502).

---

## 7. Risk rules

Units: wind in **mph** (sustained), rain/snow in **in/hr**, load in **lb**. Rain
intensity is Open-Meteo `rain` **plus** `showers` (convective showers count), and
snow uses `snowfall` (cm converted to in/hr).

| Hazard | Low | Moderate | High | Severe | No Travel |
| --- | --- | --- | --- | --- | --- |
| Wind | < 25 mph | 25-34 | 35-44 | 45-54 | >= 55 mph |
| Rain | < 0.10 in/hr | 0.10-0.25 | 0.25-0.50 | 0.50-1.00 | > 1.00 |
| Snow | < 0.5 in/hr | 0.5-1.0 | 1.0-2.0 | 2.0-3.0 | > 3.0 |

Load overrides (applied on top of the wind band):

- Wind **>= 55 mph** -> No Travel for any load.
- Wind **45-54 mph** and load **> 30,000 lb** -> No Travel.
- Wind **35-44 mph** and load **> 40,000 lb** -> Severe.

### Boundary convention (documented assumption)

Displayed ranges in the brief touch at values such as 25, 35, 45 mph and
0.25 in/hr. StormHaul assigns every touching boundary to the **more hazardous**
category (`>=`), so 25 -> Moderate, 35 -> High, 45 -> Severe. The one exception is
the top band, which the brief states as strictly greater: rain **> 1.00 in/hr**
and snow **> 3.0 in/hr** are No Travel, while exactly 1.00 / 3.0 remain Severe.
These values are covered by boundary tests in `backend/tests/test_risk.py`.

### Combined checkpoint risk

The brief does not define how hazards combine. StormHaul uses the **most severe
single hazard** at the checkpoint, with No Travel as a separate hard-stop status
and a human-readable reason. Average risk uses the transparent mapping
Low=0, Moderate=1, High=2, Severe=3, No Travel=4, weighted by the distance each
checkpoint represents. This mapping is an implementation choice, not a supplied
rule.

### Risk mileage

The distance each checkpoint represents is estimated from neighbouring
checkpoints (midpoint boundaries), so totals equal the route distance regardless
of spacing or a shorter final segment. Checkpoints without forecast coverage are
excluded from the risk totals and reported separately as `unknown_miles`.

---

## 8. Recommendation algorithm

Ranking uses an ordered comparison, never a weighted sum:

```python
sort_key(route) = (
    not route.feasible,       # feasible routes always rank above prohibited ones
    route.risk_summary.severe_miles,
    route.risk_summary.high_miles,
    round(route.risk_summary.average_risk, 6),
    route.duration_seconds,
    route.id,                 # deterministic final tie-break
)
recommended_route = min(routes, key=sort_key)
```

A route is marked **infeasible** when any checkpoint is No Travel. If every route
is infeasible, StormHaul says so explicitly and presents the least-bad option
rather than claiming a safe route. Each recommendation is explained with concrete
evidence (Severe miles, High miles, average risk, duration, No Travel exposure).

---

## 9. Tests

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py test
```

Coverage includes:

- Wind boundaries: 24.9, 25, 34.9, 35, 44.9, 45, 54.9, 55 mph.
- Load boundaries: exactly 30,000 / 40,000 lb and just above each.
- Rain/snow boundaries immediately below, equal to and above each threshold.
- Risk precedence (low wind + severe snow is not Low).
- Checkpoint spacing: exact multiple, partial final segment, route shorter than
  the interval, zero-length route.
- ETA interpolation and monotonic arrivals.
- Ranking order and tie-breaks; no-feasible-route reporting.
- API success, validation error shape, and graceful weather-provider failure.

Frontend type-check and production build:

```powershell
cd frontend
npm run build
```

---

## 10. Providers, limits and attribution

- **Routing:** OpenRouteService `driving-hgv` (alternative routes) when
  `ORS_API_KEY` is set; otherwise the public OSRM demo server (car profile, not
  HGV-restricted). The OSRM demo server is rate-limited and intended for light
  use. If neither is reachable, synthetic demo routes are generated and labelled
  as such (`data_sources.routing = "synthetic-demo"`).

  **ORS public API limit:** the public OpenRouteService API caps *alternative
  routes* at roughly 100 km of route distance (error `2004`). For longer trips
  StormHaul requests a single HGV route from ORS and tops up with OSRM demo
  alternatives, reporting the mixed source as `openrouteservice+osrm-demo`. The
  ORS route is returned as Route A. Raise this limit only on a self-hosted ORS
  instance (`maximum_distance_alternative_routes`).
- **Geocoding:** Open-Meteo geocoding API (no key). Literal `lat,lon` input is
  also accepted.
- **Weather:** Open-Meteo hourly forecast (`wind_speed_10m`, `rain`, `snowfall`,
  `temperature_2m`), no key. Rain is converted mm->in/hr and snowfall cm->in/hr.
- **Map:** keyless OpenFreeMap vector tiles via MapLibre GL JS. Attribution is
  shown on the map.

The response always reports which providers were used in `data_sources`, and any
degradation is surfaced in `warnings`.

---

## 11. Known limitations

- Checkpoint ETAs are interpolated proportionally to distance; provider step
  durations are not yet used for per-vertex timing.
- The corridor heatmap shows points sampled along each route and their forecast
  values for the selected variable/time; it is not a high-resolution
  meteorological model. Unavailable hours are not fabricated.
- Checkpoint risk uses the most-severe-hazard rule; the numeric average-risk
  mapping is an implementation choice.
- The OSRM demo profile is a car profile, so HGV restrictions and truck-specific
  durations require an `ORS_API_KEY`.
- Route geometry is simplified on the server (Douglas-Peucker, ~0.0005 degrees,
  then rounded to 5 decimals) to keep responses small; checkpoint placement and
  ETA interpolation run on the simplified line. Responses for a three-route
  500-mile trip are ~0.13 MB instead of ~3 MB.
- The frontend splits MapLibre and React into separate cached chunks (see
  `vite.config.ts`) rather than shipping one large bundle.

---

## 12. Decision log

| Decision | Choice | Rationale |
| --- | --- | --- |
| Routing provider | ORS HGV -> OSRM demo -> synthetic | Real alternatives with a key; fully demonstrable without one. |
| Weather provider | Open-Meteo | No key, hourly wind/rain/snow, 48h+ coverage. |
| Map | MapLibre + OpenFreeMap | Keyless, no token, easy deployment. |
| ETA method | Distance-proportional interpolation | Provider-agnostic and documented as an approximation. |
| Risk combination | Most severe hazard | Simple, explainable, avoids invented weighting. |
| No Travel policy | Route marked infeasible; feasible routes preferred | Prudent safety default; documented as a product choice. |
| Forecast limitation | Unavailable hours returned as null and reported | Never fabricates weather data. |

---

