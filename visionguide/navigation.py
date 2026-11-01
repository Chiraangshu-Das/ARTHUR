from __future__ import annotations

import asyncio
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

from visionguide.integrations.google_services import GoogleMapsServices, RouteResult


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6_371_000.0
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    angle = 2 * math.asin(min(1.0, math.sqrt(math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)))
    return radius * angle


def distance_to_polyline_m(point: tuple[float, float], points: tuple[tuple[float, float], ...]) -> float:
    """Approximate nearest line distance using a local equirectangular projection."""
    if not points:
        return math.inf
    lat0 = math.radians(point[0])
    scale_x = 111_320.0 * math.cos(lat0)
    scale_y = 110_540.0
    px, py = point[1] * scale_x, point[0] * scale_y
    best = math.inf
    for a, b in zip(points, points[1:]):
        ax, ay = a[1] * scale_x, a[0] * scale_y
        bx, by = b[1] * scale_x, b[0] * scale_y
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        t = 0.0 if denom == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return min(best, haversine_m(point, points[0]), haversine_m(point, points[-1])) if len(points) > 1 else haversine_m(point, points[0])


class WindowsLocationProvider:
    """Windows geolocation adapter. Windows location permission and hardware are required."""
    @staticmethod
    def current_position(timeout_seconds: float = 15.0) -> tuple[float, float]:
        if __import__("os").name != "nt":
            raise RuntimeError("Live device location is supported only on Windows in this build.")
        try:
            import winrt.windows.devices.geolocation as geolocation
        except ImportError as exc:
            raise RuntimeError(
                "Windows location support is not installed. Install requirements-navigation.txt, enable Windows Location services, and allow Arthur to access location."
            ) from exc

        async def get_position():
            access = await geolocation.Geolocator.request_access_async()
            access_name = str(access).casefold()
            if "allowed" not in access_name:
                raise PermissionError("Windows location permission was not granted. Enable Location services in Windows Settings.")
            locator = geolocation.Geolocator()
            locator.desired_accuracy = geolocation.PositionAccuracy.HIGH
            locator.report_interval = 1000
            position = await locator.get_geoposition_async()
            point = position.coordinate.point.position
            return float(point.latitude), float(point.longitude)

        try:
            return asyncio.run(asyncio.wait_for(get_position(), timeout=max(2.0, timeout_seconds)))
        except PermissionError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Windows could not retrieve a current location: {exc}") from exc


@dataclass(frozen=True)
class NavigationUpdate:
    kind: str
    message: str
    route: RouteResult | None = None


class NavigationSession:
    """Basic live route guidance with GPS updates, spoken step prompts, and off-route rerouting."""
    def __init__(
        self,
        maps: GoogleMapsServices,
        destination: str,
        travel_mode: str,
        on_update: Callable[[NavigationUpdate], None],
        *,
        location_provider: type[WindowsLocationProvider] = WindowsLocationProvider,
        poll_seconds: float = 6.0,
        off_route_meters: float = 110.0,
    ):
        self.maps = maps
        self.destination = destination
        self.travel_mode = travel_mode
        self.on_update = on_update
        self.location_provider = location_provider
        self.poll_seconds = max(3.0, min(float(poll_seconds), 20.0))
        self.off_route_meters = max(50.0, float(off_route_meters))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.route: RouteResult | None = None
        self.step_index = 0
        self._offroute_count = 0
        self._last_location_error_at = 0.0
        self._last_location_error = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def start(self, initial_position: tuple[float, float] | None = None) -> RouteResult:
        if self.running:
            raise RuntimeError("Navigation is already running.")
        point = initial_position or self.location_provider.current_position()
        route = self.maps.compute_route(point, self.destination, self.travel_mode, traffic_aware=True)
        if not route.steps:
            raise RuntimeError("The route was calculated, but the provider returned no turn-by-turn steps.")
        self.route = route
        self.step_index = 0
        self._offroute_count = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="visionguide-navigation", daemon=True)
        self._thread.start()
        next_step = route.steps[0].instruction
        self.on_update(NavigationUpdate("started", f"Navigation started. Destination {self.destination}. Route distance {route.distance_text}; estimated time {route.duration_text}. First instruction: {next_step}", route))
        return route

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2.0)
        self.on_update(NavigationUpdate("stopped", "Live navigation stopped."))

    def _run(self) -> None:
        announced = {0}
        while not self._stop.wait(self.poll_seconds):
            try:
                point = self.location_provider.current_position(timeout_seconds=self.poll_seconds + 8)
                route = self.route
                if route is None:
                    return
                self._last_location_error = ""
                offroute = distance_to_polyline_m(point, route.polyline)
                if offroute > self.off_route_meters:
                    self._offroute_count += 1
                else:
                    self._offroute_count = 0
                if self._offroute_count >= 2:
                    updated = self.maps.compute_route(point, self.destination, self.travel_mode, traffic_aware=True)
                    self.route = updated
                    self.step_index = 0
                    announced = {0}
                    self._offroute_count = 0
                    next_text = updated.steps[0].instruction if updated.steps else "Continue toward the destination."
                    self.on_update(NavigationUpdate("rerouted", f"You appear to be off route; a new route has been calculated. {next_text}", updated))
                    continue

                steps = route.steps
                if self.step_index < len(steps) - 1:
                    # A step is considered approached within 130 m of its end coordinate.
                    step = steps[self.step_index]
                    if step.end_latitude is not None and step.end_longitude is not None:
                        remaining = haversine_m(point, (step.end_latitude, step.end_longitude))
                        if remaining <= 130:
                            self.step_index += 1
                            next_step = steps[self.step_index]
                            if self.step_index not in announced:
                                announced.add(self.step_index)
                                self.on_update(NavigationUpdate("instruction", f"Approaching the next maneuver: {next_step.instruction}", route))
                if route.polyline and haversine_m(point, route.polyline[-1]) < 35:
                    self.on_update(NavigationUpdate("arrived", f"You appear to have reached {self.destination}. Please confirm your arrival.", route))
                    self._stop.set()
                    return
            except Exception as exc:
                # Stay alive through temporary GPS errors, but throttle repeated status/speech prompts.
                error_text = str(exc)
                now = time.monotonic()
                if error_text != self._last_location_error or now - self._last_location_error_at >= 30.0:
                    self._last_location_error = error_text
                    self._last_location_error_at = now
                    self.on_update(NavigationUpdate("location_error", f"Live location update failed: {error_text}"))
