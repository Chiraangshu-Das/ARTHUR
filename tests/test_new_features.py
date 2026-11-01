from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from unittest.mock import Mock, patch

from visionguide.action_history import ActionHistory, summarize_recent_actions
from visionguide.desktop_actions import calculate_expression
from visionguide.integrations.google_services import GoogleMapsServices, decode_polyline
from visionguide.gesture_mouse import GestureMouse
from visionguide.navigation import distance_to_polyline_m, haversine_m
from visionguide.semantic_router import SemanticCommandRouter


class ActionHistoryTests(unittest.TestCase):
    def test_actions_and_profile_preferences_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actions.sqlite3"
            history = ActionHistory(path)
            history.record("calculator", "Calculate 2+2", "2+2 = 4")
            history.set_preference("sample_user", "preferred_name", "Sir")

            reopened = ActionHistory(path)
            self.assertEqual(reopened.last()["result"], "2+2 = 4")
            self.assertEqual(reopened.get_preferences("sample_user")["preferred_name"], "Sir")
            self.assertIn("completed", summarize_recent_actions(reopened.recent()))
            self.assertEqual(reopened.delete_preferences("sample_user"), 1)
            self.assertEqual(reopened.get_preferences("sample_user"), {})


class DeterministicCommandTests(unittest.TestCase):
    def setUp(self):
        self.router = SemanticCommandRouter(enable_local_semantic=False)

    def test_literal_text_does_not_become_calculation(self):
        routed = self.router.route("Type 2+2=")
        self.assertEqual(routed.action, "type_text")
        self.assertEqual(routed.arguments["text"], "2+2=")

    def test_calculation_and_calculator_execution_are_distinct(self):
        self.assertEqual(self.router.route("Calculate 2+2").action, "calculate_expression")
        routed = self.router.route("Open Calculator and sum 2+2")
        self.assertEqual(routed.action, "calculator_calculate")
        self.assertEqual(routed.arguments["expression"], "2+2")

    def test_draft_request_is_not_literal_typing(self):
        routed = self.router.route("Write an email to my professor asking for an assignment extension")
        self.assertEqual(routed.action, "draft_and_type")

    def test_keyboard_gestures_focus_navigation_and_followups(self):
        self.assertEqual(self.router.route("Open the virtual keyboard").action, "keyboard_toggle")
        self.assertEqual(self.router.route("Enable hand gestures").action, "gesture_control")
        focus = self.router.route("Focus on YouTube search bar")
        self.assertEqual(focus.action, "focus_target")
        self.assertEqual(focus.arguments["element"], "search bar")
        self.assertEqual(self.router.route("What was the result?").action, "action_result")
        route = self.router.route("Get directions from Salt Lake to Howrah by motorcycle")
        self.assertEqual(route.action, "route_start")
        self.assertEqual(route.arguments["destination"], "Howrah")
        self.assertEqual(route.arguments["travel_mode"], "TWO_WHEELER")
        bicycle = self.router.route("Get directions from Salt Lake to Howrah by bicycle")
        self.assertEqual(bicycle.arguments["travel_mode"], "BICYCLE")
        self.assertEqual(bicycle.arguments["origin"], "Salt Lake")

    def test_face_preference_and_visual_research_intents(self):
        preference = self.router.route("Remember that I prefer to be called Sir")
        self.assertEqual(preference.action, "profile_preference_set")
        self.assertEqual(preference.arguments["value"], "Sir")
        self.assertEqual(self.router.route("Tell me about this air fryer").action, "product_lookup")
        self.assertEqual(self.router.route("Tell me today's weather").action, "weather_lookup")

    def test_basic_math_is_restricted_and_correct(self):
        self.assertEqual(calculate_expression("(2 + 3) * 4"), ("(2 + 3) * 4", 20))
        with self.assertRaises(ValueError):
            calculate_expression("__import__('os').system('whoami')")


