
from __future__ import annotations

import argparse
import gc
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision.models.video import swin3d_s
from torchvision.transforms import functional as TF
from torchvision.transforms import InterpolationMode


ROOT = Path(__file__).resolve().parents[1]

CHECKPOINT = (
    ROOT / "models" / "isl" / "swin3d_s" / "ISL_best_model.pt"
)

DATASET = ROOT / "data" / "isl_dataset" / "ProcessedData_vivit"

NUM_FRAMES = 32
IMAGE_SIZE = 224
RESIZE_SIZE = 256

MEAN = [0.5, 0.5, 0.5]
STD = [0.5, 0.5, 0.5]

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


def load_labels():
    labels = sorted(
        p.name for p in DATASET.iterdir() if p.is_dir()
    )

    if len(labels) != 76:
        raise RuntimeError(
            f"Expected 76 classes, found {len(labels)}"
        )

    return labels



def load_model():
    if not CHECKPOINT.exists():
        raise FileNotFoundError(CHECKPOINT)

    print("Loading checkpoint:", CHECKPOINT)
    print("Device:", DEVICE)

    checkpoint = torch.load(
        CHECKPOINT,
        map_location="cpu",
        weights_only=True
    )

    # Initialize Swin3D-S with the checkpoint's 76 classes.
    model = swin3d_s(
        weights=None,
        num_classes=76
    )

    mapped = {}

    for key, value in checkpoint.items():

        if key.startswith("base_model."):
            new_key = key[len("base_model."):]

        elif key.startswith("classification_head.0."):
            new_key = "head." + key[len("classification_head.0."):]

        else:
            raise RuntimeError(
                f"Unexpected checkpoint key: {key}"
            )

        mapped[new_key] = value

    model.load_state_dict(mapped, strict=True)

    model.eval()
    model.to(DEVICE)

    print("Checkpoint loaded successfully.")
    print("Parameters:", sum(p.numel() for p in model.parameters()))
    print("Output classes:", model.head.out_features)

    return model

def decode_video(video_path: Path):
    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        raise RuntimeError(
            f"Cannot open video: {video_path}"
        )

    frames = []

    try:
        while len(frames) < NUM_FRAMES:

            success, frame = capture.read()

            if not success:
                break

            frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            frames.append(frame)

    finally:
        capture.release()

    if len(frames) < NUM_FRAMES:
        raise RuntimeError(
            f"Video has only {len(frames)} readable frames. "
            f"Expected at least {NUM_FRAMES}."
        )

    return frames


def preprocess_video(frames):
    processed_frames = []

    for frame in frames[:NUM_FRAMES]:

        image = Image.fromarray(frame)

        # Resize shortest edge to 256.
        image = TF.resize(
            image,
            RESIZE_SIZE,
            interpolation=InterpolationMode.BILINEAR
        )

        # Center crop to 224 x 224.
        image = TF.center_crop(
            image,
            [IMAGE_SIZE, IMAGE_SIZE]
        )

        # Convert to tensor and normalize.
        tensor = TF.to_tensor(image)

        tensor = TF.normalize(
            tensor,
            mean=MEAN,
            std=STD
        )

        processed_frames.append(tensor)

    # [T, C, H, W]
    video_tensor = torch.stack(processed_frames)

    # [C, T, H, W]
    video_tensor = video_tensor.permute(1, 0, 2, 3)

    # [B, C, T, H, W]
    video_tensor = video_tensor.unsqueeze(0)

    return video_tensor.to(DEVICE)


def predict(model, video_path, labels):
    print("\nReading video:", video_path)

    frames = decode_video(video_path)

    print("Frames used:", len(frames))
    print("Original frame dimensions:", frames[0].shape)

    inputs = preprocess_video(frames)

    print("Model input shape:", tuple(inputs.shape))

    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

    # Warm-up is excluded from inference timing.
    with torch.inference_mode():
        _ = model(inputs)

    if DEVICE.type == "cuda":
        torch.cuda.synchronize()

    start = time.perf_counter()

    with torch.inference_mode():
        logits = model(inputs)

    if DEVICE.type == "cuda":
        torch.cuda.synchronize()

    elapsed = time.perf_counter() - start

    probabilities = torch.softmax(logits[0], dim=0)

    top_values, top_indices = torch.topk(
        probabilities,
        k=5
    )

    predicted_index = top_indices[0].item()
    predicted_label = labels[predicted_index]

    print("\n" + "=" * 50)
    print("ISL SWIN3D BASELINE RESULT")
    print("=" * 50)

    print("Video:", video_path.name)
    print("Predicted word:", predicted_label)

    print(
        "Confidence:",
        f"{top_values[0].item() * 100:.2f}%"
    )

    print("\nTop 5 predictions:")

    for rank, (value, index) in enumerate(
        zip(top_values, top_indices),
        start=1
    ):
        label = labels[index.item()]
        confidence = value.item() * 100

        print(
            f"{rank}. {label:<15} {confidence:.2f}%"
        )

    print("\nInference time:", f"{elapsed * 1000:.2f} ms")

    if DEVICE.type == "cuda":
        peak_memory = (
            torch.cuda.max_memory_allocated() / (1024 ** 2)
        )

        print(
            "Peak GPU memory:",
            f"{peak_memory:.2f} MB"
        )

    print("=" * 50)

    return predicted_label


def main():
    parser = argparse.ArgumentParser(
        description="Arthur ISL Swin3D baseline inference"
    )

    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Path to a specific ISL video"
    )

    args = parser.parse_args()

    labels = load_labels()

    print("Loaded classes:", len(labels))

    model = load_model()

    if args.video:
        video_path = Path(args.video).resolve()

    else:
        first_class = DATASET / labels[0]

        videos = sorted(
            list(first_class.glob("*.MOV"))
            + list(first_class.glob("*.mov"))
        )

        if not videos:
            raise FileNotFoundError(
                f"No MOV videos found in {first_class}"
            )

        video_path = videos[0]

        print(
            "\nAutomatically selected first dataset video:"
        )

    if not video_path.exists():
        raise FileNotFoundError(video_path)

    predict(model, video_path, labels)

    del model
    gc.collect()

    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()

    print("\nBaseline inference completed.")


if __name__ == "__main__":
    main()
