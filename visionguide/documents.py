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
    """Run local OCR against several page-friendly variants and keep the best-confidence result.

    OCR remains fully local. The multi-pass path is intended for ordinary printed pages;
    it cannot recover detail that was never captured by a low-resolution or out-of-focus camera.
    """
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("OCR dependency is missing. Run `pip install -r requirements.txt`.") from exc

    cmd = tesseract_cmd or os.getenv("TESSERACT_CMD", "").strip()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    if image is None or getattr(image, "size", 0) == 0:
        raise ValueError("There is no camera frame to scan yet.")

    corrected = _perspective_correct(image) if len(image.shape) == 3 else image.copy()
    gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY) if len(corrected.shape) == 3 else corrected.copy()
    # Keep detail while bringing small print into a useful OCR range.
    scale = min(2.5, 1800 / max(1, gray.shape[1])) if gray.shape[1] < 1800 else 1.0
    if scale > 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, h=8, templateWindowSize=7, searchWindowSize=21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    adaptive = cv2.adaptiveThreshold(
        clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 11
    )
    _threshold, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    candidates = (("contrast", clahe, 6), ("adaptive", adaptive, 6), ("otsu", otsu, 11))
    best_text = ""
    best_score = float("-inf")
    try:
        output_dict = pytesseract.Output.DICT
        for _name, variant, psm in candidates:
            data = pytesseract.image_to_data(
                variant,
                config=f"--oem 3 --psm {psm}",
                output_type=output_dict,
            )
            grouped: dict[tuple[int, int, int], list[str]] = {}
            confidences: list[float] = []
            words = data.get("text", [])
            confs = data.get("conf", [])
            blocks = data.get("block_num", [])
            paragraphs = data.get("par_num", [])
            lines = data.get("line_num", [])
            for index, word in enumerate(words):
                token = str(word).strip()
                if not token:
                    continue
                try:
                    confidence = float(confs[index])
                except (ValueError, IndexError, TypeError):
                    confidence = -1.0
                if confidence >= 0:
                    confidences.append(confidence)
                if confidence >= 0 and index < len(blocks) and index < len(paragraphs) and index < len(lines):
                    line_key = (int(blocks[index]), int(paragraphs[index]), int(lines[index]))
                    grouped.setdefault(line_key, []).append(token)
            text = "\n".join(" ".join(parts) for parts in grouped.values()).strip()
            if text:
                mean_confidence = sum(confidences) / max(1, len(confidences))
                word_count = sum(len(line.split()) for line in text.splitlines())
                line_count = len(text.splitlines())
                score = mean_confidence + min(word_count, 40) * 0.20 + min(line_count, 12) * 0.35
                if score > best_score:
                    best_score, best_text = score, text

        # Compatibility fallback for older Tesseract bindings or empty layout data.
        if not best_text:
            best_text = pytesseract.image_to_string(clahe, config="--oem 3 --psm 6").strip()
        return best_text
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
