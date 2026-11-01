from __future__ import annotations

import time
from pathlib import Path

import cv2


class AirKeyboard:
    """On-screen air keyboard. Input is returned to the Arthur UI, not OS-wide."""
    ROWS = [
        list("QWERTYUIOP"),
        list("ASDFGHJKL"),
        list("ZXCVBNM"),
        ["SPACE", "BACK", "CLEAR", "ENTER"],
    ]

    def __init__(self, model_path: Path):
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError("Air keyboard requires MediaPipe. Run `pip install -r requirements-integrations.txt`.") from exc
        if not model_path.is_file():
            raise FileNotFoundError(f"Hand model missing: {model_path}. Run `python tools/download_hand_model.py`.")
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        self.mp = mp
        self.vision = vision
        self.landmarker = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self.last_timestamp_ms = 0
        self.pinching = False
        self.last_key_time = 0.0
        self.last_key: str | None = None
        self.pointer: tuple[float, float] | None = None
        self.status = "Air keyboard active — move index finger and pinch to select"

    def process(self, frame) -> str | None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        timestamp = max(int(time.monotonic() * 1000), self.last_timestamp_ms + 1)
        self.last_timestamp_ms = timestamp
        result = self.landmarker.detect_for_video(image, timestamp)
        if not result.hand_landmarks:
            self.pointer = None
            self.pinching = False
            self.status = "Air keyboard active — show one hand"
            return None
        landmarks = result.hand_landmarks[0]
        index = landmarks[8]
        thumb = landmarks[4]
        self.pointer = (max(0.0, min(1.0, index.x)), max(0.0, min(1.0, index.y)))
        pinch_distance = ((index.x - thumb.x) ** 2 + (index.y - thumb.y) ** 2) ** 0.5
        is_pinching = pinch_distance < 0.045
        emitted = None
        now = time.monotonic()
        if is_pinching and not self.pinching and now - self.last_key_time >= 0.35:
            key = self._key_at(self.pointer[0], self.pointer[1], frame.shape[1], frame.shape[0])
            if key:
                emitted = key
                self.last_key = key
                self.last_key_time = now
                self.status = f"Selected {key}"
        self.pinching = is_pinching
        return emitted

    def _layout(self, width: int, height: int):
        x_margin = int(width * 0.04)
        y_top = int(height * 0.58)
        y_bottom = int(height * 0.96)
        row_height = (y_bottom - y_top) / 4
        layouts = []
        for row_index, row in enumerate(self.ROWS):
            if row_index == 0:
                left, right = x_margin, width - x_margin
            elif row_index == 1:
                left, right = int(width * 0.085), int(width * 0.915)
            elif row_index == 2:
                left, right = int(width * 0.15), int(width * 0.85)
            else:
                left, right = int(width * 0.04), int(width * 0.96)
            key_width = (right - left) / len(row)
            y1 = int(y_top + row_index * row_height)
            y2 = int(y_top + (row_index + 1) * row_height)
            for i, key in enumerate(row):
                x1 = int(left + i * key_width)
                x2 = int(left + (i + 1) * key_width)
                layouts.append((key, x1, y1, x2, y2))
        return layouts

    def _key_at(self, nx: float, ny: float, width: int, height: int) -> str | None:
        x, y = int(nx * width), int(ny * height)
        for key, x1, y1, x2, y2 in self._layout(width, height):
            if x1 <= x <= x2 and y1 <= y <= y2:
                if key == "SPACE": return " "
                if key == "BACK": return "\b"
                if key == "CLEAR": return "\x04"
                if key == "ENTER": return "\n"
                return key.lower()
        return None

    def draw(self, mirrored_frame):
        output = mirrored_frame.copy()
        height, width = output.shape[:2]
        for key, x1, y1, x2, y2 in self._layout(width, height):
            color = (54, 92, 108)
            if self.pointer:
                px, py = int(self.pointer[0] * width), int(self.pointer[1] * height)
                if x1 <= px <= x2 and y1 <= py <= y2:
                    color = (70, 180, 143)
            cv2.rectangle(output, (x1, y1), (x2, y2), color, -1)
            cv2.rectangle(output, (x1, y1), (x2, y2), (230, 245, 245), 1)
            label = "SPACE" if key == "SPACE" else ("BKSP" if key == "BACK" else key)
            size = 0.48 if len(label) <= 2 else 0.40
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, size, 1)
            cv2.putText(output, label, (x1 + max(2, (x2-x1-tw)//2), y1 + max(15, (y2-y1+th)//2)),
                        cv2.FONT_HERSHEY_SIMPLEX, size, (245, 250, 250), 1, cv2.LINE_AA)
        cv2.putText(output, "AIR KEYBOARD — pinch thumb + index to select | disable via app button",
                    (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
        return output

    def close(self):
        self.landmarker.close()
