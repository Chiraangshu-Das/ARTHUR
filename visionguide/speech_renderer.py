from __future__ import annotations

import re


_LATEX_COMMANDS = {
    r"\\neq": " not equal to ",
    r"\\ne": " not equal to ",
    r"\\leq": " less than or equal to ",
    r"\\le": " less than or equal to ",
    r"\\geq": " greater than or equal to ",
    r"\\ge": " greater than or equal to ",
    r"\\approx": " approximately ",
    r"\\times": " times ",
    r"\\cdot": " times ",
    r"\\pm": " plus or minus ",
    r"\\infty": " infinity ",
    r"\\pi": " pi ",
    r"\\rightarrow": " approaches ",
    r"\\to": " to ",
    r"\\in": " in ",
    r"\\sum": " the sum of ",
    r"\\int": " the integral of ",
    r"\\partial": " partial ",
    r"\\nabla": " gradient ",
    r"\\sqrt": " square root of ",
    r"\\sin": " sine of ",
    r"\\cos": " cosine of ",
    r"\\tan": " tangent of ",
    r"\\log": " log of ",
    r"\\ln": " natural log of ",
    r"\\lim": " the limit of ",
    r"\\max": " the maximum of ",
    r"\\min": " the minimum of ",
    r"\\alpha": " alpha ",
    r"\\beta": " beta ",
    r"\\gamma": " gamma ",
    r"\\theta": " theta ",
    r"\\lambda": " lambda ",
    r"\\mu": " mu ",
    r"\\sigma": " sigma ",
    r"\\omega": " omega ",
    r"\\,": " ",
    r"\\;": " ",
    r"\\!": "",
    r"\\quad": " ",
    r"\\qquad": " ",
    r"\\left": "",
    r"\\right": "",
    r"\\displaystyle": "",
    r"\\text": "",
    r"\\mathrm": "",
    r"\\mathbf": "",
    r"\\cdots": " and so on ",
    r"\\ldots": " and so on ",
}


def _read_group(source: str, start: int) -> tuple[str, int] | None:
    """Read a balanced {...} group beginning at start."""
    if start >= len(source) or source[start] != "{":
        return None
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index], index + 1
    return None


def _replace_fraction_and_roots(source: str) -> str:
    """Convert common nested LaTeX fractions and roots without a LaTeX dependency."""
    output = source
    for _ in range(12):
        previous = output
        index = 0
        chunks: list[str] = []
        while index < len(output):
            if output.startswith(r"\frac", index):
                numerator = _read_group(output, index + 5)
                if numerator:
                    denominator = _read_group(output, numerator[1])
                    if denominator:
                        top = _render_latex(numerator[0])
                        bottom = _render_latex(denominator[0])
                        chunks.append(f" {top} divided by {bottom} ")
                        index = denominator[1]
                        continue
            if output.startswith(r"\sqrt", index):
                group = _read_group(output, index + 5)
                if group:
                    chunks.append(f" square root of {_render_latex(group[0])} ")
                    index = group[1]
                    continue
            chunks.append(output[index])
            index += 1
        output = "".join(chunks)
        if output == previous:
            break
    return output


def _render_superscripts(source: str) -> str:
    # Braced exponent: x^{k+1} -> x to the power k plus one.
    source = re.sub(
        r"\^\{([^{}]+)\}",
        lambda match: " to the power " + _render_latex(match.group(1)),
        source,
    )
    # Single-character exponent: x^2 -> x to the power 2.
    source = re.sub(r"\^([A-Za-z0-9])", r" to the power \1", source)
    source = re.sub(r"_\{([^{}]+)\}", lambda m: " subscript " + _render_latex(m.group(1)), source)
    source = re.sub(r"_([A-Za-z0-9])", r" subscript \1", source)
    return source


