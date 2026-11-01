from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import closing
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests


class JsonTTLCache:
    """Small SQLite TTL cache. Live coordinates and active navigation are never cached."""
    def __init__(self, path: Path | None = None, ttl_seconds: int = 900):
        self.path = Path(path or (Path("data") / "cache" / "google_services.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = max(0, int(ttl_seconds))
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS usage (service TEXT NOT NULL, utc_date TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(service, utc_date))")
            connection.commit()

    def get(self, key: str) -> Any | None:
        import time
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute("SELECT value, expires FROM cache WHERE key=?", (key,)).fetchone()
            if not row:
                return None
            if float(row[1]) < time.time():
                connection.execute("DELETE FROM cache WHERE key=?", (key,))
                connection.commit()
                return None
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                return None

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        import time
        ttl = self.ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("INSERT OR REPLACE INTO cache(key,value,expires) VALUES (?,?,?)",
                               (key, json.dumps(value, ensure_ascii=False), time.time() + ttl))
            connection.commit()


def google_api_key() -> str:
    """Return a Maps-Platform key; do not silently use a Cloud-only restricted key."""
    for name in ("GOOGLE_MAPS_API_KEY", "GOOGLE_WEATHER_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def google_cloud_api_key(service: str = "generic") -> str:
    """Resolve a key for non-Maps Google Cloud APIs, preferring service-specific keys."""
    names_by_service = {
        "vision": ("GOOGLE_VISION_API_KEY", "GOOGLE_CLOUD_API_KEY", "GOOGLE_API_KEY"),
        "translation": ("GOOGLE_TRANSLATE_API_KEY", "GOOGLE_CLOUD_API_KEY", "GOOGLE_API_KEY"),
        "language": ("GOOGLE_NATURAL_LANGUAGE_API_KEY", "GOOGLE_CLOUD_API_KEY", "GOOGLE_API_KEY"),
    }
    names = names_by_service.get(service, ("GOOGLE_CLOUD_API_KEY", "GOOGLE_API_KEY"))
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _duration_seconds(raw: str | int | float | None) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(raw).strip())
    return int(float(match.group(1))) if match else 0


def _lat_lng(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        if "latitude" in value and "longitude" in value:
            return float(value["latitude"]), float(value["longitude"])
        value = value.get("latLng", value)
        if isinstance(value, dict) and "latitude" in value and "longitude" in value:
            return float(value["latitude"]), float(value["longitude"])
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", value)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng
    return None


@dataclass(frozen=True)
class RouteStep:
    instruction: str
    distance_meters: int
    end_latitude: float | None = None
    end_longitude: float | None = None


@dataclass(frozen=True)
class RouteResult:
    origin: str
    destination: str
    travel_mode: str
    distance_meters: int
    duration_seconds: int
    static_duration_seconds: int
    steps: tuple[RouteStep, ...]
    polyline: tuple[tuple[float, float], ...]
    traffic_aware: bool

    @property
    def distance_text(self) -> str:
        km = self.distance_meters / 1000
        return f"{km:.1f} kilometres" if km >= 1 else f"{self.distance_meters} metres"

    @property
    def duration_text(self) -> str:
        minutes = max(1, round(self.duration_seconds / 60))
        hours, mins = divmod(minutes, 60)
        return f"{hours} hours {mins} minutes" if hours else f"{mins} minutes"


def decode_polyline(encoded: str) -> tuple[tuple[float, float], ...]:
    points = []
    index = lat = lng = 0
    while index < len(encoded):
        for coord in (0, 1):
            result = shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if coord == 0:
                lat += delta
            else:
                lng += delta
        points.append((lat / 1e5, lng / 1e5))
    return tuple(points)


class GoogleMapsServices:
    """Maps Platform REST adapter with cached lookups and per-device daily request caps."""
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    WEATHER_URL = "https://weather.googleapis.com/v1/currentConditions:lookup"
    AIR_QUALITY_URL = "https://airquality.googleapis.com/v1/currentConditions:lookup"
    POLLEN_URL = "https://pollen.googleapis.com/v1/forecast:lookup"
    PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
    TIMEZONE_URL = "https://maps.googleapis.com/maps/api/timezone/json"
    ROADS_URL = "https://roads.googleapis.com/v1/snapToRoads"
    GEOLOCATION_URL = "https://www.googleapis.com/geolocation/v1/geolocate"
    VISION_URL = "https://vision.googleapis.com/v1/images:annotate"

    def __init__(self, api_key: str | None = None, cache_path: Path | None = None, timeout: float = 12.0):
        self.api_key = (api_key or google_api_key()).strip()
        # If a caller injects one key explicitly (for example in tests), allow it to be
        # reused deliberately. Normal app configuration keeps Cloud Vision on its own key.
        self.cloud_api_key = google_cloud_api_key("vision") or (str(api_key).strip() if api_key else "")
        self.cache = JsonTTLCache(cache_path)
        self.timeout = max(2.0, min(float(timeout), 30.0))

    def _check_daily_budget(self, service: str, env_name: str, default_limit: int) -> None:
        """Per-device daily request cap to make accidental API loops less costly.

        This is an application-side guard, not a substitute for Google Cloud quotas/budgets.
        """
        import time
        raw = os.getenv(env_name, str(default_limit)).strip()
        try:
            limit = max(0, min(int(raw), 100_000))
        except ValueError:
            limit = default_limit
        if limit == 0:
            raise RuntimeError(f"Google {service} requests are disabled by {env_name}=0.")
        today = datetime.now(timezone.utc).date().isoformat()
        with closing(sqlite3.connect(self.cache.path, timeout=5)) as connection:
            # Serialize concurrent calls so multiple worker threads cannot overshoot the cap.
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT count FROM usage WHERE service=? AND utc_date=?", (service, today)).fetchone()
            used = int(row[0]) if row else 0
            if used >= limit:
                connection.rollback()
                raise RuntimeError(f"The local daily cap for Google {service} requests ({limit}/UTC day) has been reached. Change {env_name} only after reviewing current Google Cloud quotas and billing.")
            connection.execute(
                "INSERT INTO usage(service, utc_date, count) VALUES (?,?,1) ON CONFLICT(service,utc_date) DO UPDATE SET count=count+1",
                (service, today),
            )
            connection.commit()

    def _require_key(self):
        if not self.api_key:
            raise RuntimeError("A Google Maps/Cloud API key is not configured. Set GOOGLE_MAPS_API_KEY or GOOGLE_CLOUD_API_KEY in .env.")

    def geocode(self, location: str | tuple[float, float]) -> tuple[float, float]:
        if isinstance(location, (tuple, list)) and len(location) == 2:
            lat, lng = float(location[0]), float(location[1])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError("Latitude/longitude are outside valid ranges.")
            return lat, lng
        coordinate = _lat_lng(str(location))
        if coordinate:
            return coordinate
        address = " ".join(str(location).split()).strip()
        if not address or len(address) > 300:
            raise ValueError("Enter a place name, address, or latitude/longitude pair.")
        key = "geocode:" + address.casefold()
        cached = self.cache.get(key)
        if cached:
            return float(cached[0]), float(cached[1])
        self._require_key()
        self._check_daily_budget("Geocoding", "VISIONGUIDE_GOOGLE_DAILY_GEOCODE_CAP", 30)
        try:
            response = requests.get(self.GEOCODE_URL, params={"address": address, "key": self.api_key}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Geocoding request failed: {exc}") from exc
        if payload.get("status") != "OK" or not payload.get("results"):
            raise RuntimeError(f"Could not resolve {address!r} (Geocoding status: {payload.get('status', 'unknown')}).")
        point = payload["results"][0]["geometry"]["location"]
        coords = (float(point["lat"]), float(point["lng"]))
        self.cache.put(key, coords, 86400)
        return coords

    def current_weather(self, location: str) -> dict[str, Any]:
        cache_key = "weather:" + " ".join(str(location).casefold().split())
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        lat, lng = self.geocode(location)
        self._require_key()
        self._check_daily_budget("Weather", "VISIONGUIDE_GOOGLE_DAILY_WEATHER_CAP", 20)
        try:
            response = requests.get(self.WEATHER_URL, params={
                "key": self.api_key, "location.latitude": lat, "location.longitude": lng,
                "languageCode": "en", "unitsSystem": "METRIC",
            }, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Weather request failed: {exc}") from exc
        condition = data.get("weatherCondition", {}).get("description", {}).get("text", "Current conditions unavailable")
        temperature = data.get("temperature", {}).get("degrees")
        feels = data.get("feelsLikeTemperature", {}).get("degrees")
        precip = data.get("precipitation", {}).get("probability", {}).get("percent")
        wind = data.get("wind", {}).get("speed", {})
        result = {
            "location": location, "condition": condition,
            "temperature_c": temperature, "feels_like_c": feels,
            "humidity_percent": data.get("relativeHumidity"), "uv_index": data.get("uvIndex"),
            "precipitation_percent": precip, "wind_speed": wind.get("value"),
            "wind_unit": wind.get("unit", "KILOMETERS_PER_HOUR"),
            "observed_at": data.get("currentTime"), "timezone": data.get("timeZone", {}).get("id"),
        }
        self.cache.put(cache_key, result, 600)
        return result

    def format_weather(self, location: str) -> str:
        data = self.current_weather(location)
        if data["temperature_c"] is None:
            temp = "temperature unavailable"
        else:
            temp = f"{float(data['temperature_c']):.1f} degrees Celsius"
        parts = [f"Current weather for {location}: {data['condition']}, {temp}."]
        if data.get("feels_like_c") is not None:
            parts.append(f"Feels like {float(data['feels_like_c']):.1f} degrees Celsius.")
        if data.get("humidity_percent") is not None:
            parts.append(f"Humidity {int(data['humidity_percent'])} percent.")
        if data.get("precipitation_percent") is not None:
            parts.append(f"Precipitation probability {int(data['precipitation_percent'])} percent.")
        if data.get("wind_speed") is not None:
            parts.append(f"Wind {data['wind_speed']} {data.get('wind_unit', '').replace('_', ' ').lower()}.")
        if data.get("observed_at"):
            parts.append(f"Provider observation time: {data['observed_at']}.")
        return " ".join(parts)

    def compute_route(self, origin: str | tuple[float, float], destination: str, travel_mode: str = "DRIVE", *, traffic_aware: bool = True) -> RouteResult:
        self._require_key()
        mode_aliases = {
            "car": "DRIVE", "drive": "DRIVE", "driving": "DRIVE",
            "motorcycle": "TWO_WHEELER", "motorbike": "TWO_WHEELER", "two-wheeler": "TWO_WHEELER", "two_wheeler": "TWO_WHEELER",
            "walking": "WALK", "walk": "WALK", "bicycle": "BICYCLE", "cycling": "BICYCLE", "bike": "BICYCLE",
            "transit": "TRANSIT", "public transport": "TRANSIT",
        }
        mode = mode_aliases.get(str(travel_mode).strip().casefold(), str(travel_mode).strip().upper())
        allowed = {"DRIVE", "TWO_WHEELER", "WALK", "BICYCLE", "TRANSIT"}
        if mode not in allowed:
            raise ValueError(f"Unsupported travel mode: {travel_mode!r}. Choose car, two-wheeler, walking, cycling, or transit.")
        self._check_daily_budget("Routes", "VISIONGUIDE_GOOGLE_DAILY_ROUTE_CAP", 20)
        origin_point = _lat_lng(origin) if isinstance(origin, str) else (float(origin[0]), float(origin[1]))
        destination_point = _lat_lng(destination)
        origin_location = {"location": {"latLng": {"latitude": origin_point[0], "longitude": origin_point[1]}}} if origin_point else {"address": str(origin)}
        destination_location = {"location": {"latLng": {"latitude": destination_point[0], "longitude": destination_point[1]}}} if destination_point else {"address": str(destination)}
        body: dict[str, Any] = {"origin": origin_location, "destination": destination_location, "travelMode": mode, "computeAlternativeRoutes": False}
        effective_traffic = bool(traffic_aware and mode in {"DRIVE", "TWO_WHEELER"})
        if effective_traffic:
            body["routingPreference"] = "TRAFFIC_AWARE"
            body["departureTime"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        fields = "routes.duration,routes.staticDuration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs.steps.distanceMeters,routes.legs.steps.navigationInstruction.instructions,routes.legs.steps.endLocation.latLng"
        try:
            response = requests.post(self.ROUTES_URL, headers={
                "Content-Type": "application/json", "X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": fields,
            }, json=body, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            detail = ""
            if getattr(exc, "response", None) is not None:
                detail = f" Response: {exc.response.text[:500]}"
            raise RuntimeError(f"Route request failed: {exc}.{detail}") from exc
        routes = payload.get("routes") or []
        if not routes:
            raise RuntimeError("The route provider returned no route for those locations.")
        route = routes[0]
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                end = step.get("endLocation", {}).get("latLng", {})
                steps.append(RouteStep(
                    instruction=re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(step.get("navigationInstruction", {}).get("instructions", "Continue ahead")))).strip(),
                    distance_meters=int(step.get("distanceMeters", 0) or 0),
                    end_latitude=float(end["latitude"]) if "latitude" in end else None,
                    end_longitude=float(end["longitude"]) if "longitude" in end else None,
                ))
        encoded = route.get("polyline", {}).get("encodedPolyline", "")
        start_label = str(origin) if not isinstance(origin, tuple) else f"{origin[0]:.5f}, {origin[1]:.5f}"
        return RouteResult(
            origin=start_label, destination=str(destination), travel_mode=mode,
            distance_meters=int(route.get("distanceMeters", 0) or 0),
            duration_seconds=_duration_seconds(route.get("duration")),
            static_duration_seconds=_duration_seconds(route.get("staticDuration")),
            steps=tuple(steps), polyline=decode_polyline(encoded), traffic_aware=effective_traffic,
        )

    def open_route_in_maps(self, origin: str, destination: str, travel_mode: str = "DRIVE") -> str:
        import webbrowser
        mode = {"DRIVE": "driving", "TWO_WHEELER": "two-wheeler", "WALK": "walking", "BICYCLE": "bicycling", "TRANSIT": "transit"}.get(str(travel_mode).upper(), "driving")
        url = "https://www.google.com/maps/dir/?api=1&origin=" + quote_plus(origin) + "&destination=" + quote_plus(destination) + "&travelmode=" + quote_plus(mode)
        if not webbrowser.open(url, new=2):
            raise RuntimeError("Could not open Google Maps in the default browser.")
        return url

    def places_search(self, query: str, *, location_bias: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        """Search place names using Places API (New), requesting only lightweight fields."""
        query = " ".join(str(query).split()).strip()
        if not query or len(query) > 250:
            raise ValueError("Provide a place search query up to 250 characters.")
        limit = max(1, min(int(limit), 20))
        cache_key = "places:" + hashlib.sha256(f"{query.casefold()}|{str(location_bias or '').casefold()}|{limit}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        self._require_key()
        body: dict[str, Any] = {"textQuery": query, "pageSize": limit, "languageCode": "en"}
        if location_bias:
            lat, lng = self.geocode(location_bias)
            body["locationBias"] = {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 15000.0}}
        self._check_daily_budget("Places", "VISIONGUIDE_GOOGLE_DAILY_PLACES_CAP", 20)
        try:
            response = requests.post(self.PLACES_URL,
                headers={"Content-Type": "application/json", "X-Goog-Api-Key": self.api_key,
                        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.primaryType,places.googleMapsUri"},
                json=body, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            detail = f" Response: {exc.response.text[:400]}" if getattr(exc, "response", None) is not None else ""
            raise RuntimeError(f"Places search failed: {exc}.{detail}") from exc
        result = []
        for place in payload.get("places", []) or []:
            loc = place.get("location", {}) or {}
            result.append({"id": str(place.get("id", "")),
                "name": str(place.get("displayName", {}).get("text", "")),
                "address": str(place.get("formattedAddress", "")),
                "type": str(place.get("primaryType", "")),
                "latitude": loc.get("latitude"), "longitude": loc.get("longitude"),
                "maps_url": str(place.get("googleMapsUri", ""))})
        self.cache.put(cache_key, result, 3600)
        return result

    def current_air_quality(self, location: str) -> dict[str, Any]:
        key_norm = " ".join(str(location).casefold().split())
        cache_key = "airquality:" + hashlib.sha256(key_norm.encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        lat, lng = self.geocode(location)
        self._require_key()
        self._check_daily_budget("Air Quality", "VISIONGUIDE_GOOGLE_DAILY_AIR_QUALITY_CAP", 10)
        body = {"location": {"latitude": lat, "longitude": lng},
                "extraComputations": ["LOCAL_AQI", "HEALTH_RECOMMENDATIONS"]}
        try:
            response = requests.post(self.AIR_QUALITY_URL, params={"key": self.api_key}, json=body, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            detail = f" Response: {exc.response.text[:400]}" if getattr(exc, "response", None) is not None else ""
            raise RuntimeError(f"Air-quality request failed: {exc}.{detail}") from exc
        result = {"location": location, "date_time": data.get("dateTime", ""),
                  "indexes": [{"code": i.get("code", ""), "name": i.get("displayName", ""),
                               "aqi": i.get("aqi"), "aqi_display": i.get("aqiDisplay", ""),
                               "category": i.get("category", ""), "dominant_pollutant": i.get("dominantPollutant", "")}
                              for i in data.get("indexes", []) or []],
                  "pollutants": [{"code": p.get("code", ""), "name": p.get("displayName", ""),
                                  "concentration": p.get("concentration", {}), "additional_info": p.get("additionalInfo", {})}
                                 for p in data.get("pollutants", []) or []],
                  "health_recommendations": data.get("healthRecommendations", {})}
        self.cache.put(cache_key, result, 900)
        return result

    def pollen_forecast(self, location: str, days: int = 3) -> dict[str, Any]:
        days = max(1, min(int(days), 5))
        cache_key = "pollen:" + hashlib.sha256(f"{str(location).casefold()}|{days}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        lat, lng = self.geocode(location)
        self._require_key()
        self._check_daily_budget("Pollen", "VISIONGUIDE_GOOGLE_DAILY_POLLEN_CAP", 10)
        try:
            response = requests.get(self.POLLEN_URL, params={"key": self.api_key, "location.latitude": lat,
                "location.longitude": lng, "days": days, "languageCode": "en"}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            detail = f" Response: {exc.response.text[:400]}" if getattr(exc, "response", None) is not None else ""
            raise RuntimeError(f"Pollen forecast failed: {exc}.{detail}") from exc
        result = {"location": location, "daily_info": data.get("dailyInfo", []) or [],
                  "plant_info": data.get("plantInfo", []) or []}
        self.cache.put(cache_key, result, 21600)
        return result

    def timezone_for_location(self, location: str, timestamp: int | None = None) -> dict[str, Any]:
        lat, lng = self.geocode(location)
        instant = int(timestamp if timestamp is not None else datetime.now(timezone.utc).timestamp())
        cache_key = f"timezone:{lat:.5f},{lng:.5f}:{instant // 3600}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        self._require_key()
        self._check_daily_budget("Time Zone", "VISIONGUIDE_GOOGLE_DAILY_TIMEZONE_CAP", 30)
        try:
            response = requests.get(self.TIMEZONE_URL, params={"location": f"{lat},{lng}", "timestamp": instant,
                "key": self.api_key, "language": "en"}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Time-zone lookup failed: {exc}") from exc
        if data.get("status") != "OK":
            raise RuntimeError(f"Time-zone lookup returned {data.get('status', 'unknown')}.")
        zone_id = str(data.get("timeZoneId", ""))
        try:
            local_time = datetime.fromtimestamp(instant, ZoneInfo(zone_id)).isoformat() if zone_id else datetime.fromtimestamp(instant, timezone.utc).isoformat()
        except (ZoneInfoNotFoundError, ValueError):
            local_time = datetime.fromtimestamp(instant, timezone.utc).isoformat()
        result = {"location": location, "time_zone_id": zone_id,
                  "time_zone_name": data.get("timeZoneName", ""), "raw_offset_seconds": data.get("rawOffset", 0),
                  "dst_offset_seconds": data.get("dstOffset", 0), "local_time": local_time}
        self.cache.put(cache_key, result, 3600)
        return result

    def snap_to_roads(self, path: list[tuple[float, float] | list[float]], *, interpolate: bool = True) -> list[dict[str, Any]]:
        if not isinstance(path, list) or not 2 <= len(path) <= 100:
            raise ValueError("Roads API snapping requires a list of 2–100 latitude/longitude points.")
        points: list[tuple[float, float]] = []
        for point in path:
            if not isinstance(point, (tuple, list)) or len(point) != 2:
                raise ValueError("Each road point must be [latitude, longitude].")
            lat, lng = float(point[0]), float(point[1])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError("Road point coordinates are out of range.")
            points.append((lat, lng))
        self._require_key()
        cache_key = "roads:" + hashlib.sha256(f"{points}|{bool(interpolate)}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        self._check_daily_budget("Roads", "VISIONGUIDE_GOOGLE_DAILY_ROADS_CAP", 10)
        path_text = "|".join(f"{lat:.6f},{lng:.6f}" for lat, lng in points)
        try:
            response = requests.get(self.ROADS_URL, params={"path": path_text, "interpolate": str(bool(interpolate)).lower(),
                "key": self.api_key}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            detail = f" Response: {exc.response.text[:400]}" if getattr(exc, "response", None) is not None else ""
            raise RuntimeError(f"Road snapping failed: {exc}.{detail}") from exc
        result = [{"latitude": item.get("location", {}).get("latitude"),
                   "longitude": item.get("location", {}).get("longitude"),
                   "place_id": str(item.get("placeId", "")), "original_index": item.get("originalIndex")}
                  for item in data.get("snappedPoints", []) or []]
        self.cache.put(cache_key, result, 3600)
        return result

    def geolocate_wifi(self, access_points: list[dict[str, Any]], *, consent_confirmed: bool = False) -> dict[str, Any]:
        """Resolve explicitly supplied nearby Wi-Fi observations; never collects them itself."""
        if not consent_confirmed:
            raise PermissionError("Uploading nearby Wi-Fi identifiers to Google requires explicit consent.")
        if not isinstance(access_points, list) or not 1 <= len(access_points) <= 15:
            raise ValueError("Provide 1–15 nearby Wi-Fi access-point records.")
        clean: list[dict[str, Any]] = []
        for item in access_points:
            if not isinstance(item, dict):
                raise ValueError("Each Wi-Fi access point must be an object.")
            mac = str(item.get("macAddress", "")).strip()
            if not re.fullmatch(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
                raise ValueError("Each Wi-Fi access point requires a valid MAC address.")
            row: dict[str, Any] = {"macAddress": mac}
            if "signalStrength" in item:
                row["signalStrength"] = max(-100, min(0, int(item["signalStrength"])))
            if "channel" in item:
                row["channel"] = max(1, min(196, int(item["channel"])))
            clean.append(row)
        self._require_key()
        self._check_daily_budget("Geolocation", "VISIONGUIDE_GOOGLE_DAILY_GEOLOCATION_CAP", 3)
        try:
            response = requests.post(self.GEOLOCATION_URL, params={"key": self.api_key},
                json={"wifiAccessPoints": clean}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Network geolocation failed: {exc}") from exc
        point = data.get("location", {}) or {}
        if "lat" not in point or "lng" not in point:
            raise RuntimeError("Google Geolocation did not return coordinates.")
        return {"latitude": float(point["lat"]), "longitude": float(point["lng"]),
                "accuracy_meters": data.get("accuracy"),
                "note": "Approximate network-derived location; it is not GPS and may be inaccurate indoors."}

    def web_search_image(self, frame) -> dict[str, Any]:
        """Google Cloud Vision Web Detection: visual matches/entities, not identity verification."""
        if not self.cloud_api_key:
            raise RuntimeError("Cloud Vision is optional and needs GOOGLE_CLOUD_API_KEY or GOOGLE_VISION_API_KEY with Cloud Vision API enabled and allowed by key restrictions.")
        import cv2
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise RuntimeError("The camera frame could not be encoded for visual search.")
        digest = hashlib.sha256(encoded.tobytes()).hexdigest()
        cached = self.cache.get("visual:" + digest)
        if cached:
            return cached
        # Only billable remote calls consume the local daily allowance; cached frames do not.
        self._check_daily_budget("Visual Search", "VISIONGUIDE_GOOGLE_DAILY_VISUAL_CAP", 5)
        content = base64.b64encode(encoded.tobytes()).decode("ascii")
        body = {"requests": [{"image": {"content": content}, "features": [{"type": "WEB_DETECTION", "maxResults": 8}]}]}
        try:
            response = requests.post(self.VISION_URL, params={"key": self.cloud_api_key}, json=body, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Google Cloud Vision web detection failed: {exc}") from exc
        answers = payload.get("responses") or []
        if not answers:
            raise RuntimeError("Google Cloud Vision returned no image-search response.")
        answer = answers[0]
        if answer.get("error"):
            raise RuntimeError("Google Cloud Vision error: " + str(answer["error"].get("message", "unknown error")))
        web = answer.get("webDetection", {})
        result = {
            "best_guess_labels": [item.get("label", "") for item in web.get("bestGuessLabels", []) if item.get("label")],
            "entities": [item.get("description", "") for item in web.get("webEntities", []) if item.get("description")],
            "pages": [{"title": item.get("pageTitle", ""), "url": item.get("url", "")} for item in web.get("pagesWithMatchingImages", []) if item.get("url")],
            "similar_images": [item.get("url", "") for item in web.get("visuallySimilarImages", []) if item.get("url")],
            "matching_images": [item.get("url", "") for item in web.get("fullMatchingImages", []) if item.get("url")],
        }
        self.cache.put("visual:" + digest, result, 86400)
        return result

    @staticmethod
    def format_visual_search(result: dict[str, Any]) -> str:
        sections = []
        if result.get("best_guess_labels"):
            sections.append("Search's best-guess labels: " + ", ".join(result["best_guess_labels"][:5]))
        if result.get("entities"):
            sections.append("Related web entities: " + ", ".join(result["entities"][:8]))
        if result.get("pages"):
            sections.append("Pages with matching images:\n" + "\n".join(
                f"- {page.get('title') or page.get('url')}: {page.get('url')}" for page in result["pages"][:8]
            ))
        if result.get("similar_images"):
            sections.append("Visually similar image links:\n" + "\n".join(result["similar_images"][:8]))
        if not sections:
            return "No public visual matches were returned for this frame."
        return "\n\n".join(sections) + "\n\nThese are visual-search matches, not proof of a person's identity or proof that a visually similar product is the exact model shown."


def execute_google_maps_operation(operation: str, args: dict[str, Any], service: GoogleMapsServices | None = None) -> dict[str, Any]:
    """Allowlisted dispatcher for additional Maps Platform endpoints."""
    maps = service or GoogleMapsServices()
    operation = str(operation).strip().casefold()
    if operation == "places_search":
        return {"kind": operation, "places": maps.places_search(str(args.get("query", "")),
            location_bias=str(args.get("location_bias", "")).strip() or None, limit=int(args.get("limit", 8) or 8))}
    if operation == "air_quality":
        return {"kind": operation, "air_quality": maps.current_air_quality(str(args.get("location", "")))}
    if operation == "pollen_forecast":
        return {"kind": operation, "pollen": maps.pollen_forecast(str(args.get("location", "")), int(args.get("days", 3) or 3))}
    if operation == "timezone_lookup":
        return {"kind": operation, "timezone": maps.timezone_for_location(str(args.get("location", "")))}
    if operation == "roads_snap":
        import json
        raw_path = args.get("path_json", "")
        try:
            path = json.loads(raw_path) if isinstance(raw_path, str) else raw_path
        except json.JSONDecodeError as exc:
            raise ValueError("Road points must be JSON such as [[22.57,88.36],[22.58,88.37]].") from exc
        return {"kind": operation, "snapped_points": maps.snap_to_roads(path, interpolate=bool(args.get("interpolate", True)))}
    raise ValueError(f"Unsupported Google Maps operation: {operation!r}.")
