import sys
import types
import unittest
from unittest.mock import patch

from visionguide.cloud_ai import GroqAssistant
from visionguide.semantic_router import SemanticCommandRouter


class GroqProviderTests(unittest.TestCase):
    def _fake_groq_module(self, response, captured):
        class FakeClient:
            def __init__(self, api_key):
                captured["api_key"] = api_key
                self.chat = types.SimpleNamespace(
                    completions=types.SimpleNamespace(create=lambda **kwargs: captured.setdefault("request", kwargs) or response)
                )
            def close(self):
                captured["closed"] = True
        # Ensure create returns the response while retaining the request.
        class BetterFakeClient(FakeClient):
            def __init__(self, api_key):
                captured["api_key"] = api_key
                def create(**kwargs):
                    captured["request"] = kwargs
                    return response
                self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
        module = types.ModuleType("groq")
        module.Groq = BetterFakeClient
        return module

    def test_text_generation_calls_configured_groq_model(self):
        captured = {}
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="Hello from Groq."))])
        module = self._fake_groq_module(response, captured)
        assistant = GroqAssistant()
        assistant.api_key = "test-key"
        assistant.model = "openai/gpt-oss-120b"
        with patch.dict(sys.modules, {"groq": module}):
            answer = assistant.ask_text("Say hello")
        self.assertEqual(answer, "Hello from Groq.")
        self.assertEqual(captured["api_key"], "test-key")
        self.assertEqual(captured["request"]["model"], "openai/gpt-oss-120b")
        self.assertTrue(captured["closed"])

    def test_web_search_uses_groq_browser_search_tool(self):
        captured = {}
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="Found current sources."))])
        module = self._fake_groq_module(response, captured)
        assistant = GroqAssistant()
        assistant.api_key = "test-key"
        assistant.search_model = "openai/gpt-oss-120b"
        with patch.dict(sys.modules, {"groq": module}):
            answer = assistant.ask_text("What changed recently?", use_web_search=True)
        self.assertEqual(answer, "Found current sources.")
        self.assertEqual(captured["request"]["tools"], [{"type": "browser_search"}])
        self.assertEqual(captured["request"]["tool_choice"], "required")

    def test_router_uses_groq_function_tool_calls(self):
        captured = {}
        function = types.SimpleNamespace(name="general_query", arguments='{"prompt":"Explain recursion"}')
        tool_call = types.SimpleNamespace(function=function)
        message = types.SimpleNamespace(tool_calls=[tool_call])
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])
        module = self._fake_groq_module(response, captured)
        fake_assistant = types.SimpleNamespace(api_key="test-key", model="openai/gpt-oss-120b", available=lambda: True)
        router = SemanticCommandRouter(fake_assistant, enable_local_semantic=False)
        with patch.dict(sys.modules, {"groq": module}):
            result = router.route("Please explain recursion to me")
        self.assertEqual(result.action, "general_query")
        self.assertEqual(result.arguments["prompt"], "Explain recursion")
        self.assertEqual(result.source, "groq-function-calling")
        self.assertLessEqual(len(captured["request"]["tools"]), 20)


if __name__ == "__main__":
    unittest.main()