def _render_latex(source: str) -> str:
    text = str(source or "")
    text = _replace_fraction_and_roots(text)
    text = _render_superscripts(text)
    # Longer command names must be replaced first (for example, \int before \in).
    for pattern, replacement in sorted(_LATEX_COMMANDS.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(pattern, replacement, text)
    text = text.replace(r"\neq", " not equal to ")
    text = text.replace(r"\{", " ").replace(r"\}", " ")
    text = text.replace("{", " ").replace("}", " ")
    text = text.replace("\\", " ")
    text = text.replace("&", " and ")
    text = re.sub(r"(?<![<>=])=(?![=>])", " equals ", text)
    text = re.sub(r"\+\s*C\b", " plus a constant", text)
    text = re.sub(r"\s*\+\s*", " plus ", text)
    text = re.sub(r"−", " minus ", text)
    text = re.sub(r"(?<![A-Za-z])-(?=\d)|(?<=[A-Za-z0-9})])\s*-\s*(?=\d)", " minus ", text)
    text = re.sub(r"\s*/\s*", " divided by ", text)
    text = re.sub(r"\bd([a-zA-Z])\b", r" d \1", text)
    text = re.sub(r"\bd\s+([a-z])(?=\s*(?:equals|plus|minus|divided by|[,.;]|$))", r" with respect to \1", text, flags=re.I)
    return text


def _strip_markdown(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"```[\w+-]*\s*[\r\n]+[\s\S]*?```", " Code is shown in the output panel. ", value)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\((?:https?://)?[^)]+\)", r"\1", value)
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.M)
    value = re.sub(r"^\s*>\s?", "", value, flags=re.M)

    def finish_list_item(match: re.Match[str]) -> str:
        item = match.group(1).strip()
        if item and item[-1] not in ".!?;:":
            item += "."
        return item

    value = re.sub(r"(?m)^\s*[-*+]\s+(.*)$", finish_list_item, value)
    value = re.sub(r"(?m)^\s*\d+[.)]\s+(.*)$", finish_list_item, value)
    value = re.sub(r"\n[ \t]*\n+", ". ", value)
    value = value.replace("**", "").replace("__", "")
    value = value.replace("~~", "").replace("*", "").replace("_", " ")
    return value


def render_for_speech(value: object) -> str:
    """Turn assistant Markdown/LaTeX into plain, pronounceable speech text.

    The original response must be retained separately for the visual output panel.
    This renderer is deliberately conservative: it handles common educational
    notation but does not claim to be a symbolic mathematics engine.
    """
    text = _strip_markdown(str(value or ""))
    text = text.replace(r"\[", " ").replace(r"\]", " ")
    text = text.replace(r"\(", " ").replace(r"\)", " ")
    text = text.replace("$$", " ").replace("$", " ")
    text = re.sub(r"\\begin\{(?:aligned|align|equation|array)\*?\}", " ", text)
    text = re.sub(r"\\end\{(?:aligned|align|equation|array)\*?\}", " ", text)
    text = text.replace(r"\\", ". ")
    text = _render_latex(text)

    replacements = {
        "≤": " less than or equal to ",
        "≥": " greater than or equal to ",
        "≠": " not equal to ",
        "≈": " approximately ",
        "∞": " infinity ",
        "∫": " the integral of ",
        "∑": " the sum of ",
        "√": " square root of ",
        "×": " times ",
        "÷": " divided by ",
        "→": " gives ",
        "π": " pi ",
        "−": " minus ",
        "²": " squared ",
        "³": " cubed ",
    }
    for symbol, spoken in replacements.items():
        text = text.replace(symbol, spoken)

    # Remove leftover TeX command names and formatting punctuation, while keeping
    # ordinary sentence punctuation that helps the TTS engine pause naturally.
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    text = text.replace("\\", " ")
    text = re.sub(r"[{}\[\]()]+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"([.!?])\s*([.!?])+", r"\1", text)
    return text


def split_speech_segments(text: str, max_chars: int = 420) -> list[str]:
    """Split long speech at sentence boundaries, with a safe length fallback."""
    value = " ".join(str(text or "").split()).strip()
    if not value:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", value)
    result: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            result.append(sentence)
            continue
        parts = re.split(r"(?<=[,;:])\s+", sentence)
        current = ""
        for part in parts:
            candidate = f"{current} {part}".strip()
            if current and len(candidate) > max_chars:
                result.append(current)
                current = part
            else:
                current = candidate
        if current:
            result.append(current)
    return [item for item in result if item]
