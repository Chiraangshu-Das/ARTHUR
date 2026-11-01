from __future__ import annotations

import os
import queue
import threading
import time
import hashlib
import re
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

import cv2
from PIL import Image, ImageTk

from visionguide.cloud_ai import GeminiAssistant
from visionguide.action_history import ActionHistory, summarize_recent_actions
from visionguide.system_virtual_keyboard import SystemVirtualKeyboard
from visionguide.depth import DepthWorker
from visionguide.documents import find_word, read_document, save_document
from visionguide.document_search import search_document
from visionguide.desktop_actions import (
    calculate_expression, calculator_calculate, capture_screen, check_internet_connectivity, find_latest_pdf,
    image_file_to_bgr, open_app, open_document, open_folder, open_website, search_web, search_youtube, system_status,
)
from visionguide.engine import VisionWorker
from visionguide.face_memory import FaceMemory
from visionguide.gesture_mouse import GestureMouse
from visionguide.semantic_router import SemanticCommandRouter
from visionguide.integrations.timers import TimerManager
from visionguide.integrations.google_services import GoogleMapsServices
from visionguide.navigation import NavigationSession, NavigationUpdate, WindowsLocationProvider
from visionguide.integrations.system_controls import (
    adjust_brightness, adjust_volume, get_brightness, get_volume, list_wifi_adapters,
    media_playback, set_brightness, set_mute, set_volume, set_wifi,
)
from visionguide.integrations.google_workspace import (
    calendar_create_event, calendar_search, calendar_upcoming, gmail_read_message, gmail_search, gmail_unread,
)
from visionguide.integrations.gui_automation import (
    activate_window, compose_gmail_gui, compose_whatsapp_gui, send_current_whatsapp,
    type_into_window, type_text_to_focused_window, focus_application_target, word_write_document,
)
from visionguide.memory import LocalMemory
from visionguide.perception import Detection, draw_detections, summarize_scene
from visionguide.safety import SafetyEngine
from visionguide.scene_commands import parse_voice_command
from visionguide.speech import SpeechOutput


