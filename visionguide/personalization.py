from __future__ import annotations

import re


_NAME_PATTERN = re.compile(r"^[\w][\w'’ -]{0,59}$", re.UNICODE)


def normalize_preferred_name(value: object) -> str | None:
    """Return a bounded display name suitable for spoken addressing, or None."""
    name = " ".join(str(value or "").split()).strip()
    if not name or len(name) > 60 or not name[0].isalpha() or not _NAME_PATTERN.fullmatch(name):
        return None
    return name


def personalize_spoken_response(
    text: object,
    preferred_name: object,
    *,
    address_user: bool = True,
    max_prefix_chars: int = 900,
) -> str:
    """Replace direct 'sir' salutations and naturally address the active user.

    The name is supplied at runtime from the currently active enrolled face
    profile. No person's name is embedded in application source code.
    """
    response = str(text or "").strip()
    name = normalize_preferred_name(preferred_name)
    if not response or not name:
        return response

    # Replace only vocative uses such as "Yes, sir?" and "Goodbye, sir.";
    # do not alter titles such as "Sir Isaac Newton" or arbitrary quoted text.
    response = re.sub(
        r"(?i)\bsir\b(?=\s*[,!?;:]|\s*\.|\s*$)",
        lambda _match: name,
        response,
    )

    if not address_user or len(response) > max(100, int(max_prefix_chars)):
        return response

    # A response already addressed to the user must not receive a duplicate name.
    name_at_start = re.compile(rf"(?i)^\s*(?:hello|hi|good morning|good afternoon|good evening)?[,]?\s*{re.escape(name)}\b")
    if name_at_start.search(response):
        return response
    # A leading "Sir [Name]" is an honorific title, not a salutation.
    if re.match(r"^Sir\s+[A-Z]", response):
        return response
    if re.search(rf"(?i)\b{re.escape(name)}\b", response[:160]):
        return response

    # Avoid prepending a salutation to a single detected label or fragment.
    if len(response.split()) < 2:
        return response

    return f"{name}, {response}"
