from __future__ import annotations


_DISPLAY_NAMES = {
    "youtube": "YouTube",
    "google": "Google",
    "github": "GitHub",
    "chatgpt": "ChatGPT",
    "gemini": "Groq",
    "vscode": "Visual Studio Code",
    "wi-fi settings": "Wi-Fi settings",
    "google docs": "Google Docs",
    "google sheets": "Google Sheets",
    "google drive": "Google Drive",
    "file explorer": "File Explorer",
    "task manager": "Task Manager",
}


def _display_name(value: object) -> str:
    key = " ".join(str(value or "").split()).strip().casefold()
    return _DISPLAY_NAMES.get(key, key.title() or "that item")


def natural_action_response(action: str, arguments: dict, verified_result: str) -> str:
    """Create a brief spoken confirmation after an executor reports success.

    The full executor result remains available to the UI. This helper never turns
    an exception or a failed operation into a success message.
    """
    result = " ".join(str(verified_result or "").split()).strip()
    lowered = result.casefold()
    if not result or lowered.startswith(("action failed:", "error:", "failed:", "could not ")):
        return result

    if action == "open_website" and lowered.startswith("opened "):
        name = _display_name(arguments.get("name", "website"))
        return f"{name} is open. What would you like to do next?"

    if action == "open_app" and lowered.startswith(("opened ", "launched ")):
        name = _display_name(arguments.get("name", "application"))
        return f"{name} is ready. What would you like me to do?"

    if action == "open_folder" and lowered.startswith("opened "):
        name = _display_name(arguments.get("folder", "folder"))
        return f"Your {name} folder is open."

    if action == "youtube_search" and lowered.startswith("opened youtube search results"):
        query = str(arguments.get("query", "")).strip()
        return f"I've opened YouTube results for {query}. You can choose a video."

    if action == "web_search" and lowered.startswith("opened web search results"):
        query = str(arguments.get("query", "")).strip()
        return f"I've opened web search results for {query}. You can review them in your browser."

    if action == "open_latest_pdf" and lowered.startswith("opened "):
        return "The latest PDF is open."

    return result
