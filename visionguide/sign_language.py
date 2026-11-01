
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision.models.video import swin3d_s


logger = logging.getLogger(__name__)


class ISLRecognizer:
    """
    Isolated Indian Sign Language recognizer using a fine-tuned Swin3D-S model.

    Input:
        OpenCV BGR camera frames.

    Output:
        process(frame) -> (label, confidence) or None

    The model performs inference on a background thread so that camera/UI
    refresh operations are not blocked by model execution.
    """

    SEQUENCE_LENGTH = 32
    IMAGE_SIZE = 224
    RESIZE_SHORT_EDGE = 256

    CONFIDENCE_THRESHOLD = 0.70
    INFERENCE_INTERVAL = 0.50

    CHECKPOINT_RELATIVE_PATH = (
        Path("models")
        / "isl"
        / "swin3d_s"
        / "ISL_best_model.pt"
    )

    DATASET_RELATIVE_PATH = (
        Path("data")
        / "isl_dataset"
        / "ProcessedData_vivit"
    )

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()

        self.checkpoint_path = (
            self.project_dir / self.CHECKPOINT_RELATIVE_PATH
        )

        self.dataset_path = (
            self.project_dir / self.DATASET_RELATIVE_PATH
        )

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.frames: deque[np.ndarray] = deque(
            maxlen=self.SEQUENCE_LENGTH
        )

        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

        self.pending_sequence: Optional[list[np.ndarray]] = None
        self.latest_result: Optional[tuple[str, float]] = None

        self.last_inference_time = 0.0
        self.running = True
        self.model_ready = False
        self.error: Optional[str] = None

        self.labels = self._load_labels()

        self.model = self._load_model()

        self.model.eval()

        self.model_ready = True

        self.worker = threading.Thread(
            target=self._inference_worker,
            name="ISL-Swin3D-Inference",
            daemon=True,
        )

        self.worker.start()

        logger.info(
            "ISL Swin3D recognizer initialized on %s with %d classes.",
            self.device,
            len(self.labels),
        )

    # ---------------------------------------------------------
    # LABEL LOADING
    # ---------------------------------------------------------

    def _load_labels(self) -> list[str]:
        """
        Load the class labels.

        The original training pipeline used alphabetically sorted dataset
        folder names. Prefer a model-specific label file if available;
        otherwise reconstruct the same alphabetical ordering.
        """

        possible_label_files = [
            self.checkpoint_path.parent / "labels.json",
            self.checkpoint_path.parent / "class_names.json",
            self.project_dir / "models" / "isl_labels.json",
        ]

        for label_file in possible_label_files:
            if not label_file.is_file():
                continue

            try:
                with label_file.open("r", encoding="utf-8") as file:
                    data = json.load(file)

                if isinstance(data, list):
                    labels = [str(item) for item in data]

                elif isinstance(data, dict):
                    if all(str(key).isdigit() for key in data):
                        labels = [
                            str(data[key])
                            for key in sorted(data, key=lambda x: int(x))
                        ]
                    elif all(
                        isinstance(value, int)
                        for value in data.values()
                    ):
                        labels = [
                            label
                            for label, _ in sorted(
                                data.items(),
                                key=lambda item: item[1],
                            )
                        ]
                    else:
                        continue
                else:
                    continue

                if len(labels) == 76:
                    logger.info(
                        "Loaded %d ISL labels from %s",
                        len(labels),
                        label_file,
                    )
                    return labels

                logger.warning(
                    "Ignoring label file %s: expected 76 labels, found %d.",
                    label_file,
                    len(labels),
                )

            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                logger.exception(
                    "Could not read ISL label file: %s",
                    label_file,
                )

        if not self.dataset_path.is_dir():
            raise FileNotFoundError(
                "ISL dataset directory not found. Expected:\n"
                f"{self.dataset_path}\n"
                "The dataset is required to reconstruct the training "
                "class ordering."
            )

        labels = sorted(
            folder.name
            for folder in self.dataset_path.iterdir()
            if folder.is_dir()
        )

        if len(labels) != 76:
            raise RuntimeError(
                "Incorrect number of ISL classes.\n"
                f"Expected: 76\n"
                f"Found: {len(labels)}\n"
                f"Dataset: {self.dataset_path}"
            )

        logger.info(
            "Reconstructed %d alphabetically sorted ISL labels.",
            len(labels),
        )

        return labels

    # ---------------------------------------------------------
    # MODEL LOADING
    # ---------------------------------------------------------

    def _load_model(self) -> torch.nn.Module:
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError(
                "Swin3D checkpoint not found:\n"
                f"{self.checkpoint_path}"
            )

        logger.info("Loading Swin3D-S checkpoint...")

        # The checkpoint was trained with 76 output classes.
        model = swin3d_s(
            weights=None,
            num_classes=len(self.labels),
        )

        try:
            checkpoint = torch.load(
                self.checkpoint_path,
                map_location="cpu",
                weights_only=True,
            )
        except TypeError:
            # Compatibility fallback for older PyTorch releases.
            checkpoint = torch.load(
                self.checkpoint_path,
                map_location="cpu",
            )

        # Support common checkpoint container formats.
        if isinstance(checkpoint, dict):
            if "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"]
            elif "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
            elif "model" in checkpoint and isinstance(
                checkpoint["model"], dict
            ):
                state_dict = checkpoint["model"]
            else:
                state_dict = checkpoint
        else:
            raise RuntimeError(
                "Unsupported Swin3D checkpoint format."
            )

        converted_state_dict = {}

        for key, value in state_dict.items():
            new_key = key

            if new_key.startswith("module."):
                new_key = new_key[len("module."):]

            # Training checkpoint classifier naming differs from
            # torchvision's Swin3D classifier naming.
            if new_key.startswith("classification_head.0."):
                new_key = new_key.replace(
                    "classification_head.0.",
                    "head.",
                    1,
                )

            converted_state_dict[new_key] = value

        # Strict loading ensures that the checkpoint architecture
        # actually matches the expected Swin3D-S model.
        model.load_state_dict(
            converted_state_dict,
            strict=True,
        )

        model.to(self.device)

        logger.info(
            "Swin3D-S checkpoint loaded successfully. "
            "Parameters: %s",
            f"{sum(p.numel() for p in model.parameters()):,}",
        )

        return model

    # ---------------------------------------------------------
    # VIDEO PREPROCESSING
    # ---------------------------------------------------------

    @staticmethod
    def _resize_and_crop(frame: np.ndarray) -> Image.Image:
        """
        Apply the training-time VivitImageProcessor spatial transforms:

        1. Resize shortest edge to 256.
        2. Preserve aspect ratio.
        3. Center crop to 224 x 224.
        4. Use bilinear interpolation.
        """

        height, width = frame.shape[:2]

        if height <= 0 or width <= 0:
            raise ValueError("Invalid frame dimensions.")

        scale = (
            ISLRecognizer.RESIZE_SHORT_EDGE
            / min(height, width)
        )

        resized_width = int(round(width * scale))
        resized_height = int(round(height * scale))

        image = Image.fromarray(frame)

        image = image.resize(
            (resized_width, resized_height),
            resample=Image.Resampling.BILINEAR,
        )

        left = (resized_width - ISLRecognizer.IMAGE_SIZE) // 2
        top = (resized_height - ISLRecognizer.IMAGE_SIZE) // 2

        right = left + ISLRecognizer.IMAGE_SIZE
        bottom = top + ISLRecognizer.IMAGE_SIZE

        image = image.crop(
            (left, top, right, bottom)
        )

        return image

    def _preprocess_sequence(
        self,
        frames: list[np.ndarray],
    ) -> torch.Tensor:
        """
        Convert 32 BGR frames into the Swin3D input format:

            [1, 3, 32, 224, 224]

        Training preprocessing:
            Rescale by 1/127.5
            Zero-center to [-1, 1]
            No additional normalization
        """

        if len(frames) != self.SEQUENCE_LENGTH:
            raise ValueError(
                f"Expected {self.SEQUENCE_LENGTH} frames, "
                f"received {len(frames)}."
            )

        processed_frames = []

        for bgr_frame in frames:
            if (
                bgr_frame is None
                or not isinstance(bgr_frame, np.ndarray)
                or bgr_frame.ndim != 3
                or bgr_frame.shape[2] != 3
            ):
                raise ValueError("Invalid camera frame.")

            # OpenCV BGR -> RGB.
            rgb_frame = cv2.cvtColor(
                bgr_frame,
                cv2.COLOR_BGR2RGB,
            )

            image = self._resize_and_crop(rgb_frame)

            image_array = np.asarray(
                image,
                dtype=np.float32,
            )

            # Match the supplied VivitImageProcessor configuration.
            image_array = image_array / 127.5
            image_array = image_array - 1.0

            processed_frames.append(image_array)

        # [T, H, W, C]
        video = np.stack(
            processed_frames,
            axis=0,
        )

        # [C, T, H, W]
        video = np.transpose(
            video,
            (3, 0, 1, 2),
        )

        # [1, C, T, H, W]
        video = np.expand_dims(
            video,
            axis=0,
        )

        return torch.from_numpy(
            np.ascontiguousarray(video)
        ).to(
            device=self.device,
            dtype=torch.float32,
        )

    # ---------------------------------------------------------
    # MODEL INFERENCE
    # ---------------------------------------------------------

    def _predict(
        self,
        frames: list[np.ndarray],
    ) -> tuple[str, float]:

        video_tensor = self._preprocess_sequence(frames)

        with torch.inference_mode():
            logits = self.model(video_tensor)

            probabilities = F.softmax(
                logits,
                dim=1,
            )

            confidence_tensor, predicted_tensor = (
                torch.max(probabilities, dim=1)
            )

        predicted_index = int(predicted_tensor.item())
        confidence = float(confidence_tensor.item())

        if predicted_index >= len(self.labels):
            raise RuntimeError(
                f"Model returned invalid class index: {predicted_index}"
            )

        label = self.labels[predicted_index]

        if confidence < self.CONFIDENCE_THRESHOLD:
            return "Uncertain sign", confidence

        return label, confidence

    # ---------------------------------------------------------
    # BACKGROUND INFERENCE WORKER
    # ---------------------------------------------------------

    def _inference_worker(self) -> None:
        """
        Perform model inference outside the application/UI thread.

        Only one inference job is processed at a time.
        """

        while True:
            with self.condition:
                while (
                    self.running
                    and self.pending_sequence is None
                ):
                    self.condition.wait()

                if not self.running:
                    break

                sequence = self.pending_sequence
                self.pending_sequence = None

            if sequence is None:
                continue

            try:
                result = self._predict(sequence)

                with self.condition:
                    self.latest_result = result
                    self.error = None

            except Exception as exc:
                logger.exception(
                    "ISL inference failed."
                )

                with self.condition:
                    self.error = str(exc)
                    self.latest_result = (
                        "Uncertain sign",
                        0.0,
                    )

    # ---------------------------------------------------------
    # PUBLIC APPLICATION INTERFACE
    # ---------------------------------------------------------

    def process(
        self,
        frame: np.ndarray,
    ) -> Optional[tuple[str, float]]:
        """
        Accept one OpenCV BGR camera frame.

        This method does not perform model inference directly.
        It collects frames and schedules inference in the background.

        Returns:
            (label, confidence) when a result is available.
            None while collecting the first sequence.
        """

        if not self.running or not self.model_ready:
            return None

        if (
            frame is None
            or not isinstance(frame, np.ndarray)
            or frame.ndim != 3
            or frame.shape[2] != 3
        ):
            return None

        current_time = time.monotonic()

        with self.condition:
            # Copy the frame because the camera worker may reuse
            # or modify its original frame buffer.
            self.frames.append(frame.copy())

            if (
                len(self.frames) == self.SEQUENCE_LENGTH
                and self.pending_sequence is None
                and current_time - self.last_inference_time
                >= self.INFERENCE_INTERVAL
            ):
                self.pending_sequence = list(self.frames)

                self.last_inference_time = current_time

                self.condition.notify()

            return self.latest_result

    # ---------------------------------------------------------
    # CLEANUP
    # ---------------------------------------------------------

    def close(self) -> None:
        """
        Stop the inference worker and release model resources.
        """

        with self.condition:
            if not self.running:
                return

            self.running = False
            self.pending_sequence = None

            self.condition.notify_all()

        if (
            hasattr(self, "worker")
            and self.worker.is_alive()
            and threading.current_thread() is not self.worker
        ):
            self.worker.join(timeout=5.0)

        if hasattr(self, "model"):
            del self.model

        if self.device.type == "cuda":
            torch.cuda.empty_cache()

        self.model_ready = False

        logger.info("ISL recognizer closed.")
