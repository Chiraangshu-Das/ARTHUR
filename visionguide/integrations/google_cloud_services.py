"""On-demand clients for Google Cloud Translation and Natural Language APIs.

These APIs use dedicated least-privilege OAuth scope profiles, separate from Gemini's
API key and the Maps Platform key. Text is not cached or persisted locally.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
LANGUAGE_URLS = {
    "sentiment": "https://language.googleapis.com/v2/documents:analyzeSentiment",
    "entities": "https://language.googleapis.com/v2/documents:analyzeEntities",
    "syntax": "https://language.googleapis.com/v2/documents:analyzeSyntax",
    # Classification is currently exposed on the v1beta2 REST surface.
    "classify": "https://language.googleapis.com/v2/documents:classifyText",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _guard_daily_usage(service: str, env_name: str, default_limit: int) -> None:
    raw = os.getenv(env_name, str(default_limit)).strip()
    try:
        limit = max(0, min(int(raw), 100_000))
    except ValueError:
        limit = default_limit
    if limit == 0:
        raise RuntimeError(f"Google {service} requests are disabled by {env_name}=0.")
    db_path = _project_root() / "data" / "cache" / "google_services.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    with closing(sqlite3.connect(db_path, timeout=5)) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS usage (service TEXT NOT NULL, utc_date TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(service, utc_date))")
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT count FROM usage WHERE service=? AND utc_date=?", (service, today)).fetchone()
        used = int(row[0]) if row else 0
        if used >= limit:
            connection.rollback()
            raise RuntimeError(f"The local daily cap for Google {service} requests ({limit}/UTC day) has been reached. Review current Google Cloud quotas and billing before changing {env_name}.")
        connection.execute("INSERT INTO usage(service, utc_date, count) VALUES (?,?,1) ON CONFLICT(service,utc_date) DO UPDATE SET count=count+1", (service, today))
        connection.commit()


def _authorized_session(profile: str):
    try:
        from google.auth.transport.requests import AuthorizedSession
        from visionguide.integrations.google_workspace import _credentials
    except ImportError as exc:
        raise RuntimeError("Google Cloud Translation/Natural Language OAuth needs google-auth and google-auth-oauthlib; install requirements-integrations.txt.") from exc
    return AuthorizedSession(_credentials(profile))


def _clean_text(text: str, maximum: int = 20000) -> str:
    text = str(text).strip()
    if not text:
        raise ValueError("Text must not be empty.")
    if len(text) > maximum:
        raise ValueError(f"Text exceeds the {maximum:,}-character request limit.")
    return text


def translate_text(text: str, target_language: str, source_language: str = "") -> dict[str, str]:
    """Translate explicit user-provided text; does not store the input or result locally."""
    text = _clean_text(text, 20000)
    target = str(target_language).strip().lower()
    source = str(source_language).strip().lower()
    if not target or len(target) > 20 or not target.replace("-", "").isalpha():
        raise ValueError("Provide a valid target language code such as en, hi, or bn.")
    if source and (len(source) > 20 or not source.replace("-", "").isalpha()):
        raise ValueError("Provide a valid source language code or leave it empty for auto-detection.")
    _guard_daily_usage("Translation", "VISIONGUIDE_GOOGLE_DAILY_TRANSLATION_CAP", 30)
    payload: dict[str, Any] = {"q": text, "target": target, "format": "text"}
    if source:
        payload["source"] = source
    session = _authorized_session("cloud_translation")
    try:
        response = session.post(TRANSLATE_URL, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        detail = f" Response: {exc.response.text[:400]}" if getattr(exc, "response", None) is not None else ""
        raise RuntimeError(f"Google Cloud Translation request failed: {exc}.{detail}") from exc
    finally:
        session.close()
    translations = data.get("data", {}).get("translations", []) or []
    if not translations:
        raise RuntimeError("Google Cloud Translation returned no translated text.")
    row = translations[0]
    return {"translated_text": str(row.get("translatedText", "")),
            "detected_source_language": str(row.get("detectedSourceLanguage", source)),
            "target_language": target}


def analyze_text(text: str, operation: str = "sentiment", language: str = "") -> dict[str, Any]:
    """Analyze sentiment/entities/syntax/categories for explicitly submitted text."""
    text = _clean_text(text, 20000)
    operation = str(operation).strip().casefold()
    if operation not in LANGUAGE_URLS:
        raise ValueError("Natural Language operation must be sentiment, entities, syntax, or classify.")
    if operation == "classify" and len(text) < 20:
        raise ValueError("Text classification generally requires at least 20 characters.")
    document: dict[str, str] = {"type": "PLAIN_TEXT", "content": text}
    if language:
        language = str(language).strip().lower()
        if len(language) > 20 or not language.replace("-", "").isalpha():
            raise ValueError("Provide a valid language code or leave it empty for auto-detection.")
        document["language"] = language
    _guard_daily_usage("Natural Language", "VISIONGUIDE_GOOGLE_DAILY_LANGUAGE_CAP", 30)
    body = {"document": document, "encodingType": "UTF8"}
    session = _authorized_session("cloud_language")
    try:
        response = session.post(LANGUAGE_URLS[operation], json=body, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        detail = f" Response: {exc.response.text[:400]}" if getattr(exc, "response", None) is not None else ""
        raise RuntimeError(f"Google Cloud Natural Language request failed: {exc}.{detail}") from exc
    finally:
        session.close()
    # Return provider fields without repeating the submitted original text.
    if operation == "sentiment":
        sentiment = data.get("documentSentiment", {}) or {}
        return {"operation": operation, "score": sentiment.get("score"), "magnitude": sentiment.get("magnitude"),
                "language": data.get("languageCode", language)}
    if operation == "entities":
        return {"operation": operation, "entities": [{"name": e.get("name", ""), "type": e.get("type", ""),
                "salience": e.get("salience", 0), "metadata": e.get("metadata", {})}
                for e in (data.get("entities", []) or [])[:50]], "language": data.get("languageCode", language)}
    if operation == "syntax":
        tokens = []
        for token in (data.get("tokens", []) or [])[:200]:
            tokens.append({"text": token.get("text", {}).get("content", ""),
                           "part_of_speech": token.get("partOfSpeech", {}).get("tag", ""),
                           "lemma": token.get("lemma", "")})
        return {"operation": operation, "tokens": tokens, "language": data.get("languageCode", language)}
    return {"operation": operation, "categories": [{"name": c.get("name", ""), "confidence": c.get("confidence", 0)}
            for c in (data.get("categories", []) or [])[:20]], "language": data.get("languageCode", language)}


def execute_google_cloud_operation(operation: str, args: dict[str, Any]) -> dict[str, Any]:
    operation = str(operation).strip().casefold()
    if operation == "translate":
        return {"kind": operation, **translate_text(str(args.get("text", "")), str(args.get("target_language", "")), str(args.get("source_language", "")))}
    if operation in {"sentiment", "entities", "syntax", "classify"}:
        return {"kind": operation, **analyze_text(str(args.get("text", "")), operation, str(args.get("language", "")))}
    raise ValueError(f"Unsupported Google Cloud operation: {operation!r}.")
