from __future__ import annotations

import os
import re
from pathlib import Path

import cv2
import numpy as np


def _order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).reshape(-1)
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]
    return rect


def _perspective_correct(image):
    height, width = image.shape[:2]
    scale = min(1.0, 1000 / max(height, width))
    small = cv2.resize(image, (int(width * scale), int(height * scale))) if scale < 1 else image.copy()
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if len(small.shape) == 3 else small
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[-2]
    candidates = sorted(contours, key=cv2.contourArea, reverse=True)[:8]
    page = None
    for contour in candidates:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and cv2.contourArea(approx) > small.shape[0] * small.shape[1] * 0.12:
            page = approx.reshape(4, 2).astype("float32")
            break
    if page is None:
        return image
    ordered = _order_points(page)
    tl, tr, br, bl = ordered
    out_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    out_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if out_w < 50 or out_h < 50:
        return image
    target = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype="float32")
    transform = cv2.getPerspectiveTransform(ordered, target)
    corrected = cv2.warpPerspective(small, transform, (out_w, out_h))
    return corrected


def read_document(image, tesseract_cmd: str | None = None) -> str:
    """Local OCR with contrast normalization and page perspective correction when enabled."""
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("OCR dependency is missing. Run `pip install -r requirements.txt`.") from exc

    cmd = tesseract_cmd or os.getenv("TESSERACT_CMD", "").strip()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    if image is None or getattr(image, "size", 0) == 0:
        raise ValueError("There is no camera frame to scan yet.")
    corrected = _perspective_correct(image) if len(image.shape) == 3 else image
    gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY) if len(corrected.shape) == 3 else corrected
    if gray.shape[1] < 1200:
        factor = min(2.0, 1200 / max(1, gray.shape[1]))
        gray = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 7, 45, 45)
    threshold = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, 31, 11)
    try:
        return pytesseract.image_to_string(threshold, config="--oem 3 --psm 6").strip()
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR engine is not installed or not on PATH. Install the Tesseract application; "
            "pytesseract alone is only a Python wrapper. See README.md."
        ) from exc


def find_word(text: str, query: str) -> list[tuple[int, str]]:
    needle = query.strip().casefold()
    if not needle:
        return []
    return [(idx, line.strip()) for idx, line in enumerate(text.splitlines(), 1)
            if needle in line.casefold()]


def save_document(text: str, data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
    path = data_dir / f"document-{stamp}.txt"
    path.write_text(text, encoding="utf-8")
    return path
