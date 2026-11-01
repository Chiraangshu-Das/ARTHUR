from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import cv2
import numpy as np


class FaceMemory:
    """Opt-in local face detection/recognition using OpenCV LBPH.

    Enrolled face samples and the recognizer model remain on disk under data/faces.
    This is a basic lighting-sensitive prototype; do not use it for access control.
    """
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir) / "faces"
        self.samples_dir = self.data_dir / "samples"
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.data_dir / "recognizer.yml"
        self.people_path = self.data_dir / "people.json"
        self.embeddings_path = self.data_dir / "embeddings.json"
        self.embedding_model_name = os.getenv("VISIONGUIDE_FACE_EMBEDDING_MODEL", "Facenet512").strip() or "Facenet512"
        try:
            self.embeddings: dict[str, list[list[float]]] = json.loads(self.embeddings_path.read_text(encoding="utf-8"))
            if not isinstance(self.embeddings, dict):
                self.embeddings = {}
        except (OSError, json.JSONDecodeError):
            self.embeddings = {}
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(str(cascade_path))
        self.recognizer = None
        self.people: dict[str, dict] = self._read_people()
        self.available = hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create")
        # DeepFace is an optional embedding backend. LBPH remains the offline fallback;
        # enrolled local embeddings are fused with it when the package/model is available.
        try:
            from importlib.util import find_spec
            self.deepface_installed = find_spec("deepface") is not None
        except (ImportError, ValueError):
            self.deepface_installed = False
        self.deepface_model_ready = False
        if self.available:
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            if self.model_path.exists():
                try:
                    self.recognizer.read(str(self.model_path))
                except Exception:
                    self.recognizer = cv2.face.LBPHFaceRecognizer_create()

    def _read_people(self) -> dict[str, dict]:
        try:
            data = json.loads(self.people_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_people(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.people_path.write_text(json.dumps(self.people, indent=2), encoding="utf-8")

    def detect_faces(self, frame) -> list[tuple[int, int, int, int, np.ndarray]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        boxes = self.cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(55, 55))
        results = []
        for x, y, w, h in boxes:
            crop = gray[y:y + h, x:x + w]
            crop = cv2.resize(crop, (160, 160), interpolation=cv2.INTER_CUBIC)
            results.append((int(x), int(y), int(w), int(h), crop))
        return results

    @staticmethod
    def safe_slug(name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_")
        if not slug:
            raise ValueError("Enter a name containing at least one letter or number.")
        return slug[:48]

    def enroll(self, name: str, crops: list[np.ndarray]) -> int:
        if not self.available:
            raise RuntimeError("Face recognition requires opencv-contrib-python, not opencv-python alone.")
        name = " ".join(name.split()).strip()
        slug = self.safe_slug(name)
        if len(crops) < 5:
            raise ValueError("At least five face samples are required. Try enrolling in steady, even light.")
        person_dir = self.samples_dir / slug
        person_dir.mkdir(parents=True, exist_ok=True)
        existing_files = list(person_dir.glob("*.png"))
        for index, crop in enumerate(crops, start=len(existing_files) + 1):
            normalized = cv2.resize(crop, (160, 160))
            cv2.imwrite(str(person_dir / f"sample-{index:03d}.png"), normalized)
        label_id = next((int(k) for k, v in self.people.items() if v.get("slug") == slug), None)
        if label_id is None:
            used = [int(k) for k in self.people.keys() if str(k).isdigit()]
            label_id = max(used, default=0) + 1
        self.people[str(label_id)] = {"name": name, "slug": slug}
        self._write_people()
        # Embeddings are produced only when DeepFace is installed, and stay local.
        if self.deepface_installed:
            successful: list[list[float]] = []
            for crop in crops:
                try:
                    vector = self._compute_embedding(crop)
                    if vector is not None:
                        successful.append(vector)
                except Exception as exc:
                    print(f"[FaceMemory] DeepFace embedding unavailable; retaining LBPH fallback: {exc}")
                    break
            if successful:
                # Re-enrollment improves the local template set without losing previous angles.
                self.embeddings[slug] = (self.embeddings.get(slug, []) + successful)[-50:]
                self._write_embeddings()
        self.retrain()
        return len(crops)

    def _write_embeddings(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_path.write_text(json.dumps(self.embeddings, separators=(",", ":")), encoding="utf-8")

    def _compute_embedding(self, crop: np.ndarray) -> list[float] | None:
        from deepface import DeepFace
        face = np.asarray(crop)
        if face.ndim == 2:
            face = cv2.cvtColor(face, cv2.COLOR_GRAY2BGR)
        elif face.ndim == 3 and face.shape[2] == 4:
            face = cv2.cvtColor(face, cv2.COLOR_BGRA2BGR)
        face = cv2.resize(face, (160, 160))
        result = DeepFace.represent(
            img_path=face,
            model_name=self.embedding_model_name,
            detector_backend="skip",
            enforce_detection=False,
            normalization="Facenet",
        )
        if not result or not result[0].get("embedding"):
            return None
        self.deepface_model_ready = True
        return [float(value) for value in result[0]["embedding"]]

    def retrain(self) -> None:
        if not self.available:
            raise RuntimeError("Face recognition requires opencv-contrib-python.")
        faces, labels = [], []
        for key, person in self.people.items():
            slug = person.get("slug", "")
            person_dir = self.samples_dir / slug
            if not person_dir.is_dir():
                continue
            for path in person_dir.glob("*.png"):
                image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    faces.append(cv2.resize(image, (160, 160)))
                    labels.append(int(key))
        if not faces:
            self.model_path.unlink(missing_ok=True)
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            return
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.recognizer.train(faces, np.array(labels, dtype=np.int32))
        self.recognizer.write(str(self.model_path))

    def recognize(self, crop: np.ndarray, threshold: float = 72.0) -> tuple[str, float] | None:
        """Return only enrolled matches; use DeepFace embeddings with LBPH as a local fallback.

        If both backends produce a confident but conflicting identity, return Unknown instead
        of forcing a potentially incorrect personalization decision.
        """
        lbph_match: tuple[str, float] | None = None
        if self.available and self.recognizer is not None and self.model_path.exists():
            try:
                label, confidence = self.recognizer.predict(cv2.resize(crop, (160, 160)))
                person = self.people.get(str(int(label)))
                if confidence <= threshold and person:
                    lbph_match = (str(person.get("name", "Known person")), float(confidence))
            except cv2.error:
                pass

        deepface_match = self._recognize_deepface(crop, float(os.getenv("VISIONGUIDE_FACE_COSINE_THRESHOLD", "0.30")))
        if deepface_match and lbph_match:
            if deepface_match[0].casefold() == lbph_match[0].casefold():
                return deepface_match[0], min(deepface_match[1], lbph_match[1])
            return ("Unknown face", float(deepface_match[1]))
        if deepface_match:
            return deepface_match
        if lbph_match:
            return lbph_match
        return None

    def list_people(self) -> list[str]:
        return sorted(str(value.get("name", "")) for value in self.people.values() if value.get("name"))

    def delete_person(self, name: str) -> bool:
        target = name.casefold().strip()
        match = next(((key, value) for key, value in self.people.items()
                      if str(value.get("name", "")).casefold() == target), None)
        if not match:
            return False
        key, person = match
        self.people.pop(key, None)
        slug = str(person.get("slug", ""))
        self.embeddings.pop(slug, None)
        shutil.rmtree(self.samples_dir / slug, ignore_errors=True)
        self._write_people()
        self._write_embeddings()
        self.retrain()
        return True

    def _recognize_deepface(self, crop: np.ndarray, threshold: float = 0.30) -> tuple[str, float] | None:
        if not self.deepface_installed or not self.embeddings:
            return None
        try:
            vector = np.asarray(self._compute_embedding(crop), dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            if not norm:
                return None
            vector /= norm
            best: tuple[str, float] | None = None
            for key, person in self.people.items():
                slug = str(person.get("slug", ""))
                for stored in self.embeddings.get(slug, []):
                    known = np.asarray(stored, dtype=np.float32)
                    known_norm = float(np.linalg.norm(known))
                    if not known_norm or known.shape != vector.shape:
                        continue
                    distance = 1.0 - float(np.dot(vector, known / known_norm))
                    if best is None or distance < best[1]:
                        best = (str(person.get("name", "Known person")), distance)
            if best and best[1] <= max(0.05, min(float(threshold), 0.60)):
                return best
        except Exception as exc:
            print(f"[FaceMemory] DeepFace recognition fell back to LBPH: {exc}")
        return None

    def is_enrolled_name(self, name: str) -> bool:
        return any(str(person.get("name", "")).casefold() == str(name).casefold() for person in self.people.values())

    def profile_slug(self, name: str) -> str | None:
        return next((str(person.get("slug", "")) for person in self.people.values()
                     if str(person.get("name", "")).casefold() == str(name).casefold()), None)
