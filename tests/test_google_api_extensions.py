import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from visionguide.integrations import google_cloud_services as cloud
from visionguide.integrations.google_services import GoogleMapsServices, execute_google_maps_operation
from visionguide.integrations.google_workspace import (
    GOOGLE_WORKSPACE_WRITE_OPERATIONS,
    _SCOPE_PROFILES,
    docs_create,
    execute_google_workspace_operation,
)
from visionguide.semantic_router import SemanticCommandRouter


class _Response:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class GoogleScopeProfileTests(unittest.TestCase):
    def test_core_scopes_are_narrower_than_calendar_readonly(self):
        self.assertIn("https://www.googleapis.com/auth/calendar.events.readonly", _SCOPE_PROFILES["core"])
        self.assertNotIn("https://www.googleapis.com/auth/calendar.readonly", _SCOPE_PROFILES["core"])
        self.assertNotIn("https://www.googleapis.com/auth/drive.readonly", _SCOPE_PROFILES["core"])
        self.assertIn("https://www.googleapis.com/auth/cloud-translation", _SCOPE_PROFILES["cloud_translation"])
        self.assertIn("https://www.googleapis.com/auth/cloud-language", _SCOPE_PROFILES["cloud_language"])

    def test_workspace_write_ops_are_explicitly_classified(self):
        self.assertTrue({"docs_create", "sheets_update", "tasks_create", "meet_create"}.issubset(GOOGLE_WORKSPACE_WRITE_OPERATIONS))

    def test_docs_create_requires_confirmation_before_oauth_or_network(self):
        with patch("visionguide.integrations.google_workspace._service") as make_service:
            with self.assertRaises(PermissionError):
                docs_create("Test title", "Test content", confirmed=False)
            make_service.assert_not_called()

    def test_workspace_dispatch_rejects_unknown_operation(self):
        with self.assertRaises(ValueError):
            execute_google_workspace_operation("delete_everything", {})


class GoogleMapsExtensionTests(unittest.TestCase):
    def make_service(self, temp_dir):
        return GoogleMapsServices(api_key="test-map-key", cache_path=Path(temp_dir) / "google_cache.sqlite3")

    def test_places_search_uses_field_mask_and_caches_result(self):
        payload = {"places": [{"id": "p1", "displayName": {"text": "Example Pharmacy"},
                               "formattedAddress": "1 Test Road", "location": {"latitude": 22.5, "longitude": 88.3},
                               "primaryType": "pharmacy", "googleMapsUri": "https://maps.google.com/?q=p1"}]}
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make_service(tmp)
            with patch.object(service, "_check_daily_budget"), patch("visionguide.integrations.google_services.requests.post", return_value=_Response(payload)) as request:
                first = service.places_search("pharmacies", location_bias=None, limit=4)
                second = service.places_search("pharmacies", location_bias=None, limit=4)
            self.assertEqual(first, second)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(first[0]["name"], "Example Pharmacy")
            self.assertIn("X-Goog-FieldMask", request.call_args.kwargs["headers"])
            self.assertNotEqual(request.call_args.kwargs["headers"]["X-Goog-FieldMask"], "*")

    def test_air_quality_uses_coordinate_geocode_shortcut(self):
        payload = {"dateTime": "2026-10-28T00:00:00Z", "indexes": [{"code": "uaqi", "displayName": "Universal AQI", "aqi": 42, "category": "Good"}], "pollutants": []}
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make_service(tmp)
            with patch.object(service, "_check_daily_budget"), patch("visionguide.integrations.google_services.requests.post", return_value=_Response(payload)) as request:
                result = service.current_air_quality("22.57,88.36")
            self.assertEqual(result["indexes"][0]["aqi"], 42)
            self.assertIn("location", request.call_args.kwargs["json"])

    def test_maps_dispatcher_is_allowlisted(self):
        fake = Mock()
        fake.current_air_quality.return_value = {"location": "Kolkata", "indexes": []}
        result = execute_google_maps_operation("air_quality", {"location": "Kolkata"}, service=fake)
        self.assertEqual(result["kind"], "air_quality")
        fake.current_air_quality.assert_called_once_with("Kolkata")
        with self.assertRaises(ValueError):
            execute_google_maps_operation("delete_places", {}, service=fake)


class GoogleCloudOAuthTests(unittest.TestCase):
    def test_translation_uses_oauth_session_and_does_not_need_api_key(self):
        session = Mock()
        session.post.return_value = _Response({"data": {"translations": [{"translatedText": "Namaste", "detectedSourceLanguage": "en"}]}})
        with patch.object(cloud, "_guard_daily_usage"), patch.object(cloud, "_authorized_session", return_value=session) as auth_session:
            result = cloud.translate_text("Hello", "hi")
        self.assertEqual(result["translated_text"], "Namaste")
        auth_session.assert_called_once_with("cloud_translation")
        session.close.assert_called_once()

    def test_natural_language_sentiment_uses_language_scope_profile(self):
        session = Mock()
        session.post.return_value = _Response({"documentSentiment": {"score": 0.7, "magnitude": 0.9}, "languageCode": "en"})
        with patch.object(cloud, "_guard_daily_usage"), patch.object(cloud, "_authorized_session", return_value=session) as auth_session:
            result = cloud.analyze_text("This product is great", "sentiment")
        self.assertEqual(result["score"], 0.7)
        self.assertEqual(result["language"], "en")
        auth_session.assert_called_once_with("cloud_language")

    def test_classification_uses_current_v2_endpoint(self):
        self.assertEqual(cloud.LANGUAGE_URLS["classify"], "https://language.googleapis.com/v2/documents:classifyText")

    def test_translation_rejects_empty_text_and_invalid_language(self):
        with self.assertRaises(ValueError):
            cloud.translate_text("", "hi")
        with self.assertRaises(ValueError):
            cloud.translate_text("hello", "123")


class GoogleFeatureRoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = SemanticCommandRouter(enable_local_semantic=False)

    def test_air_quality_routes_without_gemini(self):
        route = self.router.route("Tell me the air quality in Kolkata")
        self.assertEqual(route.action, "google_maps_feature")
        self.assertEqual(route.arguments["operation"], "air_quality")
        self.assertEqual(route.arguments["location"], "Kolkata")

    def test_places_query_extracts_location_bias(self):
        route = self.router.route("Find nearby pharmacies in Kolkata")
        self.assertEqual(route.action, "google_maps_feature")
        self.assertEqual(route.arguments["operation"], "places_search")
        self.assertEqual(route.arguments["query"], "pharmacies")
        self.assertEqual(route.arguments["location_bias"], "Kolkata")

    def test_translation_routes_to_cloud_oauth_feature(self):
        route = self.router.route("Translate hello world to Hindi")
        self.assertEqual(route.action, "google_cloud_feature")
        self.assertEqual(route.arguments["operation"], "translate")
        self.assertEqual(route.arguments["target_language"], "Hindi")

    def test_natural_language_entity_request_is_not_misrouted_as_places_search(self):
        route = self.router.route("Find entities in this text: Ada Lovelace worked in London.")
        self.assertEqual(route.action, "google_cloud_feature")
        self.assertEqual(route.arguments["operation"], "entities")
        self.assertEqual(route.arguments["text"], "Ada Lovelace worked in London.")

    def test_drive_and_meet_commands_route(self):
        drive = self.router.route("Search my Google Drive for project plan")
        meet = self.router.route("Create a Google Meet link")
        self.assertEqual(drive.arguments["operation"], "drive_search")
        self.assertEqual(meet.arguments["operation"], "meet_create")


if __name__ == "__main__":
    unittest.main()
