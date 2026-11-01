from __future__ import annotations

import time
from pathlib import Path

import cv2


HAND_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


class GestureMouse:
    """Air-mouse: index fingertip moves pointer; pinch makes a left click.

    It is inactive until explicitly enabled. The index fingertip controls the pointer;
    thumb-index pinch performs a click. Place the fingertip in the rightmost screen zone
    and slide vertically to scroll. A two-point wizard calibrates the usable pointer bounds.
    MediaPipe and PyAutoGUI are required.
    """
    def __init__(self, model_path: Path):
        try:
            import pyautogui
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError as exc:
            raise RuntimeError("Air mouse needs mediapipe and pyautogui. Install requirements-integrations.txt.") from exc
        if not model_path.is_file():
            raise FileNotFoundError(
                f"Hand model not found: {model_path}. Run `python tools/download_hand_model.py` first."
            )
        self.pyautogui = pyautogui
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
        self.last_click_at = 0.0
        self.pinching = False
        self.previous_index_y: float | None = None
        self.previous_index_x: float | None = None
        self.previous_motion_at: float | None = None
        self.last_scroll_at = 0.0
        self.last_tab_swipe_at = 0.0
        self.swipe_anchor_x: float | None = None
        self.swipe_anchor_at: float | None = None
        self.scroll_zone_ratio = 0.82
        self.scroll_threshold = 0.018
        self.tab_swipe_threshold = 0.24
        self.tab_swipe_window = 0.55
        self.tab_swipe_cooldown = 0.9
        self.smoothing = 0.32
        self._smoothed_x: float | None = None
        self._smoothed_y: float | None = None
        self.calibration_state = "idle"
        self.calibration_bounds: tuple[float, float, float, float] | None = None
        self._calibration_started = 0.0
        self._calibration_samples: list[tuple[float, float]] = []
        self._calibration_points: list[tuple[float, float]] = []
        self.screen_width, self.screen_height = pyautogui.size()
        pyautogui.FAILSAFE = True

    def begin_calibration(self, point: str) -> None:
        if point not in {"upper_left", "lower_right"}:
            raise ValueError("Calibration point must be upper_left or lower_right.")
        if point == "upper_left":
            self._calibration_points = []
        self._calibration_samples = []
        self._calibration_started = time.monotonic()
        self.calibration_state = "capture_" + point

    @staticmethod
    def _map_coordinate(value: float, low: float, high: float) -> float:
        if high <= low:
            return min(1.0, max(0.0, value))
        return min(1.0, max(0.0, (value - low) / (high - low)))

    def _capture_calibration(self, x: float, y: float, now: float) -> str:
        self._calibration_samples.append((x, y))
        if now - self._calibration_started < 1.25:
            return "Calibrating pointer bounds — hold the index finger still"
        if len(self._calibration_samples) < 8:
            if now - self._calibration_started > 6.0:
                self.calibration_state = "failed"
                return "Gesture calibration failed — keep one hand clearly visible and try again"
            return "Calibrating pointer bounds — keep the hand visible"
        xs = sorted(point[0] for point in self._calibration_samples)
        ys = sorted(point[1] for point in self._calibration_samples)
        middle = len(xs) // 2
        point = (xs[middle], ys[middle])
        if self.calibration_state == "capture_upper_left":
            self._calibration_points = [point]
            self.calibration_state = "await_lower_right"
            return "Calibration point 1 saved — follow the on-screen step 2 prompt"
        self._calibration_points.append(point)
        first, second = self._calibration_points[-2:]
        x_low, x_high = sorted((first[0], second[0]))
        y_low, y_high = sorted((first[1], second[1]))
        if x_high - x_low < 0.25 or y_high - y_low < 0.25:
            self.calibration_state = "failed"
            return "Gesture calibration failed — use farther-apart upper-left and lower-right points"
        self.calibration_bounds = (x_low, x_high, y_low, y_high)
        self._smoothed_x = self._smoothed_y = None
        self.calibration_state = "complete"
        return "Gesture calibration complete"

    def process(self, frame) -> str:
        rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        timestamp = max(int(time.monotonic() * 1000), self.last_timestamp_ms + 1)
        self.last_timestamp_ms = timestamp
        result = self.landmarker.detect_for_video(image, timestamp)
        if not result.hand_landmarks:
            self.pinching = False
            self.previous_index_y = None
            self.previous_index_x = None
            self.previous_motion_at = None
            self.swipe_anchor_x = None
            self.swipe_anchor_at = None
            if self.calibration_state.startswith("capture_") and time.monotonic() - self._calibration_started > 6.0:
                self.calibration_state = "failed"
                return "Gesture calibration timed out — keep one hand visible and try again"
            return "Show one hand to control pointer"
        landmarks = result.hand_landmarks[0]
        index_tip = landmarks[8]
        thumb_tip = landmarks[4]
        x = min(1.0, max(0.0, index_tip.x))
        y = min(1.0, max(0.0, index_tip.y))
        now = time.monotonic()
        if self.calibration_state.startswith("capture_"):
            return self._capture_calibration(x, y, now)
        if self.calibration_state == "await_lower_right":
            self.pinching = False
            return "Gesture calibration paused — follow the lower-right calibration prompt"
        pointer_x, pointer_y = x, y
        if self.calibration_bounds:
            x_low, x_high, y_low, y_high = self.calibration_bounds
            pointer_x = self._map_coordinate(x, x_low, x_high)
            pointer_y = self._map_coordinate(y, y_low, y_high)
        if self._smoothed_x is None:
            self._smoothed_x, self._smoothed_y = pointer_x, pointer_y
        else:
            self._smoothed_x += self.smoothing * (pointer_x - self._smoothed_x)
            self._smoothed_y += self.smoothing * (pointer_y - self._smoothed_y)
        target_x = int(self._smoothed_x * (self.screen_width - 1))
        target_y = int(self._smoothed_y * (self.screen_height - 1))
        pinch_distance = ((index_tip.x - thumb_tip.x) ** 2 + (index_tip.y - thumb_tip.y) ** 2) ** 0.5
        is_pinching = pinch_distance < 0.045
        now = time.monotonic()
        last_x, last_y, last_at = self.previous_index_x, self.previous_index_y, self.previous_motion_at

        # A short trajectory window detects swipes across multiple camera frames;
        # per-frame deltas alone miss ordinary hand movements at webcam frame rates.
        if is_pinching or x >= self.scroll_zone_ratio or now - self.last_tab_swipe_at < self.tab_swipe_cooldown:
            self.swipe_anchor_x = None
            self.swipe_anchor_at = None
        else:
            if self.swipe_anchor_x is None or self.swipe_anchor_at is None or now - self.swipe_anchor_at > self.tab_swipe_window:
                self.swipe_anchor_x = x
                self.swipe_anchor_at = now
            else:
                delta_x = x - self.swipe_anchor_x
                if abs(delta_x) >= self.tab_swipe_threshold:
                    # MediaPipe receives a horizontally mirrored frame so pointer movement
                    # feels natural. That reverses the sign of a physical left/right swipe.
                    if delta_x > 0:
                        self.pyautogui.hotkey("ctrl", "shift", "tab")
                        message = "Swipe left — switched to previous browser tab"
                    else:
                        self.pyautogui.hotkey("ctrl", "tab")
                        message = "Swipe right — switched to next browser tab"
                    self.last_tab_swipe_at = now
                    self.swipe_anchor_x = None
                    self.swipe_anchor_at = None
                    self.previous_index_x, self.previous_index_y, self.previous_motion_at = x, y, now
                    self.pinching = False
                    return message

        # Rightmost 18% is a dedicated scroll strip. Vertical finger movement scrolls
        # the active window instead of also sending the pointer across the screen.
        if x >= self.scroll_zone_ratio and self.previous_index_y is not None and not is_pinching:
            delta_y = index_tip.y - self.previous_index_y
            if abs(delta_y) >= self.scroll_threshold and now - self.last_scroll_at >= 0.04:
                amount = max(-12, min(12, int(round(-delta_y * 420))))
                if amount == 0:
                    amount = -1 if delta_y > 0 else 1
                self.pyautogui.moveTo(self.screen_width - 12, target_y, duration=0)
                self.pyautogui.scroll(amount)
                self.last_scroll_at = now
                self.previous_index_y = index_tip.y
                self.previous_index_x = index_tip.x
                self.previous_motion_at = now
                self.pinching = False
                return "Air scroll active — slide finger up or down in the right-edge strip"
        else:
            self.pyautogui.moveTo(target_x, target_y, duration=0)

        if is_pinching and not self.pinching and now - self.last_click_at > 0.7:
            self.pyautogui.click()
            self.last_click_at = now
        self.pinching = is_pinching
        self.previous_index_y = index_tip.y
        self.previous_index_x = index_tip.x
        self.previous_motion_at = now
        if is_pinching:
            return "Pinch detected — air-click"
        if x >= self.scroll_zone_ratio:
            return "Air scroll zone — slide finger up or down; pinch to click"
        return "Air mouse active — move index finger; pinch to click; quick left/right swipe changes browser tabs"

    def close(self):
        self.landmarker.close()