class GoogleServicesTests(unittest.TestCase):
    class FakeResponse:
        def __init__(self, data):
            self.data = data
            self.text = json.dumps(data)

        def raise_for_status(self):
            return None

        def json(self):
            return self.data

    def make_service(self, directory):
        return GoogleMapsServices(api_key="test-key", cache_path=Path(directory) / "services.sqlite3")

    def test_weather_uses_mocked_provider_and_cache(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VISIONGUIDE_GOOGLE_DAILY_WEATHER_CAP": "4", "VISIONGUIDE_GOOGLE_DAILY_GEOCODE_CAP": "4"}):
            service = self.make_service(directory)
            service.geocode = Mock(return_value=(22.57, 88.36))
            payload = {
                "weatherCondition": {"description": {"text": "Clear"}},
                "temperature": {"degrees": 29.5}, "feelsLikeTemperature": {"degrees": 31},
                "relativeHumidity": 68, "precipitation": {"probability": {"percent": 10}},
                "wind": {"speed": {"value": 9, "unit": "KILOMETERS_PER_HOUR"}}, "currentTime": "2026-10-26T12:00:00Z",
            }
            with patch("visionguide.integrations.google_services.requests.get", return_value=self.FakeResponse(payload)) as request:
                result = service.format_weather("Kolkata")
                again = service.format_weather("Kolkata")
            self.assertIn("Clear", result)
            self.assertIn("29.5 degrees Celsius", result)
            self.assertEqual(result, again)
            request.assert_called_once()

    def test_route_parses_steps_and_sanitizes_html(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VISIONGUIDE_GOOGLE_DAILY_ROUTE_CAP": "4"}):
            service = self.make_service(directory)
            payload = {"routes": [{
                "duration": "600s", "staticDuration": "720s", "distanceMeters": 1500,
                "polyline": {"encodedPolyline": "??"},
                "legs": [{"steps": [{"distanceMeters": 200,
                    "navigationInstruction": {"instructions": "Turn <b>left</b> onto Main Street"},
                    "endLocation": {"latLng": {"latitude": 22.57, "longitude": 88.36}}}]}],
            }]}
            with patch("visionguide.integrations.google_services.requests.post", return_value=self.FakeResponse(payload)) as request:
                route = service.compute_route("22.57,88.36", "Howrah", "DRIVE", traffic_aware=True)
            self.assertEqual(route.distance_meters, 1500)
            self.assertEqual(route.duration_seconds, 600)
            self.assertEqual(route.steps[0].instruction, "Turn left onto Main Street")
            self.assertTrue(route.traffic_aware)
            self.assertEqual(request.call_count, 1)

    def test_visual_search_cache_does_not_consume_daily_allowance_twice(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VISIONGUIDE_GOOGLE_DAILY_VISUAL_CAP": "1"}):
            service = self.make_service(directory)
            frame = np.zeros((32, 32, 3), dtype=np.uint8)
            payload = {"responses": [{"webDetection": {"webEntities": [{"description": "sample item"}]}}]}
            with patch("visionguide.integrations.google_services.requests.post", return_value=self.FakeResponse(payload)) as request:
                first = service.web_search_image(frame)
                second = service.web_search_image(frame)
            self.assertEqual(first, second)
            request.assert_called_once()

    def test_route_mode_aliases_support_bicycle_and_two_wheeler(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VISIONGUIDE_GOOGLE_DAILY_ROUTE_CAP": "4"}):
            service = self.make_service(directory)
            payload = {"routes": [{"duration": "600s", "distanceMeters": 100, "polyline": {"encodedPolyline": "??"}, "legs": []}]}
            with patch("visionguide.integrations.google_services.requests.post", return_value=self.FakeResponse(payload)) as request:
                service.compute_route("Salt Lake", "Howrah", "bicycle", traffic_aware=True)
                body = request.call_args.kwargs["json"]
                self.assertEqual(body["travelMode"], "BICYCLE")
                self.assertNotIn("routingPreference", body)


    def test_daily_budget_stops_additional_provider_requests(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VISIONGUIDE_GOOGLE_DAILY_VISUAL_CAP": "1"}):
            service = self.make_service(directory)
            service._check_daily_budget("Visual Search", "VISIONGUIDE_GOOGLE_DAILY_VISUAL_CAP", 5)
            with self.assertRaisesRegex(RuntimeError, "daily cap"):
                service._check_daily_budget("Visual Search", "VISIONGUIDE_GOOGLE_DAILY_VISUAL_CAP", 5)

    def test_known_google_encoded_polyline_and_distance_math(self):
        points = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        self.assertEqual(len(points), 3)
        self.assertGreater(haversine_m(points[0], points[-1]), 0)
        self.assertLess(distance_to_polyline_m(points[0], points), 1)


class GestureCalibrationLogicTests(unittest.TestCase):
    def test_coordinate_mapping_clamps_and_normalizes_calibrated_span(self):
        self.assertEqual(GestureMouse._map_coordinate(0.25, 0.25, 0.75), 0.0)
        self.assertEqual(GestureMouse._map_coordinate(0.50, 0.25, 0.75), 0.5)
        self.assertEqual(GestureMouse._map_coordinate(0.90, 0.25, 0.75), 1.0)
        self.assertEqual(GestureMouse._map_coordinate(0.5, 0.5, 0.5), 0.5)


if __name__ == "__main__":
    unittest.main()