class ArthurApp:
    BG = "#101820"
    PANEL = "#17232d"
    PANEL_ALT = "#1d2c38"
    TEXT = "#edf3f5"
    MUTED = "#9eb0ba"
    ACCENT = "#4fd1a5"
    WARN = "#f3bd58"

    def __init__(self, worker: VisionWorker, speech: SpeechOutput, project_dir: Path):
        self.worker = worker
        self.speech = speech
        self.project_dir = Path(project_dir)
        self.data_dir = self.project_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "snapshots").mkdir(exist_ok=True)
        (self.data_dir / "documents").mkdir(exist_ok=True)
        self.face_memory = FaceMemory(self.data_dir)
        self.memory = LocalMemory(self.data_dir / "memory.sqlite3")
        self.action_history = ActionHistory(self.data_dir / "action_history.sqlite3")
        self.maps_services = GoogleMapsServices(cache_path=self.data_dir / "cache" / "google_services.sqlite3")
        self.navigation_session: NavigationSession | None = None
        self.last_action_result = ""
        self.last_voice_transcript = ""
        self._dispatch_context: tuple[str, str] | None = None
        self.face_overlay: list[tuple[int, int, int, int, str, float]] = []
        self._last_face_scan_at = 0.0
        self._face_scan_pending = False
        self._face_absence_since = 0.0
        self.active_face_profile: str | None = None
        self._last_greeted_profile: str | None = None
        self._unknown_greeted = False
        self.gemini = GeminiAssistant()
        self.command_router = SemanticCommandRouter(self.gemini)
        self.safety_engine = SafetyEngine()
        self.safety_enabled = False
        self.face_recognition_enabled = False
        self.gesture_mouse: GestureMouse | None = None
        self.gesture_enabled = False
        self.system_virtual_keyboard: SystemVirtualKeyboard | None = None
        self.depth_worker: DepthWorker | None = None
        self.depth_enabled = False
        self.sign_recognizer = None
        self.wake_word_listener = None
        # Master listening is opt-in. Wake-word and conversation capture are both disabled at startup.
        self.wake_word_armed = False
        self.conversation_active = False
        self._conversation_stop = threading.Event()
        self._conversation_command_done = threading.Event()
        self._conversation_command_done.set()
        self._conversation_lock = threading.Lock()
        self._camera_explicitly_enabled = False
        self._camera_task_lock = threading.Lock()
        self.sign_enabled = False
        self.last_sign_spoken = ""
        self.last_sign_spoken_at = 0.0
        self.latest_frame = None
        self.latest_detections: list[Detection] = []
        self.latest_version = -1
        self.latest_ocr = ""
        self.last_safety_version = -1
        self.last_photo_path: Path | None = None
        self._async_messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.timer_manager = TimerManager(lambda timer_id, label: self._async_messages.put(("timer_expired", (timer_id, label))))
        self._closed = False

        self.root = tk.Tk()
        self.root.title("Arthur | AI Assistive Assistant")
        self.root.geometry("1420x940")
        self.root.minsize(1120, 820)
        self.root.configure(bg=self.BG)
        self._configure_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # Privacy-first startup: camera and microphone are both off until explicitly enabled.
        self.status_var.set("Camera off · listening disabled")
        self.root.after(30, self._refresh)
        self.root.after(120, self._drain_async_messages)

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.PANEL, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI Semibold", 21))
        style.configure("Subheader.TLabel", background=self.PANEL, foreground=self.TEXT, font=("Segoe UI Semibold", 11))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(10, 8))
        style.configure("Primary.TButton", background=self.ACCENT, foreground="#0b2019", padding=(10, 9))
        style.map("Primary.TButton", background=[("active", "#77e5c0")])
        style.configure("Quiet.TButton", background=self.PANEL_ALT, foreground=self.TEXT, padding=(10, 8))
        style.map("Quiet.TButton", background=[("active", "#2a3d4b")])
        style.configure("TCheckbutton", background=self.PANEL, foreground=self.TEXT)
        style.configure("Treeview", background=self.PANEL_ALT, fieldbackground=self.PANEL_ALT,
                        foreground=self.TEXT, rowheight=25, borderwidth=0)
        style.configure("Treeview.Heading", background="#253744", foreground=self.TEXT,
                        font=("Segoe UI Semibold", 9), relief="flat")

    def _build_ui(self):
        header = ttk.Frame(self.root, padding=(22, 16, 22, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Arthur", style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="LOCAL ASSISTIVE-AI PROTOTYPE", foreground=self.ACCENT,
                  background=self.BG, font=("Segoe UI Semibold", 9)).pack(side="left", padx=(16, 0), pady=(8, 0))
        self.status_var = tk.StringVar(value="Initializing camera and model…")
        ttk.Label(header, textvariable=self.status_var, foreground=self.MUTED, background=self.BG).pack(side="right", pady=(8, 0))
        self.listening_button = self._button(header, "Listening: OFF", self.toggle_master_listening, primary=True)
        self.listening_button.pack(side="right", padx=(0, 12), pady=(3, 0))

        body = ttk.Frame(self.root, padding=(18, 0, 18, 14))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Panel.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="Live camera", style="Subheader.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.preview = tk.Label(left, text="Waiting for camera…", bg="#071017", fg=self.MUTED,
                                font=("Segoe UI", 12), anchor="center")
        self.preview.grid(row=1, column=0, sticky="nsew")
        self.preview.bind("<Configure>", lambda _event: self.root.after(10, self._draw_preview))
        self.fps_var = tk.StringVar(value="Inference: waiting")
        ttk.Label(left, textvariable=self.fps_var, style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(7, 0))

        quick = ttk.Frame(left, style="Panel.TFrame")
        quick.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        for column in range(3): quick.columnconfigure(column, weight=1)
        self._button(quick, "Describe scene", self.describe_scene, primary=True).grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=3)
        self._button(quick, "Scan / read text", self.scan_document).grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        self._button(quick, "Voice command", self.voice_command).grid(row=0, column=2, sticky="ew", padx=(5, 0), pady=3)

        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        right.rowconfigure(4, weight=2)
        ttk.Label(right, text="Detected objects", style="Subheader.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="Directions refer to the camera image. Range is an approximate monocular model estimate.",
                  style="Muted.TLabel", wraplength=440).grid(row=1, column=0, sticky="ew", pady=(3, 6))
        self.objects = ttk.Treeview(right, columns=("object", "direction", "confidence", "range", "motion", "track"), show="headings", height=7)
        for key, heading, width in [("object", "Object", 82), ("direction", "Image direction", 74),
                                    ("confidence", "Conf.", 48), ("range", "Est. range", 82), ("motion", "Motion", 90), ("track", "ID", 40)]:
            self.objects.heading(key, text=heading)
            self.objects.column(key, width=width, anchor="w" if key == "object" else "center", stretch=True)
        self.objects.grid(row=2, column=0, sticky="nsew")
        ttk.Label(right, text="Response / document text", style="Subheader.TLabel").grid(row=3, column=0, sticky="w", pady=(14, 5))
        self.output = tk.Text(right, bg="#0c151c", fg=self.TEXT, insertbackground=self.TEXT,
                              relief="flat", wrap="word", font=("Segoe UI", 10), padx=10, pady=10)
        self.output.grid(row=4, column=0, sticky="nsew")
        self.output.insert("1.0", "Camera detection is visual-only until you request an action.\n\n"
                           "Use Describe scene to hear a summary, Scan / read text for OCR, or Voice command to record a short command.")
        self.output.configure(state="disabled")

        controls = ttk.Frame(self.root, padding=(18, 0, 18, 8))
        controls.pack(fill="x")
        for c in range(5): controls.columnconfigure(c, weight=1)
        control_items = [
            ("Find word on page", self.lookup_word),
            ("Ask Gemini about view", lambda: self.ask_gemini(use_web_search=False)),
            ("Ask Gemini + web", lambda: self.ask_gemini(use_web_search=True)),
            ("Text AI / email", self.ask_gemini_text),
            ("Save snapshot", self.save_snapshot),
            ("Remember info…", self.remember_info),
            ("Search memory…", self.search_memory),
            ("Delete memory…", self.delete_memory),
            ("Help / controls", self.show_help),
            ("Camera: ON / OFF", self.toggle_camera_manual),
        ]
        for index, (label, callback) in enumerate(control_items):
            row, column = divmod(index, 5)
            padx = (0, 5) if column == 0 else ((5, 0) if column == 4 else 5)
            self._button(controls, label, callback).grid(row=row, column=column, sticky="ew", padx=padx, pady=3)

        promptbar = ttk.Frame(self.root, padding=(18, 0, 18, 8))
        promptbar.pack(fill="x")
        promptbar.columnconfigure(1, weight=1)
        ttk.Label(promptbar, text="Keyboard / visual question:", background=self.BG, foreground=self.TEXT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.virtual_input_var = tk.StringVar(value="")
        ttk.Entry(promptbar, textvariable=self.virtual_input_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self._button(promptbar, "Ask about view + text", self.ask_gemini_with_typed_prompt, primary=True).grid(row=0, column=2, sticky="e")

        advanced = ttk.Frame(self.root, padding=(18, 0, 18, 8))
        advanced.pack(fill="x")
        for c in range(5): advanced.columnconfigure(c, weight=1)
        self._button(advanced, "Enable metric depth", self.toggle_depth).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._button(advanced, "Calibrate range…", self.calibrate_depth).grid(row=0, column=1, sticky="ew", padx=5)
        self._button(advanced, "Air virtual keyboard…", self.toggle_system_virtual_keyboard).grid(row=0, column=2, sticky="ew", padx=5)
        self._button(advanced, "Hand gestures…", self.toggle_air_mouse).grid(row=0, column=3, sticky="ew", padx=5)
        self._button(advanced, "ISL sign mode…", self.toggle_sign_mode).grid(row=0, column=4, sticky="ew", padx=(5, 0))
        self._button(advanced, "Calibrate gestures…", self.calibrate_gestures).grid(row=1, column=3, sticky="ew", padx=5, pady=(5, 0))

        settings = ttk.Frame(self.root, style="Panel.TFrame", padding=(18, 10))
        settings.pack(fill="x", padx=18, pady=(0, 14))
        self.safety_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings, text="Depth-based spoken alerts (off by default)",
                        variable=self.safety_var, command=self.toggle_safety).pack(side="left")
        self.face_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings, text="Recognize enrolled faces (off by default)", variable=self.face_var,
                        command=self.toggle_face_recognition).pack(side="left", padx=(18, 0))
        self._button(settings, "Enroll face…", self.enroll_face).pack(side="right", padx=(6, 0))
        self._button(settings, "Manage face memory…", self.manage_faces).pack(side="right", padx=6)

    def _button(self, parent, text, command, primary=False):
        return ttk.Button(parent, text=text, command=command,
                          style="Primary.TButton" if primary else "Quiet.TButton")

    @staticmethod
    def _parse_voice_confirmation(transcript: str) -> bool | None:
        """Return True/False only for a clear spoken confirmation; otherwise fail closed."""
        text = re.sub(r"[^a-z0-9' ]+", " ", str(transcript).casefold())
        text = " ".join(text.split())
        if re.match(r"^(yes|yeah|yep|correct|confirm|confirmed|approve|approved|go ahead|do it|send it|proceed|okay|ok)(?:\b|$)", text):
            return True
        if re.match(r"^(no|nope|cancel|cancel it|don't|do not|stop|not now|decline)(?:\b|$)", text):
            return False
        return None

    def _ask_yes_no(self, title: str, message: str, parent=None) -> bool:
        """Use spoken confirmation during Arthur conversations; use a dialog otherwise."""
        if not self.conversation_active:
            return messagebox.askyesno(title, message, parent=parent or self.root)
        prompt = f"{title}. {message[:1100]}. Please say yes or no."
        self.speech.say(prompt[:1400])
        self.speech.wait_until_idle(timeout=25.0)
        try:
            from visionguide.voice_commands import record_and_transcribe
            response = record_and_transcribe(duration_seconds=5.0, model_name="base")
        except Exception as exc:
            self._append_output(f"Voice confirmation failed closed: {exc}")
            self.speech.say("I could not confirm that safely, so I cancelled the action.")
            return False
        decision = self._parse_voice_confirmation(response)
        if decision is True:
            self._append_output("Voice confirmation received: yes.")
            return True
        if decision is False:
            self._append_output("Voice confirmation received: no. Action cancelled.")
            self.speech.say("Cancelled, sir.")
            return False
        self._append_output("No clear yes/no confirmation was transcribed. Action cancelled.")
        self.speech.say("I did not hear a clear yes or no, so I cancelled the action.")
        return False

    def _set_output(self, text: str):
        text = str(text)
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")
        self.last_action_result = text
        if self._dispatch_context:
            action_name, transcript = self._dispatch_context
            # A result query must not overwrite the result it is asking about.
            if action_name != "action_result":
                try:
                    self.action_history.record(action_name, transcript, text, success=not text.casefold().startswith(("action failed:", "error:")))
                except Exception as exc:
                    print(f"[ActionHistory] Could not persist action result: {exc}")

    def _append_output(self, text: str):
        self.output.configure(state="normal")
        self.output.insert("end", "\n\n" + text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _refresh(self):
        if self._closed: return
        frame, camera_detections, version, status, error, fps = self.worker.snapshot()
        new_frame = version != self.latest_version
        if frame is not None:
            self.latest_frame = frame
        elif status == "Camera off":
            self.latest_frame = None
        if self.depth_worker is not None:
            self.latest_detections = self.depth_worker.decorate(camera_detections)
            _readings, depth_status, depth_error = self.depth_worker.snapshot()
        else:
            self.latest_detections = camera_detections
            depth_status, depth_error = "Depth not enabled", ""
        if status == "Camera/model error" and error:
            self.status_var.set("Camera/model error")
            self._set_output(error)
        elif self.depth_enabled and depth_status == "Depth unavailable":
            self.status_var.set("Depth unavailable")
            if self.safety_enabled:
                self.safety_enabled = False
                self.safety_var.set(False)
                self._append_output("Safety alerts switched off because the depth model became unavailable.")
        else:
            if self.conversation_active:
                self.status_var.set("Arthur active · 30-second inactivity timeout")
            elif self.wake_word_armed:
                self.status_var.set("Wake-word listening active · camera " + ("on" if self.worker.is_running else "off"))
            else:
                self.status_var.set("Camera " + ("on" if self.worker.is_running else "off") + " · listening disabled")
        depth_hint = depth_status
        if depth_error:
            depth_hint += " — " + depth_error
        self.fps_var.set(f"Display {fps:.1f} FPS · {depth_hint} · audio: on demand")

        if new_frame:
            self.latest_version = version
            self._update_object_table(self.latest_detections)
            if self.face_recognition_enabled and frame is not None and not self._face_scan_pending and time.monotonic() - self._last_face_scan_at >= 0.65:
                self._face_scan_pending = True
                self._last_face_scan_at = time.monotonic()
                frame_for_faces = frame.copy()
                def scan_faces():
                    matches = []
                    for x, y, w, h, crop in self.face_memory.detect_faces(frame_for_faces):
                        result = self.face_memory.recognize(crop)
                        name, score = result if result else ("Unknown face", 0.0)
                        matches.append((x, y, w, h, name, float(score)))
                    return matches
                self._run_async("face_scan", scan_faces)
            # The unified air keyboard is a system-wide overlay. Its keys can be clicked
            # with the mouse or with the same system-wide gesture controller below.
            if frame is not None and self.sign_enabled and self.sign_recognizer is not None and version % 3 == 0:
                try:
                    prediction = self.sign_recognizer.process(frame)
                    if prediction:
                        label, confidence = prediction
                        if label not in {"Uncertain sign"} and confidence >= 0.70 and (label != self.last_sign_spoken or time.monotonic() - self.last_sign_spoken_at > 2.5):
                            self._append_output(f"ISL isolated-sign prediction: {label} ({confidence:.0%}). This is not sentence-level translation.")
                            self.speech.say(label)
                            self.last_sign_spoken = label
                            self.last_sign_spoken_at = time.monotonic()
                except Exception as exc:
                    self._stop_sign_mode()
                    messagebox.showerror("ISL sign mode stopped", str(exc))

        if self.depth_worker is not None:
            alerts = self.depth_worker.take_alerts()
            if self.safety_enabled:
                for alert in alerts:
                    self._append_output("[DEPTH ALERT] " + alert)
                    self.speech.say(alert, priority=True)

        self._draw_preview()
        if self.gesture_enabled and self.gesture_mouse is not None and self.latest_frame is not None and new_frame:
            try:
                self.status_var.set(self.gesture_mouse.process(self.latest_frame))
            except Exception as exc:
                self.gesture_enabled = False
                if self.gesture_mouse:
                    try: self.gesture_mouse.close()
                    except Exception: pass
                    self.gesture_mouse = None
                messagebox.showerror("Air mouse stopped", str(exc))
        self.root.after(30, self._refresh)

    def _draw_preview(self):
        if self._closed or self.latest_frame is None: return
        width = max(480, self.preview.winfo_width())
        height = max(300, self.preview.winfo_height())
        image = draw_detections(self.latest_frame, self.latest_detections)
        if self.face_recognition_enabled:
            for x, y, w, h, label, _score in self.face_overlay:
                cv2.rectangle(image, (x, y), (x+w, y+h), (242, 189, 88), 2)
                cv2.putText(image, label, (x, max(22, y-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (242, 189, 88), 2)
        banner = "Audio on demand | " + ("Metric depth estimates active" if self.depth_enabled else "Depth estimates off")
        cv2.putText(image, banner, (12, image.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.thumbnail((width, height), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(pil)
        self.preview.configure(image=self._photo, text="")

    def _update_object_table(self, detections: list[Detection]):
        for item in self.objects.get_children(): self.objects.delete(item)
        best = {}
        for det in detections:
            key = (det.label, det.direction, det.track_id)
            if key not in best or best[key].confidence < det.confidence: best[key] = det
        for det in sorted(best.values(), key=lambda d: (-d.confidence, d.center_x))[:40]:
            range_text = f"~{det.distance_m:.1f} m" if det.distance_m is not None else "—"
            if det.closing_speed_mps is not None and det.closing_speed_mps > 0.4:
                motion = f"closing {det.closing_speed_mps:.1f} m/s"
            elif det.closing_speed_mps is not None and det.closing_speed_mps < -0.4:
                motion = f"receding {abs(det.closing_speed_mps):.1f} m/s"
            elif det.motion_direction:
                motion = det.motion_direction.replace(" across image", "")
            else:
                motion = "—"
            self.objects.insert("", "end", values=(det.label, det.direction, f"{det.confidence:.0%}", range_text, motion, det.track_id if det.track_id is not None else "—"))

    def _maybe_stop_camera(self):
        """Stop the camera when no persistent user choice or camera feature needs it."""
        if self._camera_explicitly_enabled:
            return
        if self.face_recognition_enabled or self.gesture_enabled or self.depth_enabled or self.sign_enabled:
            return
        self.worker.stop()
        self.latest_frame = None
        self.latest_detections = []

    def _camera_snapshot_for_task(self, wait_for_detection: bool = False, timeout: float = 18.0):
        """Open the camera only for a requested task unless persistent camera mode is enabled."""
        was_running = self.worker.is_running
        _old_frame, _old_detections, starting_version, _old_status, _old_error, _old_fps = self.worker.snapshot()
        if not was_running:
            self.worker.start()
        deadline = time.monotonic() + timeout
        frame = None
        detections = []
        while time.monotonic() < deadline and not self._closed:
            frame, detections, version, status, error, _fps = self.worker.snapshot()
            if status == "Camera/model error":
                if not self._camera_explicitly_enabled:
                    self.worker.stop()
                raise RuntimeError(error or "Camera could not be opened.")
            # A newer frame means the worker has begun its live capture/inference cycle;
            # an empty detection list is valid when no objects are confidently detected.
            if frame is not None and (not wait_for_detection or version >= starting_version + 4):
                self.latest_frame = frame.copy()
                self.latest_detections = list(detections)
                break
            time.sleep(0.08)
        if frame is None:
            if not self._camera_explicitly_enabled:
                self.worker.stop()
            raise RuntimeError("The camera did not produce a frame in time. Check camera permissions and close other apps using it.")
        if not self._camera_explicitly_enabled:
            self._maybe_stop_camera()
            if not self.worker.is_running:
                # Do not retain a camera preview after a temporary task ends.
                self.latest_frame = None
                self.latest_detections = []
        return frame.copy(), list(detections)

    def _require_frame(self):
        try:
            frame, _detections = self._camera_snapshot_for_task(wait_for_detection=False)
            return frame
        except Exception as exc:
            messagebox.showwarning("Camera unavailable", str(exc))
            return None

    def toggle_camera_manual(self):
        """Explicitly keep the camera running, or turn it fully off."""
        if self._camera_explicitly_enabled:
            self._camera_explicitly_enabled = False
            self.worker.stop()
            self.latest_frame = None
            self.latest_detections = []
            self._append_output("Camera turned off.")
            self.speech.say("Camera off, sir.")
            return
        try:
            self._camera_explicitly_enabled = True
            self.worker.start()
            self._append_output("Camera turned on. It will remain active until you turn it off or disable the master system.")
            self.speech.say("Camera on, sir.")
        except Exception as exc:
            self._camera_explicitly_enabled = False
            messagebox.showerror("Camera could not start", str(exc))

    def describe_scene(self):
        try:
            _frame, detections = self._camera_snapshot_for_task(wait_for_detection=True)
            text = summarize_scene(detections) if detections else "I could not confidently detect any objects in the current view."
        except Exception as exc:
            text = f"I could not describe the scene: {exc}"
        self._set_output(text)
        self.speech.say(text)

    def scan_document(self):
        frame = self._require_frame()
        if frame is None: return
        self.status_var.set("Scanning text locally…")
        self._run_async("ocr", lambda: read_document(frame))

    def lookup_word(self):
        if not self.latest_ocr:
            messagebox.showinfo("No document text", "First click Scan / read text to capture text from the page.")
            return
        query = simpledialog.askstring("Find a word", "Word or phrase to find in the last scanned page:", parent=self.root)
        if not query: return
        matches = find_word(self.latest_ocr, query)
        if not matches:
            response = f'No match found for “{query}”.'
        else:
            response = f'Found “{query}” on {len(matches)} line(s):\n' + "\n".join(f"Line {n}: {line}" for n, line in matches[:30])
        self._set_output(response)
        self.speech.say(response)

    def save_snapshot(self):
        frame = self._require_frame()
        if frame is None: return
        default_name = datetime.now().strftime("visionguide-%Y%m%d-%H%M%S.jpg")
        chosen = filedialog.asksaveasfilename(parent=self.root, title="Save camera snapshot",
                    initialdir=str(self.data_dir / "snapshots"), initialfile=default_name,
                    defaultextension=".jpg", filetypes=[("JPEG image", "*.jpg"), ("PNG image", "*.png")])
        if not chosen: return
        if not cv2.imwrite(chosen, frame):
            messagebox.showerror("Snapshot failed", "Could not save this image.")
            return
        self.last_photo_path = Path(chosen)
        self._append_output(f"Snapshot saved locally to: {chosen}")

    def toggle_safety(self):
        self.safety_enabled = bool(self.safety_var.get())
        depth_status = "Depth not enabled"
        if self.depth_worker is not None:
            _readings, depth_status, _error = self.depth_worker.snapshot()
        if self.safety_enabled and not depth_status.startswith("Metric depth active"):
            self.safety_var.set(False)
            self.safety_enabled = False
            messagebox.showinfo("Depth is not ready", "Safety alerts remain off until the metric depth model reports that it is active. Wait for depth loading to finish and try again.")
            return
        state = "enabled" if self.safety_enabled else "disabled"
        self._append_output(f"Depth-based spoken alerts {state}.")
        if self.safety_enabled:
            messagebox.showwarning("Depth-based safety alerts enabled",
                "These are unvalidated monocular depth and object-tracking heuristics. They can miss hazards or alert incorrectly, especially if the camera moves. "
                "They are not a collision-avoidance system and must not be used as a mobility aid.")

    def toggle_face_recognition(self):
        if not self.face_memory.available:
            self.face_var.set(False)
            self.face_recognition_enabled = False
            messagebox.showerror("Face recognition unavailable",
                "This feature requires opencv-contrib-python. Reinstall dependencies from the project requirements in a fresh virtual environment.")
            return
        self.face_recognition_enabled = bool(self.face_var.get())
        if self.face_recognition_enabled:
            self.worker.start()
            self._append_output("Local face recognition is enabled. Only manually enrolled names may be shown; unknown faces remain unknown.")
        else:
            self.active_face_profile = None
            self.face_overlay = []
            self._unknown_greeted = False
            self._append_output("Local face recognition is disabled.")
            self._maybe_stop_camera()

    def enroll_face(self):
        if not self.face_memory.available:
            messagebox.showerror("Face memory unavailable", "Face memory requires opencv-contrib-python. See README.md.")
            return
        name = simpledialog.askstring("Enroll face", "Name/label for this consenting person:", parent=self.root)
        if not name or not name.strip(): return
        approved = self._ask_yes_no("Consent required",
            f"Confirm that {name.strip()} knows their face samples will be stored locally on this computer for recognition. Continue?")
        if not approved: return
        self._append_output(f"Collecting face samples for {name.strip()}. Keep one face centered and turn slightly between samples.")
        camera_was_explicit = self._camera_explicitly_enabled
        try:
            self.worker.start()
        except Exception as exc:
            messagebox.showerror("Camera unavailable", str(exc))
            return
        def collect():
            crops = []
            last_sample = 0.0
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and len(crops) < 10 and not self._closed:
                frame, _, _, _, _, _ = self.worker.snapshot()
                if frame is not None and time.monotonic() - last_sample > 0.45:
                    faces = self.face_memory.detect_faces(frame)
                    if len(faces) == 1:
                        crops.append(faces[0][4])
                        last_sample = time.monotonic()
                time.sleep(0.08)
            try:
                count = self.face_memory.enroll(name.strip(), crops)
                self._async_messages.put(("message", ("Face enrollment complete", f"Saved {count} new samples for {name.strip()} locally.")))
            except Exception as exc:
                self._async_messages.put(("error", ("Face enrollment failed", str(exc))))
            finally:
                if not camera_was_explicit and not self._camera_explicitly_enabled:
                    self._maybe_stop_camera()
        threading.Thread(target=collect, name="face-enrollment", daemon=True).start()

    def manage_faces(self):
        people = self.face_memory.list_people()
        if not people:
            messagebox.showinfo("Local face memory", "No people are enrolled. Use Enroll face… after obtaining consent.")
            return
        selected = simpledialog.askstring("Manage face memory", "Enrolled people:\n" + "\n".join(people) +
            "\n\nEnter the exact name to DELETE all stored samples for that person:", parent=self.root)
        if not selected: return
        if not self._ask_yes_no("Delete biometric data", f"Delete local face samples and recognition data for {selected.strip()}?"):
            return
        try:
            profile_slug = self.face_memory.profile_slug(selected)
            deleted = self.face_memory.delete_person(selected)
            if deleted:
                self.action_history.delete_preferences(profile_slug)
                if self.active_face_profile and self.active_face_profile.casefold() == selected.strip().casefold():
                    self.active_face_profile = None
                self._append_output(f"Deleted face samples, local recognition data, and profile preferences for {selected.strip()}.")
            else: messagebox.showinfo("Not found", "That name was not in local memory.")
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc))

    def toggle_air_mouse(self):
        if self.gesture_enabled:
            self.gesture_enabled = False
            try:
                if self.gesture_mouse: self.gesture_mouse.close()
            finally:
                self.gesture_mouse = None
            self._append_output("Air mouse disabled.")
            self._maybe_stop_camera()
            return
        proceed = self._ask_yes_no("Enable hand gestures", "Hand gestures move the system pointer, pinch to click, use the right-edge strip for scrolling, and quick horizontal swipes to switch browser tabs. They can interact with other applications and the air virtual keyboard. Do not enable while entering passwords or handling sensitive screens. Continue?")
        if not proceed: return
        model_path = self.project_dir / "models" / "hand_landmarker.task"
        try:
            self.gesture_mouse = GestureMouse(model_path)
            self.gesture_enabled = True
            self.worker.start()
            self._append_output("System-wide hand gestures enabled. Move the index finger, pinch to click, use the right-edge strip to scroll, and swipe left/right quickly to switch tabs. The same gestures can select keys on the air virtual keyboard.")
        except Exception as exc:
            self.gesture_mouse = None
            messagebox.showerror("Air mouse could not start", str(exc))

    def calibrate_gestures(self):
        if not self.gesture_enabled or self.gesture_mouse is None:
            messagebox.showinfo("Enable hand gestures first", "Enable Hand gestures… and allow the camera to see one hand before calibrating the pointer range.")
            return
        if not self._ask_yes_no(
            "Calibrate hand pointer — step 1 of 2",
            "After you press Yes, hold your index finger steadily near the upper-left corner of the usable camera view for about two seconds. Keep the whole hand visible. The pointer is paused while calibration runs.",
            parent=self.root,
        ):
            return
        self.gesture_mouse.begin_calibration("upper_left")
        self._poll_gesture_calibration()

    def _poll_gesture_calibration(self):
        controller = self.gesture_mouse
        if not self.gesture_enabled or controller is None:
            return
        state = controller.calibration_state
        if state == "await_lower_right":
            messagebox.showinfo(
                "Calibrate hand pointer — step 2 of 2",
                "Now hold your index finger steadily near the lower-right corner of the usable camera view for about two seconds. Keep the whole hand visible.",
                parent=self.root,
            )
            controller.begin_calibration("lower_right")
        elif state == "complete":
            self._append_output("Hand-pointer calibration saved in memory for this run. You can repeat the wizard if camera position changes.")
            self.speech.say("Hand pointer calibration complete.")
            return
        elif state == "failed":
            messagebox.showwarning("Gesture calibration did not complete", "Keep one hand in view and use farther-apart upper-left and lower-right points, then repeat calibration.", parent=self.root)
            return
        self.root.after(100, self._poll_gesture_calibration)

    def remember_info(self):
        note = simpledialog.askstring("Remember information", "What should Arthur remember locally?", parent=self.root)
        if not note or not note.strip():
            return
        if not self._ask_yes_no("Save local memory", "Save this information on this computer in Arthur's local SQLite memory? It will not be uploaded automatically."):
            return
        try:
            memory_id = self.memory.add(note)
            message = f"Saved memory {memory_id} locally."
            self._append_output(message)
            self.speech.say(message)
        except Exception as exc:
            messagebox.showerror("Could not save memory", str(exc))

    def search_memory(self):
        query = simpledialog.askstring("Search local memory", "Enter a word or phrase to search (leave blank to list recent notes):", parent=self.root)
        if query is None:
            return
        try:
            rows = self.memory.search(query.strip(), limit=30)
            if not rows:
                result = "No matching local memories were found."
            else:
                result = "Local memories (newest first):\n" + "\n\n".join(
                    f"ID {row['id']} · {row['created_at']}\n{row['content']}" for row in rows
                )
            self._set_output(result)
            self.speech.say(result[:5000])
        except Exception as exc:
            messagebox.showerror("Memory search failed", str(exc))

    def delete_memory(self):
        query = simpledialog.askstring("Delete local memory", "Enter a distinctive word or phrase contained in memories to delete matching entries:", parent=self.root)
        if not query or not query.strip():
            return
        matches = self.memory.search(query.strip(), limit=100)
        if not matches:
            messagebox.showinfo("No matches", "No matching memories were found.")
            return
        matching_count = self.memory.count_matching(query.strip())
        preview = "\n\n".join(f"ID {row['id']}: {row['content']}" for row in matches[:10])
        prompt = f"Permanently delete all {matching_count} matching local memory entr(y/ies)?\n\nShowing at most 10 entries:\n\n{preview}"
        if not self._ask_yes_no("Confirm memory deletion", prompt):
            return
        deleted = self.memory.delete_matching(query.strip())
        self._append_output(f"Deleted {deleted} local memory entr(y/ies).")
        self.speech.say(f"Deleted {deleted} local memory entries.")

    def toggle_depth(self):
        if self.depth_enabled:
            self.depth_enabled = False
            self.safety_enabled = False
            self.safety_var.set(False)
            if self.depth_worker:
                self.depth_worker.stop()
            self.depth_worker = None
            self._append_output("Metric depth estimates disabled.")
            self._maybe_stop_camera()
            return
        checkpoint = self.project_dir / "models" / "depth_anything_v2_metric_hypersim_vits.pth"
        source = self.project_dir / "vendor" / "Depth-Anything-V2" / "metric_depth" / "depth_anything_v2" / "dpt.py"
        if not checkpoint.is_file() or not source.is_file():
            if self._ask_yes_no("Depth model not installed", "The ~100 MB indoor metric-depth model is not installed. Run `python tools/setup_depth_model.py` in PowerShell now, then enable depth again. Open instructions?"):
                import webbrowser
                webbrowser.open((self.project_dir / "README.md").as_uri())
            return
        self.worker.start()
        self.depth_worker = DepthWorker(
            self.worker, self.project_dir, checkpoint, self.data_dir / "depth_calibration.json", interval_seconds=1.0
        )
        self.depth_enabled = True
        self.depth_worker.start()
        self._append_output("Loading indoor metric-depth model. Range estimates will appear when ready; they are approximate and not suitable for safe navigation.")

    def calibrate_depth(self):
        if not self.depth_enabled or not self.depth_worker:
            messagebox.showinfo("Depth not enabled", "Enable metric depth estimates first.")
            return
        candidates = [d for d in self.latest_detections if d.track_id is not None and d.distance_m is not None]
        if not candidates:
            messagebox.showinfo("No range readings", "Wait for depth estimates, then try again. The target object must have a track ID.")
            return
        rows = [f"ID {d.track_id}: {d.label}, image {d.direction}, current estimate ~{d.distance_m:.1f} m" for d in candidates]
        picked = simpledialog.askstring("Calibrate range", "Measure one clearly visible object with a tape measure. Enter its track ID below.\n\n" + "\n".join(rows), parent=self.root)
        if not picked: return
        try:
            track_id = int(picked.strip())
        except ValueError:
            messagebox.showerror("Invalid track ID", "Enter the numeric track ID shown in the list.")
            return
        det = next((d for d in candidates if d.track_id == track_id), None)
        if det is None:
            messagebox.showerror("Track not found", "That track is no longer visible. Try again with the current list.")
            return
        known = simpledialog.askfloat("Known distance", f"Enter the measured distance to this {det.label} in metres:", minvalue=0.3, maxvalue=15.0, parent=self.root)
        if known is None: return
        try:
            scale = self.depth_worker.calibrate(det.label, track_id, known)
            messagebox.showinfo("Calibration saved", f"Single-point depth scale factor set to {scale:.3f}. This may improve nearby estimates but does not guarantee accuracy across all objects/distances.")
            self._append_output(f"Depth scale calibration saved: {scale:.3f} using {det.label} at {known:.2f} m.")
        except Exception as exc:
            messagebox.showerror("Calibration failed", str(exc))

    def toggle_air_keyboard(self):
        """Backward-compatible entry point; there is one unified system-wide air keyboard."""
        self.toggle_system_virtual_keyboard()

    def toggle_system_virtual_keyboard(self):
        """Show/hide a mouse-operated keyboard that types into the focused Windows app."""
        if self.system_virtual_keyboard is not None and self.system_virtual_keyboard.is_open:
            self.system_virtual_keyboard.close()
            self.system_virtual_keyboard = None
            self._append_output("System virtual keyboard closed.")
            return
        try:
            keyboard = SystemVirtualKeyboard(self.root, on_status=self._append_output)
            keyboard.open()
            self.system_virtual_keyboard = keyboard
            self._append_output(
                "Unified system-wide air virtual keyboard opened. Use mouse clicks or enable Hand gestures to move the pointer and pinch-click keys. Voice commands such as 'type exactly hello world' paste literal text into the currently focused application without submitting it."
            )
        except Exception as exc:
            self.system_virtual_keyboard = None
            messagebox.showerror("System virtual keyboard could not start", str(exc))
            self.speech.say("The system virtual keyboard could not start. Please check the displayed error.")

    def toggle_sign_mode(self):
        if self.sign_enabled:
            self._stop_sign_mode()
            self._append_output("ISL isolated-sign mode disabled.")
            self._maybe_stop_camera()
            return
        if self.gesture_enabled:
            messagebox.showinfo("Gesture tool active", "Disable system-wide hand gestures before enabling sign recognition so both features do not compete for the same camera frames.")
            return
        accepted = self._ask_yes_no("Enable isolated ISL sign recognition", "Sign mode processes camera frames locally and speaks high-confidence predictions. It requires a trained model for a limited Indian Sign Language (ISL) vocabulary. It is not a full sentence translator. Continue?")
        if not accepted: return
        try:
            from visionguide.sign_language import ISLRecognizer
            self.sign_recognizer = ISLRecognizer(self.project_dir)
            self.sign_enabled = True
            self.worker.start()
            self._append_output("ISL isolated-sign recognition enabled. This model does not translate continuous sentences and may be inaccurate.")
        except Exception as exc:
            messagebox.showerror("ISL model unavailable", str(exc))

    def _stop_sign_mode(self):
        self.sign_enabled = False
        if self.sign_recognizer:
            try: self.sign_recognizer.close()
            except Exception: pass
        self.sign_recognizer = None
        self._maybe_stop_camera()

    def ask_gemini_text(self):
        question = simpledialog.askstring("Text-only AI", "Ask a general question, draft an email, summarize text, or request a writing task. No camera image will be sent:", parent=self.root)
        if not question or not question.strip():
            return
        if not self._ask_yes_no("Send text to Gemini?", "This sends the text you entered to Google's Gemini API. No camera image is attached. Continue?"):
            return
        use_web_search = self._ask_yes_no("Use web search?", "Allow Gemini to use Google Search grounding for this text-only request? Choose No for a text-only AI response without Search grounding.")
        self.status_var.set("Waiting for text-only AI response…")
        self._set_output("Sending your requested text-only prompt…")
        self._run_async("text_ai", lambda: self.gemini.ask_text(question.strip(), use_web_search=use_web_search))

    def _submit_voice_text_ai(self, prompt: str):
        if not self._ask_yes_no("Send text to Gemini?", "This sends only your transcribed words to Gemini. No camera image is attached. Continue?"):
            return
        use_web_search = self._ask_yes_no("Use web search?", "Allow Google Search grounding for this request?")
        self.status_var.set("Waiting for text-only AI response…")
        self._run_async("text_ai", lambda: self.gemini.ask_text(prompt, use_web_search=use_web_search))

    def ask_gemini_with_typed_prompt(self):
        question = self.virtual_input_var.get().strip()
        if not question:
            messagebox.showinfo("Prompt is empty", "Type a question manually or use the unified air virtual keyboard while this prompt field is focused.")
            return
        frame = self._require_frame()
        if frame is None: return
        approved = self._ask_yes_no("Send image to Gemini?", "This will upload the current camera image and your question to Google Gemini. The image may include people or private information. Proceed?")
        if not approved: return
        self._run_async("gemini", lambda: self.gemini.ask_about_frame(question, frame, False))

    def ask_gemini(self, use_web_search: bool):
        frame = self._require_frame()
        if frame is None: return
        question = simpledialog.askstring("Ask Gemini", "Question about the current camera image:", parent=self.root)
        if not question or not question.strip(): return
        action = " and a web search" if use_web_search else ""
        approved = self._ask_yes_no("Send image to Gemini?",
            "This action will upload the current camera image and your question to the Google Gemini API" + action + ". "
            "The image may include people or private information. Proceed only if you are comfortable sharing it.")
        if not approved: return
        self.status_var.set("Waiting for Gemini response…")
        self._set_output("Sending the requested image question…")
        self._run_async("gemini", lambda: self.gemini.ask_about_frame(question.strip(), frame, use_web_search))

    def voice_command(self):
        if not self._ask_yes_no("Record voice command", "Record up to 5 seconds from your microphone? "
            "Audio will be transcribed locally with Whisper when installed; it is not sent to Gemini by this action."):
            return
        if self.wake_word_listener is not None:
            self.wake_word_listener.stop()
            self.wake_word_listener = None
        self.status_var.set("Recording voice command for 5 seconds…")
        self._run_async("voice", self._record_voice)

    @staticmethod
    def _record_voice():
        from visionguide.voice_commands import record_and_transcribe
        return record_and_transcribe(duration_seconds=5.0, model_name="base")

    def _run_async(self, action: str, function):
        def run():
            try:
                result = function()
                self._async_messages.put((action, result))
            except Exception as exc:
                self._async_messages.put(("error", (action, str(exc))))
        threading.Thread(target=run, name=f"visionguide-{action}", daemon=True).start()

    def _drain_async_messages(self):
        if self._closed: return
        try:
            while True:
                action, result = self._async_messages.get_nowait()
                if action == "wake_detected":
                    self._on_wake_word_detected()
                elif action == "conversation_transcript":
                    transcript = str(result).strip()
                    if transcript:
                        self._append_output("Arthur heard: " + transcript)
                        self._route_voice_command(transcript)
                    else:
                        self._conversation_command_done.set()
                elif action == "conversation_end":
                    reason = str(result)
                    self.conversation_active = False
                    self._conversation_stop.set()
                    self.status_var.set("Wake-word listening active" if self.wake_word_armed else "Listening disabled")
                    if reason == "timeout":
                        self.speech.say("I'll wait for you, sir.")
                    elif reason == "sleep":
                        self.speech.say("Sleeping now, sir.")
                    elif reason == "goodbye":
                        self.speech.say("Goodbye, sir.")
                    else:
                        self.speech.say("Okay, sir. I'll wait for you.")
                    if self.wake_word_armed:
                        def restart_after_response():
                            self.speech.wait_until_idle(timeout=15.0)
                            self._async_messages.put(("restart_wake", None))
                        threading.Thread(target=restart_after_response, daemon=True).start()
                elif action == "restart_wake":
                    if self.wake_word_armed and not self.conversation_active:
                        self._restart_wake_word_listener()
                elif action == "conversation_error":
                    self.conversation_active = False
                    self._conversation_stop.set()
                    self._append_output("Continuous listening stopped: " + str(result))
                    self.speech.say("I had a microphone or transcription error, sir.")
                    if self.wake_word_armed:
                        self.root.after(1000, self._restart_wake_word_listener)
                elif action == "wake_error":
                    self.wake_word_armed = False
                    self.conversation_active = False
                    self.listening_button.configure(text="Listening: OFF")
                    if self.wake_word_listener:
                        self.wake_word_listener = None
                    message = "Wake-word listener stopped: " + str(result)
                    self._append_output(message)
                    self.speech.say("Wake word mode stopped because of an error.")
                    messagebox.showerror("Wake word mode", message)
                elif action in {"ocr", "screen_ocr"}:
                    self.latest_ocr = str(result).strip()
                    if self.latest_ocr:
                        save_path = save_document(self.latest_ocr, self.data_dir / "documents")
                        self._set_output(self.latest_ocr + f"\n\nSaved local text copy: {save_path}")
                        spoken = self.latest_ocr[:6000]
                        self.speech.say(spoken)
                    else:
                        self._set_output("No readable text was found. Try holding the page flat, filling the frame, improving light, and scanning again.")
                        self.speech.say("I could not read text on this page. Try holding it steady in better light.")
                elif action in {"gemini", "text_ai"}:
                    self._set_output(str(result))
                    self.speech.say(str(result)[:6000])
                    self.status_var.set("AI response received")
                elif action == "route":
                    transcript, routed = result
                    self._dispatch_routed_command(str(transcript), routed)
                elif action == "face_scan":
                    self._face_scan_pending = False
                    matches = list(result or [])
                    self.face_overlay = matches
                    if matches:
                        self._face_absence_since = 0.0
                        known_profiles = [item[4] for item in matches if item[4] != "Unknown face" and self.face_memory.is_enrolled_name(item[4])]
                        # Apply personalized greetings only for one unambiguous enrolled face.
                        if len(matches) == 1 and len(known_profiles) == 1:
                            matched_name = known_profiles[0]
                            if matched_name != self.active_face_profile:
                                self.active_face_profile = matched_name
                                self._last_greeted_profile = matched_name
                                self._unknown_greeted = False
                                slug = self.face_memory.profile_slug(matched_name)
                                prefs = self.action_history.get_preferences(slug) if slug else {}
                                greeting = prefs.get("preferred_name") or matched_name
                                self.speech.say(f"Hello, {greeting}.")
                        else:
                            self.active_face_profile = None
                            if not self._unknown_greeted:
                                self.speech.say("Hello. I do not recognize this view as one enrolled person. What would you like me to call you?")
                                self._unknown_greeted = True
                    else:
                        if not self._face_absence_since:
                            self._face_absence_since = time.monotonic()
                        elif time.monotonic() - self._face_absence_since >= 2.5:
                            self.active_face_profile = None
                            self._unknown_greeted = False
                            self._last_greeted_profile = None
                elif action == "navigation_update":
                    update = result
                    kind = getattr(update, "kind", "update")
                    message = str(getattr(update, "message", update))
                    if kind in {"started", "instruction", "rerouted", "arrived", "location_error", "stopped"}:
                        route = getattr(update, "route", None)
                        if kind in {"started", "rerouted"} and route is not None:
                            preview_note = ""
                            try:
                                self.maps_services.open_route_in_maps(route.origin, route.destination, route.travel_mode)
                                preview_note = " Google Maps route preview opened; live spoken guidance and rerouting continue in Arthur."
                            except Exception as exc:
                                preview_note = f" Google Maps preview could not open: {exc}"
                            message += preview_note
                        self._set_output(message)
                        spoken_message = str(getattr(update, "message", message))
                        self.speech.say(spoken_message[:2400], priority=(kind in {"instruction", "rerouted", "arrived"}))
                        self._record_async_action("navigation_" + str(kind), message, success=kind != "location_error")
                    if kind == "arrived" and self.navigation_session is not None:
                        self.navigation_session = None
                elif action in {"weather", "route_calculation", "product_lookup", "typed_text", "calculator"}:
                    message = str(result)
                    self._set_output(message)
                    self.speech.say(message[:4500])
                    self._record_async_action(action, message)
                    self.status_var.set("Action completed")
                elif action == "navigation_start":
                    # The session's started callback contains the spoken route summary.
                    self._record_async_action(action, result)
                elif action == "draft_text":
                    draft = str(result).strip()
                    self._set_output("Draft preview — review the content before pasting. Nothing has been sent.\n\n" + draft)
                    self.speech.say("The draft is ready for review. It has not been sent.")
                    self._record_async_action(action, draft)
                    if draft and self._ask_yes_no("Paste reviewed draft?", "The full draft is shown in the Arthur output panel. Paste it into your currently focused Windows text field? It will not be submitted or sent. After Yes, you have four seconds to select the target application and field.", parent=self.root):
                        self.status_var.set("Draft will be pasted in four seconds — select the target field now.")
                        self.speech.say("Select the target application and field within four seconds.")
                        self._run_async("typed_text", lambda: self._paste_after_focus_delay(draft, 4.0))
                elif action == "workspace":
                    message = self._format_workspace_result(result)
                    self._set_output(message)
                    self.speech.say(message[:3200])
                    self.status_var.set("Google Workspace action complete")
                elif action == "timer_expired":
                    timer_id, label = result
                    message = f"Timer {timer_id} finished: {label}."
                    self._append_output(message)
                    self.status_var.set("Timer completed")
                    self.speech.say(message, priority=True)
                elif action in {"voice", "wakevoice"}:
                    transcript = str(result).strip()
                    if transcript:
                        self._append_output("Voice command transcript: " + transcript)
                        self._route_voice_command(transcript)
                    else:
                        self._append_output("No clear speech was transcribed. Try again in a quieter place.")
                        self.speech.say("I could not understand the voice command. Please try again.")
                    self.status_var.set("Ready — audio is on demand")
                    if self.wake_word_armed and not self.conversation_active:
                        self.root.after(900, self._restart_wake_word_listener)
                elif action == "message":
                    title, body = result
                    self._append_output(body)
                    messagebox.showinfo(title, body)
                elif action == "error":
                    title, body = result
                    if self.conversation_active and str(title) == "route":
                        self._conversation_command_done.set()
                    if title == "face_scan":
                        self._face_scan_pending = False
                    if title == "navigation_start":
                        self.navigation_session = None
                    self._set_output(f"Action failed: {body}")
                    self._record_async_action(str(title), str(body), success=False)
                    messagebox.showerror("Arthur", f"{title}\n\n{body}")
                    self.status_var.set("Ready — check the error message")
                    if title == "wakevoice" and self.wake_word_armed:
                        self.root.after(1200, self._restart_wake_word_listener)
        except queue.Empty:
            pass
        self.root.after(120, self._drain_async_messages)

    @staticmethod
    def _paste_after_focus_delay(text: str, delay_seconds: float = 4.0) -> str:
        # Give the user time to activate the intended application after a modal confirmation.
        time.sleep(max(0.5, min(float(delay_seconds), 8.0)))
        return type_text_to_focused_window(text)

    def _calculate_and_open_route(self, origin: str, destination: str, mode: str) -> str:
        route = self.maps_services.compute_route(origin, destination, mode, traffic_aware=True)
        mode_label = {
            "DRIVE": "car", "TWO_WHEELER": "motorcycle/two-wheeler", "WALK": "walking",
            "BICYCLE": "bicycle", "TRANSIT": "public transport",
        }.get(route.travel_mode, route.travel_mode)
        time_note = "traffic-aware ETA" if route.traffic_aware else "estimated travel time"
        traffic_delta = ""
        if route.traffic_aware and route.static_duration_seconds:
            difference = route.duration_seconds - route.static_duration_seconds
            if abs(difference) >= 60:
                traffic_delta = f" Traffic changes the estimate by about {round(abs(difference) / 60)} minutes {'longer' if difference > 0 else 'shorter'} than the non-traffic estimate."
        instructions = "\n".join(
            f"{index}. {step.instruction}" for index, step in enumerate(route.steps[:10], start=1)
        ) or "The provider returned no detailed maneuver list."
        # Static route preview opens Google Maps; the API response is still reported separately.
        origin_for_maps = origin if isinstance(origin, str) else f"{origin[0]},{origin[1]}"
        try:
            self.maps_services.open_route_in_maps(origin_for_maps, destination, route.travel_mode)
            maps_note = " Google Maps was opened for visual route review."
        except Exception as exc:
            maps_note = f" Google Maps could not be opened automatically: {exc}"
        beta_note = " The provider marks this travel mode as subject to beta/coverage limitations; verify local road legality and routing." if route.travel_mode in {"TWO_WHEELER", "WALK", "BICYCLE"} else ""
        return (
            f"Route from {route.origin} to {route.destination} by {mode_label}: {route.distance_text}; "
            f"{time_note}: {route.duration_text}.\n\nTurn-by-turn steps from the route provider:\n{instructions}"
            f"{traffic_delta}{beta_note}{maps_note}\n\nThis is a route-provider estimate, not confirmation of road conditions beyond its returned data."
        )

    def _research_visible_item(self, frame, query: str) -> str:
        # Cache by image content + question; raw camera frames are not written to disk.
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
        if not ok:
            raise RuntimeError("The camera frame could not be encoded for product research.")
        cache_key = "product-research:" + hashlib.sha256(encoded.tobytes() + query.encode("utf-8", "replace")).hexdigest()
        cached = self.maps_services.cache.get(cache_key)
        if cached:
            return str(cached.get("response", "")) + "\n\nThis answer was reused from the local cache; it may be stale."

        sections: list[str] = []
        try:
            ocr_text = str(read_document(frame)).strip()
            if ocr_text:
                sections.append("Text detected in the camera image (OCR; may contain errors):\n" + ocr_text[:3500])
        except Exception as exc:
            sections.append(f"Local label OCR was unavailable: {exc}")

        visual_error = ""
        if self.maps_services.cloud_api_key:
            try:
                visual = self.maps_services.web_search_image(frame)
                sections.append("Public visual-search results:\n" + self.maps_services.format_visual_search(visual))
            except Exception as exc:
                visual_error = f"Google Cloud Vision Web Detection was unavailable: {exc}"
        else:
            visual_error = "Google Cloud visual search was skipped because GOOGLE_CLOUD_API_KEY or GOOGLE_VISION_API_KEY is not configured."

        if self.gemini.available():
            prompt = (
                f"{query}\n\nUse only visible evidence for visual claims. Use the attached image to infer likely object category and, if legible, brand/model. "
                "When product facts are uncertain, distinguish inference from verified information. If the image contains a person, do not claim a verified identity from appearance or image similarity; public visual-search matches are only leads and must be described as such. "
                "When web search is available, cite or name the source/website used. Keep the answer concise and useful."
            )
            try:
                sections.append("Gemini visual research:\n" + self.gemini.ask_about_frame(prompt, frame, True))
            except Exception as exc:
                sections.append(f"Gemini research was unavailable: {exc}")
        else:
            sections.append("Gemini visual research was skipped because GEMINI_API_KEY is not configured.")

        if visual_error:
            sections.append(visual_error)
        sections.append("Important: camera-based product identification and visual-search matches are not proof of the exact model. Verify specifications against an official manufacturer page or manual before relying on them.")
        response = "\n\n".join(sections)
        self.maps_services.cache.put(cache_key, {"response": response}, 86400)
        return response

    def _record_async_action(self, action: str, result: object, *, success: bool = True) -> None:
        transcript = self.last_voice_transcript
        try:
            if isinstance(result, str):
                result_text = result
            elif hasattr(result, "distance_text"):
                result_text = f"Route {getattr(result, 'origin', '')} to {getattr(result, 'destination', '')}; {getattr(result, 'distance_text', '')}, {getattr(result, 'duration_text', '')}."
            else:
                result_text = str(result)
            self.action_history.record(action, transcript, result_text, success=success)
        except Exception as exc:
            print(f"[ActionHistory] Could not persist async result for {action}: {exc}")

    @staticmethod
    def _normalise_arthur_command(transcript: str) -> str:
        text = " ".join(str(transcript).strip().split())
        text = re.sub(r"^[,\s]*(?:hey|hi|hello)\s+arthur[,\s:.-]*", "", text, flags=re.I)
        text = re.sub(r"^[,\s]*arthur[,\s:.-]+", "", text, flags=re.I)
        text = re.sub(r"[,\s:.-]+arthur[.!?\s]*$", "", text, flags=re.I)
        text = text.strip(" ,.!?\t\r\n")
        return "" if text.casefold() == "arthur" else text

    @staticmethod
    def _exit_phrase_kind(transcript: str) -> str | None:
        text = " ".join(str(transcript).casefold().strip().split())
        text = re.sub(r"[^a-z0-9' ]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"^(?:hey|hi|hello) arthur\s*", "", text)
        text = re.sub(r"^arthur\s*", "", text)
        text = re.sub(r"\s*arthur$", "", text).strip()
        if re.fullmatch(r"(?:please )?(?:goodbye|good bye|bye|see you)(?: now| please)?", text):
            return "goodbye"
        if re.fullmatch(r"(?:please )?(?:(?:go|fall) to sleep|sleep|shut down listening|stop listening|stop listening now|deactivate listening|wait quietly)(?: now| please)?", text):
            return "sleep"
        return None

    def _route_voice_command(self, transcript: str):
        transcript = str(transcript).strip()
        exit_kind = self._exit_phrase_kind(transcript)
        if self.conversation_active and exit_kind:
            self._conversation_stop.set()
            self._async_messages.put(("conversation_end", exit_kind))
            return
        cleaned = self._normalise_arthur_command(transcript) if self.conversation_active else transcript
        if self.conversation_active and not cleaned:
            self.speech.say("I'm listening, sir.")
            self._conversation_command_done.set()
            return
        self.status_var.set("Understanding voice command…")
        self._run_async("route", lambda: (cleaned or transcript, self.command_router.route(cleaned or transcript)))

    def _dispatch_routed_command(self, transcript: str, routed):
        self._dispatch_context = (str(routed.action), str(transcript))
        self.last_voice_transcript = str(transcript)
        try:
            return self._dispatch_routed_command_impl(transcript, routed)
        finally:
            self._dispatch_context = None
            if self.conversation_active:
                self._conversation_command_done.set()

    def _dispatch_routed_command_impl(self, transcript: str, routed):
        action, argument = routed.action, routed.legacy_argument()
        args = routed.arguments

        # Input and assistive controls are intentionally local-first; literal text never becomes code.
        if action == "keyboard_toggle":
            should_open = bool(args.get("open", True))
            is_open = bool(self.system_virtual_keyboard and self.system_virtual_keyboard.is_open)
            if should_open != is_open:
                self.toggle_system_virtual_keyboard()
            else:
                message = "The unified air virtual keyboard is already open." if should_open else "The unified air virtual keyboard is already closed."
                self._set_output(message); self.speech.say(message)
            return
        if action == "gesture_control":
            desired = bool(args.get("enabled", True))
            if desired != self.gesture_enabled:
                self.toggle_air_mouse()
            else:
                message = "System-wide hand gestures are already enabled." if desired else "System-wide hand gestures are already disabled."
                self._set_output(message); self.speech.say(message)
            return
        if action == "type_text":
            literal = str(args.get("text", ""))
            if not literal:
                self.speech.say("Tell me the exact text you want typed.")
                return
            preview = literal if len(literal) <= 1200 else literal[:1200] + "…"
            confirm_text = ("Paste this exact text into a Windows text field? It will not be submitted or sent.\n\n"
                           "After selecting Yes, switch to the intended application and click its target field within four seconds.\n\n" + preview)
            if self._ask_yes_no("Type literal text?", confirm_text, parent=self.root):
                self.status_var.set("Typing in four seconds — select the target application and field now.")
                self.speech.say("Switch to the target application and click the field within four seconds.")
                self._run_async("typed_text", lambda: self._paste_after_focus_delay(literal, 4.0))
            else:
                self.speech.say("Typing cancelled. Nothing was entered.")
            return
        if action == "draft_and_type":
            prompt = str(args.get("prompt", transcript)).strip()
            if not self.gemini.available():
                message = "Draft generation requires GEMINI_API_KEY in your local .env file. No text was entered."
                self._set_output(message); self.speech.say(message)
                return
            generic = bool(re.search(r"\b(?:an?\s+)?(?:email|message|reply|note|paragraph)\b", prompt, re.I)) and not bool(re.search(r"\b(?:about|regarding|because|request(?:ing)?|ask(?:ing)?|tell(?:ing)?|thank(?:ing)?|apolog(?:y|ize|ise)|say(?:ing)?|that)\b", prompt, re.I))
            if generic:
                details = simpledialog.askstring("Draft details", "What should the email/message say? Enter the important context; Arthur will not invent personal facts.", parent=self.root)
                if not details or not details.strip():
                    self.speech.say("Draft cancelled because no message details were provided.")
                    return
                prompt += "\nUser-provided content/details: " + details.strip()
            if not self._ask_yes_no("Draft with Gemini?", "Send this text instruction to Gemini to generate a draft? No camera image will be attached. The generated draft will be shown for review and will not be sent automatically.", parent=self.root):
                return
            full_prompt = ("Create a polished, editable draft from this instruction. Do not invent names, dates, reasons, commitments, or other personal facts. "
                           "Where an essential fact is missing, use a clearly marked short placeholder instead. Return only the draft text, no commentary.\n\n" + prompt)
            self._run_async("draft_text", lambda: self.gemini.ask_text(full_prompt, use_web_search=False))
            return
        if action == "focus_target":
            target = str(args.get("target", "")); element = str(args.get("element", ""))
            try:
                response = focus_application_target(target, element)
                self._set_output(response); self.speech.say(response)
            except Exception as exc:
                self._set_output(f"Could not focus the requested target safely: {exc}")
                self.speech.say("I could not verify that control. Please select the field manually before typing.")
            return
        if action == "calculate_expression":
            try:
                expression, result = calculate_expression(str(args.get("expression", "")))
                response = f"The calculation is {expression} = {result}. This result was computed locally using a restricted arithmetic parser."
                self._set_output(response); self.speech.say(response)
            except Exception as exc:
                self._set_output(f"Calculation failed: {exc}"); self.speech.say("I could not safely calculate that expression.")
            return
        if action == "calculator_calculate":
            expression = str(args.get("expression", ""))
            self._run_async("calculator", lambda: calculator_calculate(expression))
            return
        if action == "action_result":
            recent = bool(args.get("recent", False))
            if recent:
                response = summarize_recent_actions(self.action_history.recent(6))
            else:
                record = self.action_history.last()
                response = (f"The last recorded action was: {record.get('transcript') or record.get('action')}. Result: {record.get('result')}" if record else "I don't have a completed action result recorded yet.")
            self._set_output(response); self.speech.say(response[:3500])
            return
        if action == "profile_preference_set":
            value = str(args.get("value", "")).strip()
            key = str(args.get("key", "preferred_name")).strip() or "preferred_name"
            profile_name = self.active_face_profile if self.active_face_profile and self.face_memory.is_enrolled_name(self.active_face_profile) else None
            if not profile_name:
                people = self.face_memory.list_people()
                if not people:
                    message = "No enrolled face profile is available for a persistent preference. Enroll the consenting user first, then repeat the preference command."
                    self._set_output(message); self.speech.say(message)
                    return
                selected = simpledialog.askstring("Profile preference", "Which enrolled profile should this preference apply to? Enter an exact name:\n\n" + "\n".join(people), parent=self.root)
                profile_name = next((name for name in people if selected and name.casefold() == selected.strip().casefold()), None)
            slug = self.face_memory.profile_slug(profile_name) if profile_name else None
            if not slug or not value:
                message = "Preference not saved. Choose an exact enrolled profile and provide a non-empty preference."
            else:
                self.action_history.set_preference(slug, key, value)
                message = f"Saved the preference for enrolled profile {profile_name}: preferred form of address is {value}. It is stored locally and will persist across restarts."
            self._set_output(message); self.speech.say(message)
            return
        if action == "weather_lookup":
            location = str(args.get("location", "")).strip() or os.getenv("VISIONGUIDE_DEFAULT_LOCATION", "").strip()
            if not location:
                use_current = self._ask_yes_no("Weather location", "No place was specified. Use your device's current location? Arthur will request Windows location access but will not send it to a general web search.")
                if use_current:
                    self._run_async("weather", lambda: self.maps_services.format_weather(",".join(map(str, WindowsLocationProvider.current_position())))
                    )
                    return
                location = simpledialog.askstring("Weather location", "Enter a city, place, address, or 'latitude, longitude':", parent=self.root) or ""
            if not location:
                self.speech.say("Weather lookup cancelled because no location was supplied.")
                return
            self._run_async("weather", lambda: self.maps_services.format_weather(location))
            return
        if action == "route_start":
            destination = str(args.get("destination", "")).strip()
            origin = str(args.get("origin", "")).strip()
            mode = str(args.get("travel_mode", "DRIVE"))
            if not destination:
                destination = simpledialog.askstring("Navigation destination", "Where would you like to go?", parent=self.root) or ""
            if not destination:
                self.speech.say("Navigation cancelled because no destination was supplied.")
                return
            start_live = self._ask_yes_no("Live navigation", "Start live turn-by-turn guidance? This uses Windows device location (if available), speaks route steps, and may request another route if you go off route. Location is used for navigation, not saved as a profile.")
            if start_live and origin:
                use_current = self._ask_yes_no(
                    "Use current location?",
                    f"The requested origin was: {origin}. Live navigation must start from the device's current Windows location and will not use that typed origin. Use current location instead? Choose No to calculate the route from the specified origin without live GPS guidance.",
                    parent=self.root,
                )
                if not use_current:
                    start_live = False
            if start_live:
                if self.navigation_session and self.navigation_session.running:
                    messagebox.showinfo("Navigation already active", "Stop the current navigation before starting another route.")
                    return
                self.navigation_session = NavigationSession(
                    self.maps_services, destination, mode,
                    on_update=lambda update: self._async_messages.put(("navigation_update", update)),
                )
                self._run_async("navigation_start", lambda: self.navigation_session.start())
            else:
                if not origin:
                    origin = simpledialog.askstring("Route origin", "Enter the starting place or address:", parent=self.root) or ""
                if not origin:
                    self.speech.say("Route lookup cancelled because no origin was supplied.")
                    return
                self._run_async("route_calculation", lambda: self._calculate_and_open_route(origin, destination, mode))
            return
        if action == "navigation_stop":
            if self.navigation_session:
                session, self.navigation_session = self.navigation_session, None
                session.stop()  # The session callback announces the stop exactly once.
                self._set_output("Stopping live navigation.")
            else:
                message = "No live navigation session is active."
                self._set_output(message); self.speech.say(message)
            return
        if action == "product_lookup":
            frame = self._require_frame()
            if frame is None:
                return
            query = str(args.get("query", "Tell me about the visible product or object.")).strip()
            if not self._ask_yes_no("Research the visible item?", "Arthur will send a compressed camera image to the configured Gemini service and, when a Google Cloud API key is available, Google Cloud Vision Web Detection to look for related public pages and visually similar images. The image may contain people or private information. Continue?"):
                self.speech.say("Visual product research cancelled; the image was not uploaded by this action.")
                return
            self._run_async("product_lookup", lambda: self._research_visible_item(frame, query))
            return

        # Google API extensions execute only through scoped adapters and bounded requests.
        if action in {"google_workspace_feature", "google_maps_feature", "google_cloud_feature"}:
            try:
                if action == "google_workspace_feature":
                    from visionguide.integrations.google_workspace import execute_google_workspace_operation, GOOGLE_WORKSPACE_WRITE_OPERATIONS
                    operation = str(args.get("operation", "")).casefold()
                    if operation in GOOGLE_WORKSPACE_WRITE_OPERATIONS:
                        preview = "\n".join(f"{key}: {str(value)[:1000]}" for key, value in args.items() if key != "operation")
                        if not self._ask_yes_no("Confirm Google Workspace change", f"Arthur will perform '{operation}' in your Google account. Review the details below. This action cannot be automatically undone. Continue?\n\n{preview}", parent=self.root):
                            self.speech.say("Google Workspace change cancelled.")
                            return
                    self._run_async("workspace", lambda: execute_google_workspace_operation(operation, args, confirmed=operation in GOOGLE_WORKSPACE_WRITE_OPERATIONS))
                    return
                if action == "google_maps_feature":
                    from visionguide.integrations.google_services import execute_google_maps_operation
                    operation = str(args.get("operation", "")).casefold()
                    self._run_async("workspace", lambda: execute_google_maps_operation(operation, args, service=self.maps_services))
                    return
                from visionguide.integrations.google_cloud_services import execute_google_cloud_operation
                operation = str(args.get("operation", "")).casefold()
                if not self._ask_yes_no("Send text to Google Cloud?", f"The requested {operation} action sends the supplied text to Google's Cloud API for processing. It is not saved by this local integration. Do not submit passwords or other unnecessary sensitive information. Continue?\n\n{str(args.get('text', ''))[:1000]}", parent=self.root):
                    self.speech.say("Google Cloud text operation cancelled.")
                    return
                self._run_async("workspace", lambda: execute_google_cloud_operation(operation, args))
            except Exception as exc:
                messagebox.showerror("Google API integration", str(exc), parent=self.root)
                self.speech.say("The Google API request failed. Check the displayed error.")
            return

        # These integrations execute through typed, permission-aware device/provider adapters.
        if action in {"media_playback", "brightness_set", "brightness_adjust", "volume_set", "volume_adjust", "audio_mute", "wifi_set", "wifi_status", "brightness_get", "volume_get",
                      "timer_set", "timer_list", "timer_cancel", "gmail_unread", "gmail_search", "calendar_upcoming", "calendar_search",
                      "calendar_create_event", "gmail_compose", "gmail_send_current", "gmail_read_message", "word_write", "whatsapp_compose",
                      "whatsapp_send_current", "type_into_window"}:
            try:
                if action == "media_playback":
                    response = media_playback(str(args.get("action", "toggle")), int(args.get("seconds", 10)))
                    self._set_output(response); self.speech.say(response)
                elif action == "brightness_set":
                    response = set_brightness(int(args["level"]))
                    self._set_output(response); self.speech.say(response)
                elif action == "brightness_adjust":
                    response = adjust_brightness(int(args["delta"]))
                    self._set_output(response); self.speech.say(response)
                elif action == "volume_set":
                    response = set_volume(int(args["level"]))
                    self._set_output(response); self.speech.say(response)
                elif action == "volume_adjust":
                    response = adjust_volume(int(args["delta"]))
                    self._set_output(response); self.speech.say(response)
                elif action == "audio_mute":
                    response = set_mute(bool(args.get("muted", True)))
                    self._set_output(response); self.speech.say(response)
                elif action == "brightness_get":
                    response = f"Current display brightness is approximately {get_brightness()} percent."
                    self._set_output(response); self.speech.say(response)
                elif action == "volume_get":
                    state = get_volume()
                    response = f"System volume is {state['volume']} percent and audio is {'muted' if state['muted'] else 'unmuted'}."
                    self._set_output(response); self.speech.say(response)
                elif action == "wifi_status":
                    adapters = list_wifi_adapters()
                    response = "Network adapters: " + ("; ".join(f"{x['name']}: {x['admin_state']}, {x['state']}" for x in adapters) or "none detected")
                    self._set_output(response); self.speech.say(response[:1500])
                elif action == "wifi_set":
                    enabled = bool(args.get("enabled"))
                    adapter = str(args.get("adapter", "Wi-Fi"))
                    operation = "enable" if enabled else "disable"
                    if self._ask_yes_no("Change Wi-Fi state?", f"This will {operation} the network adapter {adapter!r}. This may disconnect Arthur and active work. Continue?"):
                        response = set_wifi(enabled, adapter)
                        self._set_output(response); self.speech.say(response)
                    else:
                        self.speech.say("Wi-Fi change cancelled.")
                elif action == "timer_set":
                    record = self.timer_manager.schedule(int(args.get("seconds", 0)), str(args.get("label", "Reminder")))
                    response = f"Timer {record.timer_id} set for {record.duration_seconds} seconds: {record.label}."
                    self._set_output(response); self.speech.say(response)
                elif action == "timer_list":
                    rows = self.timer_manager.list_timers()
                    response = "No active timers." if not rows else "Active timers: " + "; ".join(f"{r['id']}: {r['label']}, {r['remaining_seconds']} seconds remaining" for r in rows)
                    self._set_output(response); self.speech.say(response)
                elif action == "timer_cancel":
                    timer_id = int(args.get("id", 0))
                    cancelled = self.timer_manager.cancel(timer_id)
                    response = f"Timer {timer_id} cancelled." if cancelled else f"No active timer with ID {timer_id}."
                    self._set_output(response); self.speech.say(response)
                elif action == "gmail_unread":
                    limit = int(args.get("limit", 10)); include_body = bool(args.get("include_body", False))
                    self._run_async("workspace", lambda: {"kind": "gmail_unread", "include_body": include_body, "messages": gmail_unread(limit, include_body=include_body)})
                elif action == "gmail_read_message":
                    message_id = str(args.get("message_id", ""))
                    self._run_async("workspace", lambda: {"kind": "gmail_read_message", "message": gmail_read_message(message_id)})
                elif action == "gmail_search":
                    query = str(args.get("query", ""))
                    limit = int(args.get("limit", 10))
                    self._run_async("workspace", lambda: {"kind": "gmail_search", "messages": gmail_search(query, limit)})
                elif action == "calendar_upcoming":
                    days, limit = int(args.get("days", 7)), int(args.get("limit", 10))
                    self._run_async("workspace", lambda: {"kind": "calendar_upcoming", "events": calendar_upcoming(days, limit)})
                elif action == "calendar_search":
                    query = str(args.get("query", "")); days = int(args.get("days", 180))
                    self._run_async("workspace", lambda: {"kind": "calendar_search", "events": calendar_search(query, days)})
                elif action == "calendar_create_event":
                    summary, start, end = str(args.get("summary", "")), str(args.get("start", "")), str(args.get("end", ""))
                    tz = str(args.get("timezone_name", "Asia/Kolkata"))
                    preview = f"Title: {summary}\nStart: {start}\nEnd: {end}\nTimezone: {tz}\nLocation: {args.get('location', '')}"
                    if self._ask_yes_no("Add Google Calendar event?", "Review and confirm this event.\n\n" + preview):
                        self._run_async("workspace", lambda: {"kind": "calendar_create_event", "event": calendar_create_event(summary, start, end, tz, location=str(args.get("location", "")), description=str(args.get("description", "")), confirmed=True)})
                    else:
                        self.speech.say("Calendar event cancelled.")
                elif action == "gmail_compose":
                    recipient = str(args.get("recipient", "")); subject = str(args.get("subject", "")); instructions = str(args.get("instructions", ""))
                    if not self._ask_yes_no("Prepare Gmail draft?", f"Arthur will send these drafting instructions to Gemini as text, then enter a draft into your Gmail window.\n\nTo: {recipient}\nSubject: {subject}\nInstructions: {instructions}\n\nNo email will be sent by this step. Continue?"):
                        self.speech.say("Email draft cancelled.")
                    else:
                        def prepare_gmail_draft():
                            body = self.gemini.ask_text("Write only the body of a professional email. Do not invent factual details. User instructions: " + instructions)
                            message = compose_gmail_gui(recipient, subject, body, send=False)
                            return {"kind": "gmail_compose", "recipient": recipient, "subject": subject, "body_preview": body[:2000], "message": message}
                        self._run_async("workspace", prepare_gmail_draft)
                elif action == "gmail_send_current":
                    if self._ask_yes_no("Confirm email send", "Confirm that you have reviewed the recipient, subject, and full body in the active Gmail draft. Arthur will issue Ctrl+Enter to send the current draft. This action cannot be undone. Send now?"):
                        def send_current():
                            title = activate_window("gmail", timeout=8)
                            import pyautogui
                            pyautogui.hotkey("ctrl", "enter")
                            return {"kind": "gmail_send_current", "message": f"Issued Ctrl+Enter in {title!r}. Verify Gmail's Sent state to confirm delivery."}
                        self._run_async("workspace", send_current)
                    else:
                        self.speech.say("Email send cancelled. The draft remains open.")
                elif action == "word_write":
                    text_to_write = str(args.get("text", ""))
                    if not self._ask_yes_no("Create Word document?", "Arthur will open Microsoft Word, create a new document, and paste this text. It will not save or share the document. Continue?\n\n" + text_to_write[:1200]):
                        self.speech.say("Word document creation cancelled.")
                    else:
                        self._run_async("workspace", lambda: {"kind": "word_write", "message": word_write_document(text_to_write)})
                elif action == "whatsapp_compose":
                    contact, body = str(args.get("contact", "")), str(args.get("message", ""))
                    if not self._ask_yes_no("Prepare WhatsApp message?", f"Arthur will open WhatsApp Web and enter a draft. It will NOT send it. Verify the selected contact in WhatsApp before sending.\n\nContact: {contact}\nMessage: {body[:1500]}\n\nContinue?"):
                        self.speech.say("WhatsApp draft cancelled.")
                    else:
                        self._run_async("workspace", lambda: {"kind": "whatsapp_compose", "contact": contact, "message_preview": body[:1200], "message": compose_whatsapp_gui(contact, body, send=False)})
                elif action == "whatsapp_send_current":
                    if self._ask_yes_no("Confirm WhatsApp send", "Confirm that the visible WhatsApp chat title matches the intended contact and the complete message is correct. Arthur will press Enter to send the current message. Continue?"):
                        self._run_async("workspace", lambda: {"kind": "whatsapp_send_current", "message": send_current_whatsapp(confirmed_send=True)})
                    else:
                        self.speech.say("WhatsApp send cancelled. The draft remains unsent.")
                elif action == "type_into_window":
                    target, text_to_type = str(args.get("target", "")), str(args.get("text", ""))
                    if self._ask_yes_no("Paste dictated text?", f"Paste text into the {target} window without submitting it? Review the destination first.\n\n{text_to_type[:1000]}"):
                        self._run_async("workspace", lambda: {"kind": "type_into_window", "message": type_into_window(target, text_to_type)})
            except Exception as exc:
                messagebox.showerror("Arthur integration", str(exc))
                self.speech.say("That integration action failed. Please check the displayed error.")
            return

        if action == "general_query":
            self._submit_voice_text_ai(str(args.get("prompt", transcript)))
            return
        if action == "describe":
            self.describe_scene()
        elif action == "ocr":
            self.scan_document()
        elif action == "check_object":
            matches = [d for d in self.latest_detections if argument in d.label.casefold()]
            if matches:
                best = max(matches, key=lambda d: d.confidence)
                range_note = f", estimated {best.distance_m:.1f} metres away" if best.distance_m is not None else " (distance unavailable)"
                response = f"I can see a possible {best.label} on the {best.direction}{range_note}. Please verify visually; the detector can miss objects."
            else:
                response = f"I did not detect a {argument} in the current camera view. That does not prove it is absent; it may be outside the frame or missed by the detector."
            self._set_output(response)
            self.speech.say(response)
        elif action == "safety_on":
            self.safety_var.set(True)
            self.toggle_safety()
            self.speech.say("Safety alerts enabled." if self.safety_enabled else "Safety alerts remain off because metric depth is not ready.")
        elif action == "safety_off":
            self.safety_var.set(False)
            self.toggle_safety()
            self.speech.say("Safety alerts disabled.")
        elif action == "snapshot":
            self.save_snapshot()
        elif action == "screenshot":
            try:
                path = capture_screen(self.data_dir / "snapshots")
                message = f"Screenshot saved locally to {path}. It has not been uploaded. Say 'explain what is on my screen' to request an AI description."
                self._set_output(message)
                self.speech.say(message)
            except Exception as exc:
                messagebox.showerror("Screenshot failed", str(exc))
        elif action == "screen_describe":
            try:
                path = capture_screen(self.data_dir / "snapshots")
                if not self._ask_yes_no("Share screenshot with AI?", "To describe your screen, Arthur will send this screenshot to the configured Gemini service. It may contain private information. Continue?"):
                    message = f"Screenshot saved locally to {path}; AI upload cancelled."
                    self._set_output(message)
                    self.speech.say(message)
                else:
                    frame = image_file_to_bgr(path)
                    prompt = argument or "Describe the visible screen. Read prominent text and controls where possible, explain visible error messages if any, and distinguish observation from inference. Do not infer unseen content."
                    self._set_output("Sending the screenshot for the requested screen description…")
                    self._run_async("gemini", lambda: self.gemini.ask_about_frame(prompt, frame, False))
            except Exception as exc:
                messagebox.showerror("Screen description failed", str(exc))
        elif action == "screen_ocr":
            try:
                path = capture_screen(self.data_dir / "snapshots")
                frame = image_file_to_bgr(path)
                self.status_var.set("Reading screen text locally…")
                self._run_async("screen_ocr", lambda: read_document(frame))
            except Exception as exc:
                messagebox.showerror("Read screen failed", str(exc))
        elif action in {"youtube_search", "web_search", "open_website", "open_app", "open_folder", "open_latest_pdf"}:
            try:
                if action == "youtube_search":
                    response = search_youtube(argument)
                elif action == "web_search":
                    response = search_web(argument)
                elif action == "open_website":
                    response = open_website(argument)
                elif action == "open_app":
                    response = open_app(argument)
                elif action == "open_folder":
                    response = open_folder(argument, self.project_dir)
                else:
                    response = open_document(find_latest_pdf())
                self._set_output(response)
                self.speech.say(response)
            except Exception as exc:
                messagebox.showerror("Desktop action failed", str(exc))
                self.speech.say("The requested desktop action could not be completed. Please check the message on screen.")
        elif action == "open_document":
            chosen = filedialog.askopenfilename(parent=self.root, title="Choose a document to open",
                filetypes=[("Supported documents", "*.txt *.md *.pdf *.docx *.py *.js *.ts *.tsx *.java *.c *.cpp *.csv *.json *.html *.css *.log"), ("All files", "*.*")])
            if chosen:
                try:
                    response = open_document(Path(chosen))
                    self._set_output(response)
                    self.speech.say(response)
                except Exception as exc:
                    messagebox.showerror("Open document failed", str(exc))
        elif action == "document_search":
            chosen = filedialog.askopenfilename(parent=self.root, title=f"Choose a document to search for: {argument}",
                filetypes=[("Supported documents", "*.txt *.md *.pdf *.docx *.py *.js *.ts *.tsx *.java *.c *.cpp *.csv *.json *.html *.css *.log"), ("All files", "*.*")])
            if chosen:
                try:
                    matches = search_document(Path(chosen), argument, limit=25)
                    if not matches:
                        response = f"I did not find '{argument}' in {Path(chosen).name}. Scanned PDFs or images may need OCR first."
                    else:
                        response = f"Found '{argument}' in {Path(chosen).name}, {len(matches)} match(es) shown:\n" + "\n".join(f"{m.location}: {m.excerpt}" for m in matches)
                    self._set_output(response)
                    self.speech.say(response[:4500])
                except Exception as exc:
                    messagebox.showerror("Document search failed", str(exc))
        elif action == "internet_status":
            response = check_internet_connectivity()
            self._set_output(response)
            self.speech.say(response)
        elif action == "system_status":
            try:
                response = system_status()
                self._set_output(response)
                self.speech.say(response)
            except Exception as exc:
                messagebox.showerror("System status failed", str(exc))
        elif action == "find_word":
            if not self.latest_ocr:
                self.speech.say("Scan a page before searching for a word.")
            else:
                matches = find_word(self.latest_ocr, argument)
                response = (f"Found {argument} on lines " + ", ".join(str(n) for n, _ in matches[:10])) if matches else f"I did not find {argument} on the last scanned page."
                self._set_output(response)
                self.speech.say(response)
        elif action == "ask_ai":
            if argument:
                frame = self._require_frame()
                if frame is not None and self._ask_yes_no("Send image to Gemini?", "This voice command sends the current camera image and question to Gemini. Proceed?"):
                    self._run_async("gemini", lambda: self.gemini.ask_about_frame(argument, frame, False))
        elif action == "text_ai":
            self._submit_voice_text_ai(argument or transcript)
        elif action == "memory_save":
            if argument and self._ask_yes_no("Save local memory?", "Store this note locally? It will not be sent to the internet.\n\n" + argument):
                try:
                    memory_id = self.memory.add(argument)
                    message = f"Saved memory {memory_id} locally."
                    self._append_output(message)
                    self.speech.say(message)
                except Exception as exc:
                    messagebox.showerror("Memory save failed", str(exc))
        elif action == "memory_search":
            rows = self.memory.search(argument, limit=20)
            if not rows:
                message = "No matching local memories were found."
            else:
                message = "Here is what I remember locally: " + "; ".join(str(row["content"]) for row in rows[:10])
            self._set_output(message)
            self.speech.say(message[:5000])
        elif action == "memory_delete":
            if not argument:
                message = "Please give me a phrase from the memory you want deleted."
                self._append_output(message)
                self.speech.say(message)
            else:
                rows = self.memory.search(argument, limit=100)
                if not rows:
                    message = "No matching local memories were found."
                    self._append_output(message)
                    self.speech.say(message)
                elif self._ask_yes_no("Delete local memories?", f"Permanently delete {len(rows)} matching local memory entr(y/ies)?"):
                    deleted = self.memory.delete_matching(argument)
                    message = f"Deleted {deleted} local memory entr(y/ies)."
                    self._append_output(message)
                    self.speech.say(message)
        elif action == "email_send":
            response = ("Sending email is not enabled in this build: no authenticated email-provider integration is configured. "
                        "I can draft an email with 'write an email to ...', but you must review and send it through your email client.")
            self._set_output(response)
            self.speech.say(response)
            messagebox.showinfo("Email not sent", response)
        elif action == "wake_on":
            self.toggle_wake_word(enable=True)
        elif action == "wake_off":
            self.toggle_wake_word(enable=False)
        elif action == "wake_detected":
            self._on_wake_word_detected()
        elif action == "sign_start":
            self.toggle_sign_mode()
        elif action == "sign_stop":
            if self.sign_enabled:
                self._stop_sign_mode()
                self._append_output("Isolated-sign recognition stopped.")
                self.speech.say("Sign recognition stopped.")
            else:
                self.speech.say("Sign recognition is not active.")
        elif action == "cancel":
            self.speech.say("There is no cancellable action currently running. Use Exit or turn off the active feature to stop it.")
        elif action == "camera_stop":
            self._camera_explicitly_enabled = False
            self.worker.stop()
            self.latest_frame = None
            self.latest_detections = []
            self.speech.say("Camera off, sir.")
            self._append_output("Camera capture stopped by user request.")
        elif action == "camera_start":
            self._camera_explicitly_enabled = True
            self.worker.start()
            message = "Camera is on, sir. It will stay on until you ask me to turn it off."
            self._append_output(message)
            self.speech.say(message)
        elif action == "help":
            self.show_help()
        else:
            if self._ask_yes_no("Ask text-only AI?", "I did not recognize this as a local command. Send the transcribed words to Gemini as a text-only request? No camera or screen image will be sent."):
                self._submit_voice_text_ai(transcript)
            else:
                message = "Command cancelled. Open Help / controls or COMMAND_CATALOGUE.md to see the supported commands."
                self._append_output(message)
                self.speech.say(message)

    @staticmethod
    def _format_workspace_result(result) -> str:
        if not isinstance(result, dict):
            return str(result)
        kind = str(result.get("kind", "Google Workspace result"))
        if kind.startswith("gmail"):
            messages = result.get("messages", [])
            if not messages:
                return "No matching Gmail messages were found."
            lines = [f"{kind.replace('_', ' ').title()} — {len(messages)} message(s):"]
            for index, message in enumerate(messages[:20], 1):
                lines.append(f"{index}. {message.get('subject', '(no subject)')} | From: {message.get('from', '')} | {message.get('date', '')}\n   {message.get('body', message.get('snippet', ''))}")
            return "\n".join(lines)
        if kind == "gmail_read_message":
            message = result.get("message", {})
            return (f"Email from {message.get('from', '')}, dated {message.get('date', '')}. Subject: {message.get('subject', '(no subject)')}.\n\n"
                    + str(message.get("body", message.get("snippet", ""))))
        if kind.startswith("calendar") and "events" in result:
            events = result.get("events", [])
            if not events:
                return "No matching calendar events were found."
            return "Upcoming/search calendar events:\n" + "\n".join(
                f"{i}. {event.get('summary', '(no title)')} | {event.get('start', '')} to {event.get('end', '')} | {event.get('location', '')}"
                for i, event in enumerate(events[:30], 1))
        if kind == "calendar_create_event":
            event = result.get("event", {})
            return f"Calendar event created: {event.get('summary', '')}, {event.get('start', '')} to {event.get('end', '')}. {event.get('html_link', '')}"
        if kind == "places_search":
            places = result.get("places", []) or []
            if not places:
                return "No matching places were returned."
            return "Places found:\n" + "\n".join(f"{i}. {p.get('name', 'Unknown place')} — {p.get('address', '')}. {p.get('maps_url', '')}" for i, p in enumerate(places[:10], 1))
        if kind == "air_quality":
            info = result.get("air_quality", {}) or {}
            indexes = info.get("indexes", []) or []
            if not indexes:
                return f"Air-quality data was returned for {info.get('location', 'the requested location')}, but no index was available."
            return "Air quality: " + "; ".join(f"{i.get('name') or i.get('code')}: AQI {i.get('aqi', 'unavailable')} ({i.get('category', 'category unavailable')})" for i in indexes[:5])
        if kind == "pollen_forecast":
            pollen = result.get("pollen", {}) or {}
            return "Pollen forecast received. Daily forecasts: " + str(len(pollen.get("daily_info", []) or [])) + ". See the output panel for the full forecast details."
        if kind == "timezone_lookup":
            zone = result.get("timezone", {}) or {}
            return f"Time zone for {zone.get('location', 'the requested place')}: {zone.get('time_zone_name', '')} ({zone.get('time_zone_id', '')}). Approximate local time: {zone.get('local_time', 'unavailable')}."
        if kind == "translate":
            return str(result.get("translated_text", "No translation was returned."))
        if kind == "sentiment":
            return f"Sentiment analysis result: score {result.get('score', 'unavailable')}, magnitude {result.get('magnitude', 'unavailable')}."
        if kind == "entities":
            entities = result.get("entities", []) or []
            return "Recognized entities: " + (", ".join(str(e.get("name", "")) for e in entities[:20] if e.get("name")) or "none returned")
        if kind == "profile":
            profile = result.get("profile", {}) or {}
            return f"Google profile: {profile.get('name', '')}; {profile.get('email', '')}."
        if kind == "tasks_list":
            tasks = result.get("tasks", []) or []
            return "Google Tasks: " + ("; ".join(str(t.get("title", "Untitled task")) for t in tasks[:20]) if tasks else "no open tasks returned")
        if kind == "tasks_create":
            task = result.get("task", {}) or {}
            return f"Google Task created: {task.get('title', '')}."
        if kind == "meet_create":
            meeting = result.get("meeting", {}) or {}
            return f"Google Meet link created: {meeting.get('meeting_uri', '') or 'the API returned no meeting URL'}"
        if kind == "google_workspace_feature":
            return "Google Workspace request completed."
        if kind == "gmail_compose":
            return (f"{result.get('message', 'Gmail draft prepared.')}\n\nTo: {result.get('recipient', '')}\nSubject: {result.get('subject', '')}\n\nDraft body preview:\n{result.get('body_preview', '')}\n\nReview the complete draft in Gmail before saying 'send email'.")
        if kind in {"gmail_send_current", "whatsapp_send_current", "word_write", "type_into_window"}:
            return str(result.get("message", "The GUI action has completed. Inspect the target window to verify the result."))
        if kind == "whatsapp_compose":
            return (f"{result.get('message', 'WhatsApp message prepared.')}\n\nContact requested: {result.get('contact', '')}\nMessage preview: {result.get('message_preview', '')}\n\nVerify the visible chat title and text before saying 'send WhatsApp message'.")
        return str(result)

    def toggle_master_listening(self):
        """Master microphone toggle: OFF means no wake-word or conversation capture."""
        if self.wake_word_armed:
            self.toggle_wake_word(enable=False)
            self.listening_button.configure(text="Listening: OFF")
            self.conversation_active = False
            self._conversation_stop.set()
            self._camera_explicitly_enabled = False
            self.worker.stop()
            self.latest_frame = None
            self.latest_detections = []
            self.status_var.set("Camera off · listening disabled")
            return
        self.toggle_wake_word(enable=True, ask_confirmation=True)
        if self.wake_word_armed:
            self.listening_button.configure(text="Listening: ON")
            if self.face_recognition_enabled or self.gesture_enabled or self.depth_enabled or self.sign_enabled:
                self.worker.start()

    def toggle_wake_word(self, enable: bool | None = None, ask_confirmation: bool = True):
        """Arm/disarm the local wake model. The master toggle calls this method."""
        target = (not self.wake_word_armed) if enable is None else bool(enable)
        if not target:
            self.wake_word_armed = False
            self.conversation_active = False
            self._conversation_stop.set()
            listener, self.wake_word_listener = self.wake_word_listener, None
            if listener:
                listener.stop()
            self._append_output("Listening disabled. The microphone will not be monitored for a wake phrase.")
            self.status_var.set("Listening disabled")
            return
        if self.wake_word_armed:
            return
        model_value = os.getenv("WAKE_WORD_MODEL", "models/wakeword/hey_arthur.onnx").strip()
        model_path = Path(model_value)
        if not model_path.is_absolute():
            model_path = self.project_dir / model_path
        if not model_path.is_file():
            message = (f"No wake-word model was found at {model_path}. Set WAKE_WORD_MODEL in .env to your compatible ONNX model path.")
            self._set_output(message)
            messagebox.showinfo("Wake-word model not installed", message)
            return
        if ask_confirmation and not self._ask_yes_no("Enable listening?", "Arthur will monitor the microphone locally for the configured wake phrase while this toggle is ON. The camera remains off unless you request it. Enable listening?"):
            return
        try:
            from visionguide.wake_word import WakeWordListener
            threshold = float(os.getenv("WAKE_WORD_THRESHOLD", "0.60"))
            self.wake_word_armed = True
            self._conversation_stop.clear()
            self.wake_word_listener = WakeWordListener(
                model_path=model_path, threshold=threshold,
                on_detected=lambda: self._async_messages.put(("wake_detected", None)),
                on_error=lambda exc: self._async_messages.put(("wake_error", str(exc))),
            )
            self.wake_word_listener.start()
            self._set_output("Listening enabled. Say the configured wake phrase to start a conversation. The camera is off until needed.")
            self.status_var.set("Wake-word listening active · camera off")
        except Exception as exc:
            self.wake_word_armed = False
            self.wake_word_listener = None
            messagebox.showerror("Could not enable listening", str(exc))

    def _on_wake_word_detected(self):
        if not self.wake_word_armed or self._closed or self.conversation_active:
            return
        self.wake_word_listener = None  # detector exited and released its microphone stream
        self.conversation_active = True
        self._conversation_stop.clear()
        self._conversation_command_done.set()
        self.status_var.set("Arthur is active · 30-second inactivity timeout")
        self._append_output("Wake phrase detected. Continuous conversation is active.")
        self.speech.say("Yes, sir?")
        self._run_async("conversation_loop", self._conversation_loop)

    def _conversation_loop(self):
        from visionguide.voice_commands import record_and_transcribe
        last_activity = time.monotonic()
        # Wait for Arthur's acknowledgement to finish before recording, to avoid transcribing TTS.
        self.speech.wait_until_idle(timeout=8.0)
        while self.wake_word_armed and self.conversation_active and not self._conversation_stop.is_set() and not self._closed:
            if time.monotonic() - last_activity >= 30.0:
                self._async_messages.put(("conversation_end", "timeout"))
                return "timeout"
            try:
                transcript = record_and_transcribe(duration_seconds=5.0, model_name="base", stop_event=self._conversation_stop)
            except Exception as exc:
                self._async_messages.put(("conversation_error", str(exc)))
                return "error"
            if self._conversation_stop.is_set() or not self.conversation_active:
                return "stopped"
            transcript = str(transcript).strip()
            if not transcript:
                continue
            last_activity = time.monotonic()
            self._conversation_command_done.clear()
            self._async_messages.put(("conversation_transcript", transcript))
            # Process utterances serially so consecutive chunks do not race command execution.
            while not self._conversation_command_done.wait(0.1):
                if self._conversation_stop.is_set() or not self.conversation_active or self._closed:
                    return "stopped"
            self.speech.wait_until_idle(timeout=20.0)
        return "stopped"

    def _restart_wake_word_listener(self):
        if self.wake_word_armed and not self._closed and self.wake_word_listener is None and not self.conversation_active:
            try:
                from visionguide.wake_word import WakeWordListener
                model_value = os.getenv("WAKE_WORD_MODEL", "models/wakeword/hey_arthur.onnx").strip()
                model_path = Path(model_value)
                if not model_path.is_absolute():
                    model_path = self.project_dir / model_path
                threshold = float(os.getenv("WAKE_WORD_THRESHOLD", "0.60"))
                self.wake_word_listener = WakeWordListener(
                    model_path=model_path, threshold=threshold,
                    on_detected=lambda: self._async_messages.put(("wake_detected", None)),
                    on_error=lambda exc: self._async_messages.put(("wake_error", str(exc))),
                )
                self.wake_word_listener.start()
                self.status_var.set("Wake-word listening active · camera off")
            except Exception as exc:
                self.wake_word_armed = False
                self.listening_button.configure(text="Listening: OFF")
                self.wake_word_listener = None
                self._append_output("Wake-word listener could not restart: " + str(exc))
                self.speech.say("Listening stopped because the wake-word detector could not restart.")

    def show_help(self):
        messagebox.showinfo("Arthur controls",
            "The camera starts silently. Nothing is spoken unless you request an action or explicitly enable safety alerts.\n\n"
            "Voice command — records only after you press the button and approve the recording.\n"
            "Browser — 'Open YouTube', 'Search YouTube for Python tutorials', 'Search Google for binary trees'.\n"
            "Apps — 'Open Calculator', 'Open Notepad', 'Open VS Code', 'Open File Explorer'; only allowlisted apps can launch.\n"
            "Screen — 'Take a screenshot', 'Explain what is on my screen' (separate AI-upload confirmation), 'Read the text on my screen' (local OCR).\n"
            "Documents — 'Open my document', 'Open my document and find the word algorithm'; supports text/code files and, with dependencies, PDF/DOCX.\n"
            "Vision — 'Describe the scene', 'Is there a TV?', 'Read the text', 'Capture photo'. Camera descriptions are on request.\n"
            "Input — one unified 'Air virtual keyboard…' works system-wide in the currently focused Windows app. Use mouse clicks, hand gestures, or voice commands such as 'type exactly hello world'; literal text is not submitted automatically. Enable Hand gestures for pointer movement, pinch-click, scrolling and tab switching.\n"
            "Writing — 'Write an email to my professor' can prepare a Gemini-assisted draft. Sending requires an authenticated provider, final-content review and explicit confirmation.\n"
            "Memory — explicitly save, search, or delete local notes. Delete/save actions require confirmation.\n"
            "Listening — use the Listening ON/OFF master toggle. Say the configured wake phrase to begin continuous conversation; 30 seconds without speech returns to wake mode.\n"
            "Camera — off by default; turn it on explicitly to keep it running, or request a camera task to open it temporarily.\n"
            "Sign language — current included classifier is isolated-label only and requires training; it is not continuous sentence translation. See CONTINUOUS_ISL.md.\n"
            "Safety — proactive depth alerts are OFF by default. Depth/motion estimates are not validated navigation or collision avoidance.\n\n"
            "See COMMAND_CATALOGUE.md for a wider list of supported commands, command aliases, architecture details and integration setup.")

    def run(self):
        self.root.mainloop()

    def close(self):
        if self._closed: return
        self._closed = True
        self.worker.stop()
        if self.navigation_session:
            try: self.navigation_session.stop()
            except Exception: pass
            self.navigation_session = None
        if self.depth_worker:
            self.depth_worker.stop()
        if self.gesture_mouse:
            try: self.gesture_mouse.close()
            except Exception: pass
        if self.system_virtual_keyboard is not None:
            try: self.system_virtual_keyboard.close()
            except Exception: pass
            self.system_virtual_keyboard = None
        self._stop_sign_mode()
        self.timer_manager.close()
        self.wake_word_armed = False
        self.conversation_active = False
        self._conversation_stop.set()
        if self.wake_word_listener:
            try: self.wake_word_listener.stop()
            except Exception: pass
        self.wake_word_listener = None
        self.speech.close()
        self.root.destroy()
