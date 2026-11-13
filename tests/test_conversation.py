from __future__ import annotations

import unittest

from visionguide.conversation import ConversationContext
from visionguide.semantic_router import SemanticCommandRouter
from visionguide.voice_responses import natural_action_response
from visionguide.speech import SpeechOutput


class ConversationContextTests(unittest.TestCase):
    def test_turn_keeps_user_action_and_result_in_memory_context(self):
        context = ConversationContext(max_turns=3)
        turn_id = context.begin_turn("Open YouTube")
        context.set_action(turn_id, "open_website", {"name": "youtube"})
        context.set_result(turn_id, "Opened youtube in the default browser.", success=True)

        rendered = context.render()
        self.assertIn("User: Open YouTube", rendered)
        self.assertIn('"name": "youtube"', rendered)
        self.assertIn("success", rendered)
        self.assertNotIn("Open YouTube", context.render(exclude_turn_id=turn_id))

    def test_context_is_bounded_and_clearable(self):
        context = ConversationContext(max_turns=2)
        context.begin_turn("First")
        context.begin_turn("Second")
        context.begin_turn("Third")
        rendered = context.render()
        self.assertNotIn("First", rendered)
        self.assertIn("Second", rendered)
        self.assertIn("Third", rendered)
        context.clear()
        self.assertEqual(context.render(), "")

    def test_action_arguments_are_compacted(self):
        context = ConversationContext()
        turn_id = context.begin_turn("Search")
        context.set_action(turn_id, "web_search", {"query": "x" * 500, "frame": object(), "count": 2})
        rendered = context.render()
        self.assertIn('"count": 2', rendered)
        self.assertNotIn("object at", rendered)
        self.assertLess(len(rendered), 1000)


class NaturalVoiceResponseTests(unittest.TestCase):
    def test_open_website_gets_conversational_confirmation(self):
        response = natural_action_response(
            "open_website", {"name": "youtube"}, "Opened youtube in the default browser."
        )
        self.assertEqual(response, "YouTube is open. What would you like to do next?")

    def test_failed_result_is_not_rewritten_as_success(self):
        response = natural_action_response(
            "open_app", {"name": "calculator"}, "Action failed: application not found."
        )
        self.assertEqual(response, "Action failed: application not found.")


class SpeechRateMappingTests(unittest.TestCase):
    def test_pytsx3_style_rate_maps_to_sapi_range(self):
        self.assertEqual(SpeechOutput._sapi_rate(175), 0)
        self.assertEqual(SpeechOutput._sapi_rate(165), 0)  # rounded to SAPI's neutral rate
        self.assertEqual(SpeechOutput._sapi_rate(999), 10)
        self.assertEqual(SpeechOutput._sapi_rate(0), -9)


class ContextAwareRouterTests(unittest.TestCase):
    class FakeGemini:
        api_key = "test-key"

        def available(self):
            return True

    def test_context_is_forwarded_to_gemini_for_elliptical_followup(self):
        router = SemanticCommandRouter(self.FakeGemini(), enable_local_semantic=False)
        expected = object()

        def fake_route(text, *, conversation_context=""):
            self.assertEqual(text, "open it")
            self.assertEqual(conversation_context, "User: Open YouTube")
            return expected

        router._route_with_gemini = fake_route
        self.assertIs(
            router.route("open it", conversation_context="User: Open YouTube"),
            expected,
        )

    def test_deterministic_route_still_precedes_contextual_model(self):
        router = SemanticCommandRouter(self.FakeGemini(), enable_local_semantic=False)
        router._route_with_gemini = lambda *_args, **_kwargs: self.fail("Gemini should not override a deterministic route")
        routed = router.route("Open YouTube", conversation_context="User: Open Google")
        self.assertEqual(routed.action, "open_website")
        self.assertEqual(routed.arguments["name"], "youtube")


if __name__ == "__main__":
    unittest.main()
