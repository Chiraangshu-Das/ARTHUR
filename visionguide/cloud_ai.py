from __future__ import annotations

import os

import cv2


class GeminiAssistant:
    """On-demand Gemini image Q&A. Network calls happen only after the user asks."""
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip() or "gemini-flash-latest"

    def available(self) -> bool:
        return bool(self.api_key)

    def ask_about_frame(self, question: str, frame, use_web_search: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your local .env file, restart Arthur, "
                "and click Ask Gemini again."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Gemini support requires the integration dependency. Run `pip install -r requirements-integrations.txt`.") from exc

        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok:
            raise RuntimeError("Could not encode the camera frame for the AI request.")
        client = genai.Client(api_key=self.api_key)
        try:
            contents = [
                "You are Arthur, an assistive visual-description assistant. Be concise and concrete. "
                "Describe only visible evidence; distinguish uncertainty. Never claim calibrated distance or "
                "guaranteed safety from this single image. User question: " + question,
                types.Part.from_bytes(data=encoded.tobytes(), mime_type="image/jpeg"),
            ]
            config = None
            if use_web_search:
                config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
            response = client.models.generate_content(model=self.model, contents=contents, config=config)
            answer = (getattr(response, "text", None) or "").strip()
            if not answer:
                raise RuntimeError("Gemini returned an empty response. Try a shorter question.")
            return answer
        finally:
            client.close()
    def ask_text(self, prompt: str, use_web_search: bool = False) -> str:
        """Answer a user-requested text-only prompt without uploading camera images."""
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your local .env file, restart Arthur, "
                "and retry the text-only AI action."
            )
        prompt = "\n".join(line.rstrip() for line in str(prompt).splitlines()).strip()
        if not prompt:
            raise ValueError("The AI prompt is empty.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Gemini support requires the integration dependency. Run `pip install -r requirements-integrations.txt`.") from exc
        client = genai.Client(api_key=self.api_key)
        try:
            config = None
            if use_web_search:
                config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
            response = client.models.generate_content(
                model=self.model,
                contents=(
                    "You are Arthur, a helpful accessible assistant. Follow the user's task. "
                    "Be clear about uncertainty. Do not claim that you sent emails, changed external "
                    "systems, or performed actions unless a connected tool actually did so.\n\n"
                    + prompt
                ),
                config=config,
            )
            answer = (getattr(response, "text", None) or "").strip()
            if not answer:
                raise RuntimeError("Gemini returned an empty response. Try a shorter prompt.")
            return answer
        finally:
            client.close()

