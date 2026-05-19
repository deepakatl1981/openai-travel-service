import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

TRANSPORTAPI_PLACES_URL = "https://transportapi.com/v3/uk/places.json"
POSTCODES_URL = "https://api.postcodes.io/postcodes"


class Location(BaseModel):
    lat: float
    lon: float
    label: str


class BusStop(BaseModel):
    type: str | None = None
    name: str | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    accuracy: int | None = None
    atcocode: str | None = None
    distance: float | None = None


class BusStopResponse(BaseModel):
    source: str
    count: int
    stops: list[BusStop]


def build_app() -> FastAPI:
    app = FastAPI(
        title="OpenAI Travel Service",
        description="Backend API for travel data integrations.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    return app


def get_allowed_origins() -> list[str]:
    raw_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def get_transportapi_credentials() -> tuple[str, str]:
    app_id = os.getenv("TRANSPORTAPI_APP_ID", "").strip()
    app_key = os.getenv("TRANSPORTAPI_APP_KEY", "").strip()

    if not app_id or not app_key:
        raise HTTPException(
            status_code=500,
            detail="TransportAPI credentials are not configured on the backend.",
        )

    return app_id, app_key


def parse_coordinate_query(query: str) -> Location | None:
    parts = [part.strip() for part in query.split(",")]

    if len(parts) != 2:
        return None

    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        return None

    return Location(lat=lat, lon=lon, label=f"{lat}, {lon}")


async def geocode_postcode(client: httpx.AsyncClient, postcode: str) -> Location:
    response = await client.get(f"{POSTCODES_URL}/{postcode}")
    payload = response.json()

    if response.status_code != 200 or not payload.get("result"):
        raise HTTPException(status_code=404, detail="Postcode was not found.")

    result = payload["result"]
    return Location(
        lat=result["latitude"],
        lon=result["longitude"],
        label=result["postcode"],
    )


async def resolve_location(
    client: httpx.AsyncClient,
    query: str | None,
    lat: float | None,
    lon: float | None,
) -> Location:
    if lat is not None and lon is not None:
        return Location(lat=lat, lon=lon, label=f"{lat}, {lon}")

    if query:
        coordinate_query = parse_coordinate_query(query)

        if coordinate_query:
            return coordinate_query

        return await geocode_postcode(client, query)

    raise HTTPException(
        status_code=422,
        detail="Provide a postcode or coordinates with query, or pass lat and lon.",
    )


def normalize_stop(stop: dict[str, Any]) -> BusStop:
    return BusStop(
        type=stop.get("type"),
        name=stop.get("name"),
        description=stop.get("description"),
        latitude=stop.get("latitude"),
        longitude=stop.get("longitude"),
        accuracy=stop.get("accuracy"),
        atcocode=stop.get("atcocode"),
        distance=stop.get("distance"),
    )


async def fetch_bus_stops(
    client: httpx.AsyncClient,
    location: Location,
) -> list[BusStop]:
    app_id, app_key = get_transportapi_credentials()
    response = await client.get(
        TRANSPORTAPI_PLACES_URL,
        params={
            "app_id": app_id,
            "app_key": app_key,
            "lat": location.lat,
            "lon": location.lon,
            "type": "bus_stop",
        },
    )
    payload = response.json()

    if response.status_code >= 400:
        message = payload.get("error") or payload.get("message") or "TransportAPI request failed."
        raise HTTPException(status_code=response.status_code, detail=message)

    members = payload.get("member", [])
    return [normalize_stop(stop) for stop in members if isinstance(stop, dict)]


app = build_app()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/bus-stops", response_model=BusStopResponse)
async def get_bus_stops(
    query: str | None = Query(
        default=None,
        description="UK postcode or coordinates in 'lat, lon' format.",
    ),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
) -> BusStopResponse:
    async with httpx.AsyncClient(timeout=10) as client:
        location = await resolve_location(client, query, lat, lon)
        stops = await fetch_bus_stops(client, location)

    return BusStopResponse(source=location.label, count=len(stops), stops=stops)
