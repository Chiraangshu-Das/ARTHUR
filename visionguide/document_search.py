from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".h",
    ".cpp", ".hpp", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".csv", ".log",
    ".sql", ".xml", ".ini", ".bat", ".ps1", ".sh", ".tex",
}


@dataclass(frozen=True)
class DocumentMatch:
    location: str
    excerpt: str


def extract_supported_text(path: Path) -> list[tuple[str, str]]:
    """Return (location, text) units; PDF units are pages, text files are lines, DOCX is paragraphs."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {path}")
    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        content = path.read_text(encoding="utf-8", errors="replace")
        return [(f"line {i}", line) for i, line in enumerate(content.splitlines(), 1)]
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF text search requires pypdf. Run `pip install -r requirements.txt`.") from exc
        reader = PdfReader(str(path))
        return [(f"page {i}", page.extract_text() or "") for i, page in enumerate(reader.pages, 1)]
    if ext == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX text search requires python-docx. Run `pip install -r requirements.txt`.") from exc
        doc = Document(str(path))
        units = [(f"paragraph {i}", p.text) for i, p in enumerate(doc.paragraphs, 1) if p.text]
        for t_index, table in enumerate(doc.tables, 1):
            for r_index, row in enumerate(table.rows, 1):
                units.append((f"table {t_index}, row {r_index}", " | ".join(c.text for c in row.cells)))
        return units
    raise ValueError(f"Unsupported document type {ext!r}. Supported: text/code files, PDF, and DOCX.")


def search_document(path: Path, query: str, limit: int = 25) -> list[DocumentMatch]:
    query = str(query).strip()
    if not query:
        raise ValueError("Search term cannot be empty.")
    if limit < 1:
        raise ValueError("Limit must be positive.")
    units = extract_supported_text(path)
    matches: list[DocumentMatch] = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for location, text in units:
        if pattern.search(text):
            compact = " ".join(text.split())
            matches.append(DocumentMatch(location, compact[:360]))
            if len(matches) >= limit:
                break
    return matches
