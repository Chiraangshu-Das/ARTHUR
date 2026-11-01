from __future__ import annotations

import argparse
import csv
import gc
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from torchvision.models.video import swin3d_s
from transformers import VivitImageProcessor


# ---------------------------------------------------------
# PATHS AND SETTINGS
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

DATASET_DIR = ROOT / "data" / "isl_dataset" / "ProcessedData_vivit"
CHECKPOINT_PATH = ROOT / "models" / "isl" / "swin3d_s" / "ISL_best_model.pt"

OUTPUT_DIR = ROOT / "reports" / "isl_swin3d"
PREDICTIONS_FILE = OUTPUT_DIR / "predictions.csv"
SUMMARY_FILE = OUTPUT_DIR / "evaluation_summary.json"
REPORT_FILE = OUTPUT_DIR / "classification_report.txt"
CONFUSION_FILE = OUTPUT_DIR / "confusion_matrix.csv"

PROCESSOR_NAME = "google/vivit-b-16x2"

NUM_FRAMES = 32
NUM_CLASSES = 76
CONFIDENCE_THRESHOLD = 0.0  # Evaluation records all predictions.

CSV_FIELDS = [
    "video_path",
    "true_index",
    "pred_index",
    "top5_indices",
    "confidence",
    "inference_ms",
    "status",
    "error",
]


# ---------------------------------------------------------
# DEVICE AND MODEL
# ---------------------------------------------------------

def load_model(device: torch.device):
    print("\nLoading Swin3D-S architecture...", flush=True)

    model = swin3d_s(weights=None, num_classes=NUM_CLASSES)

    print(f"Loading checkpoint: {CHECKPOINT_PATH}", flush=True)

    checkpoint = torch.load(
        CHECKPOINT_PATH,
        map_location="cpu",
        weights_only=True,
    )

    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]

    mapped_state = {}

    for key, value in checkpoint.items():
        if key.startswith("base_model."):
            new_key = key[len("base_model."):]

        elif key.startswith("classification_head.0."):
            new_key = key.replace(
                "classification_head.0.",
                "head.",
                1,
            )

        else:
            new_key = key

        mapped_state[new_key] = value

    model.load_state_dict(mapped_state, strict=True)

    model.to(device)
    model.eval()

    print("Checkpoint loaded successfully.", flush=True)
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Output classes: {NUM_CLASSES}", flush=True)

    return model


# ---------------------------------------------------------
# DATASET AND CLASS MAPPING
# ---------------------------------------------------------

def load_dataset():
    if not DATASET_DIR.exists():
        raise FileNotFoundError(
            f"Dataset folder not found:\n{DATASET_DIR}"
        )

    class_folders = sorted(
        folder
        for folder in DATASET_DIR.iterdir()
        if folder.is_dir()
    )

    class_names = [folder.name for folder in class_folders]

    if len(class_names) != NUM_CLASSES:
        raise RuntimeError(
            f"Expected {NUM_CLASSES} classes, "
            f"but found {len(class_names)} in {DATASET_DIR}"
        )

    video_paths = []
    labels = []

    print("\nReading dataset...", flush=True)

    for class_index, folder in enumerate(class_folders):
        videos = sorted(
            file
            for file in folder.iterdir()
            if file.is_file() and file.suffix.upper() == ".MOV"
        )

        for video in videos:
            video_paths.append(str(video.resolve()))
            labels.append(class_index)

        print(
            f"  {folder.name}: {len(videos)} videos",
            flush=True,
        )

    if not video_paths:
        raise RuntimeError("No .MOV videos were found.")

    print(f"\nTotal videos: {len(video_paths)}", flush=True)

    return video_paths, np.asarray(labels), class_names


def create_test_split(video_paths, labels):
    # Preserve the notebook's two-stage stratified split.
    train_paths, _, train_labels, _ = train_test_split(
        video_paths,
        labels,
        test_size=0.2,
        stratify=labels,
        random_state=42,
    )

    _, test_paths, _, test_labels = train_test_split(
        train_paths,
        train_labels,
        test_size=0.2,
        stratify=train_labels,
        random_state=42,
    )

    return list(test_paths), np.asarray(test_labels)


# ---------------------------------------------------------
# VIDEO PREPROCESSING
# ---------------------------------------------------------

def read_video_frames(video_path: str):
    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open this video.")

    frames = []

    try:
        for _ in range(NUM_FRAMES):
            success, frame = capture.read()

            if not success:
                break

            frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            frames.append(Image.fromarray(frame))

    finally:
        capture.release()

    if len(frames) != NUM_FRAMES:
        raise RuntimeError(
            f"Expected {NUM_FRAMES} frames, "
            f"but decoded {len(frames)}."
        )

    return frames


def preprocess_video(video_path: str, processor, device):
    frames = read_video_frames(video_path)

    processed = processor(
        images=frames,
        return_tensors="pt",
    )

    pixel_values = processed["pixel_values"]

    # Handle either [T, C, H, W] or [B, T, C, H, W].
    if pixel_values.ndim == 4:
        pixel_values = pixel_values.unsqueeze(0)

    if pixel_values.ndim != 5:
        raise RuntimeError(
            f"Unexpected processor output shape: "
            f"{tuple(pixel_values.shape)}"
        )

    # ViViT processor output: [B, T, C, H, W]
    # Swin3D input:           [B, C, T, H, W]
    video_tensor = pixel_values.permute(
        0, 2, 1, 3, 4
    ).contiguous()

    expected_shape = (
        1,
        3,
        NUM_FRAMES,
        224,
        224,
    )

    if tuple(video_tensor.shape) != expected_shape:
        raise RuntimeError(
            f"Expected model input {expected_shape}, "
            f"received {tuple(video_tensor.shape)}"
        )

    return video_tensor.to(
        device=device,
        dtype=torch.float32,
    )


# ---------------------------------------------------------
# CHECKPOINTED PREDICTIONS
# ---------------------------------------------------------

def prepare_predictions_file(fresh: bool):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if fresh and PREDICTIONS_FILE.exists():
        PREDICTIONS_FILE.unlink()
        print(
            "\nPrevious prediction file removed (--fresh).",
            flush=True,
        )

    if not PREDICTIONS_FILE.exists():
        with PREDICTIONS_FILE.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=CSV_FIELDS,
            )
            writer.writeheader()


def read_completed_predictions():
    completed = {}

    if not PREDICTIONS_FILE.exists():
        return completed

    with PREDICTIONS_FILE.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames != CSV_FIELDS:
            raise RuntimeError(
                "The existing predictions.csv has an unexpected format. "
                "Run again with --fresh to create a new evaluation."
            )

        for row in reader:
            if row["status"] == "ok":
                completed[row["video_path"]] = row

    return completed


def save_prediction(row: dict):
    with PREDICTIONS_FILE.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=CSV_FIELDS,
        )
        writer.writerow(row)
        file.flush()


# ---------------------------------------------------------
# SINGLE-VIDEO INFERENCE
# ---------------------------------------------------------

@torch.inference_mode()
def predict_video(model, processor, video_path, device):
    video_tensor = preprocess_video(
        video_path,
        processor,
        device,
    )

    if device.type == "cuda":
        torch.cuda.synchronize()

    start = time.perf_counter()

    logits = model(video_tensor)

    if device.type == "cuda":
        torch.cuda.synchronize()

    inference_ms = (time.perf_counter() - start) * 1000

    probabilities = torch.softmax(
        logits,
        dim=1,
    )[0]

    top5_probabilities, top5_indices = torch.topk(
        probabilities,
        k=5,
    )

    predicted_index = int(top5_indices[0].item())
    confidence = float(top5_probabilities[0].item())

    result = {
        "pred_index": predicted_index,
        "top5_indices": [
            int(index)
            for index in top5_indices.cpu().tolist()
        ],
        "confidence": confidence,
        "inference_ms": inference_ms,
    }

    del video_tensor, logits, probabilities
    del top5_probabilities, top5_indices

    return result


# ---------------------------------------------------------
# METRICS AND REPORTS
# ---------------------------------------------------------

def generate_reports(
    test_paths,
    test_labels,
    class_names,
    completed,
):
    # Only include successful predictions from this test split.
    rows = [
        completed[path]
        for path in test_paths
        if path in completed
    ]

    if not rows:
        print(
            "\nNo successful predictions are available yet.",
            flush=True,
        )
        return

    y_true = np.asarray(
        [int(row["true_index"]) for row in rows]
    )

    y_pred = np.asarray(
        [int(row["pred_index"]) for row in rows]
    )

    top5_correct = 0

    for row in rows:
        top5 = json.loads(row["top5_indices"])

        if int(row["true_index"]) in top5:
            top5_correct += 1

    top1_accuracy = accuracy_score(y_true, y_pred)
    top5_accuracy = top5_correct / len(rows)

    macro_f1 = f1_score(
        y_true,
        y_pred,
        average="macro",
        zero_division=0,
    )

    weighted_f1 = f1_score(
        y_true,
        y_pred,
        average="weighted",
        zero_division=0,
    )

    report = classification_report(
        y_true,
        y_pred,
        labels=list(range(len(class_names))),
        target_names=class_names,
        zero_division=0,
        digits=4,
    )

    matrix = confusion_matrix(
        y_true,
        y_pred,
        labels=list(range(len(class_names))),
    )

    SUMMARY_FILE.write_text(
        json.dumps(
            {
                "evaluated_videos": len(rows),
                "test_videos": len(test_paths),
                "top1_accuracy": float(top1_accuracy),
                "top5_accuracy": float(top5_accuracy),
                "macro_f1": float(macro_f1),
                "weighted_f1": float(weighted_f1),
                "note": (
                    "Metrics are based only on successfully evaluated "
                    "videos in the generated local test split."
                ),
            },
            indent=4,
        ),
        encoding="utf-8",
    )

    REPORT_FILE.write_text(
        report,
        encoding="utf-8",
    )

    with CONFUSION_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["true/predicted"] + class_names)

        for index, row in enumerate(matrix):
            writer.writerow([class_names[index]] + row.tolist())

    print("\n" + "=" * 60)
    print("ISL SWIN3D EVALUATION RESULTS")
    print("=" * 60)

    print(f"Successfully evaluated: {len(rows)} / {len(test_paths)}")
    print(f"Top-1 accuracy:         {top1_accuracy:.4%}")
    print(f"Top-5 accuracy:         {top5_accuracy:.4%}")
    print(f"Macro F1:               {macro_f1:.4f}")
    print(f"Weighted F1:            {weighted_f1:.4f}")

    print("\nClassification report:")
    print(report)

    print("\nSaved reports:")
    print(f"  Predictions:       {PREDICTIONS_FILE}")
    print(f"  Summary:           {SUMMARY_FILE}")
    print(f"  Classification:    {REPORT_FILE}")
    print(f"  Confusion matrix:  {CONFUSION_FILE}")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Arthur's pretrained ISL Swin3D model."
    )

    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete previous predictions and start from scratch.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Evaluate only the first N test videos (0 = all).",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ARTHUR - ISL SWIN3D EVALUATION")
    print("=" * 60)

    print(f"Python: {sys.version.split()[0]}")
    print(f"PyTorch: {torch.__version__}")

    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(
            f"Checkpoint not found:\n{CHECKPOINT_PATH}"
        )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print(f"Device: {device}", flush=True)

    if device.type == "cuda":
        print(
            f"GPU: {torch.cuda.get_device_name(0)}",
            flush=True,
        )
        print(
            f"GPU memory: "
            f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB",
            flush=True,
        )

    # Keep CPU preprocessing from oversubscribing the laptop.
    torch.set_num_threads(2)

    video_paths, labels, class_names = load_dataset()

    test_paths, test_labels = create_test_split(
        video_paths,
        labels,
    )

    print(
        f"\nTest split: {len(test_paths)} videos",
        flush=True,
    )

    if args.limit > 0:
        test_paths = test_paths[:args.limit]
        print(
            f"LIMIT MODE: evaluating only {len(test_paths)} videos.",
            flush=True,
        )

    # Rebuild path -> true label lookup from the full dataset.
    true_label_by_path = {
        path: int(label)
        for path, label in zip(video_paths, labels)
    }

    prepare_predictions_file(args.fresh)

    completed = read_completed_predictions()

    # Only count completed predictions belonging to this run's test set.
    test_path_set = set(test_paths)
    completed = {
        path: row
        for path, row in completed.items()
        if path in test_path_set
    }

    remaining = [
        path
        for path in test_paths
        if path not in completed
    ]

    print(
        f"Already completed: {len(completed)}",
        flush=True,
    )
    print(
        f"Remaining videos:  {len(remaining)}",
        flush=True,
    )

    if not remaining:
        print("\nAll selected videos have already been evaluated.")
        generate_reports(
            test_paths,
            test_labels,
            class_names,
            completed,
        )
        return

    print("\nLoading image processor...", flush=True)

    processor = VivitImageProcessor.from_pretrained(
        PROCESSOR_NAME
    )

    model = load_model(device)

    print("\nStarting one-video-at-a-time evaluation...\n", flush=True)

    total = len(test_paths)
    start_all = time.perf_counter()

    for index, video_path in enumerate(test_paths, start=1):
        if video_path in completed:
            continue

        true_index = true_label_by_path[video_path]
        true_name = class_names[true_index]
        video_name = Path(video_path).name

        try:
            result = predict_video(
                model,
                processor,
                video_path,
                device,
            )

            pred_index = result["pred_index"]
            pred_name = class_names[pred_index]

            row = {
                "video_path": video_path,
                "true_index": true_index,
                "pred_index": pred_index,
                "top5_indices": json.dumps(
                    result["top5_indices"]
                ),
                "confidence": f'{result["confidence"]:.8f}',
                "inference_ms": f'{result["inference_ms"]:.2f}',
                "status": "ok",
                "error": "",
            }

            save_prediction(row)
            completed[video_path] = row

            status = (
                "CORRECT"
                if pred_index == true_index
                else "WRONG"
            )

            print(
                f"[{index}/{total}] {status} | "
                f"True: {true_name} | "
                f"Predicted: {pred_name} | "
                f"Confidence: {result['confidence']:.2%} | "
                f"{result['inference_ms']:.1f} ms | "
                f"{video_name}",
                flush=True,
            )

            del result, row

        except Exception as error:
            error_message = (
                f"{type(error).__name__}: {error}"
            )

            save_prediction(
                {
                    "video_path": video_path,
                    "true_index": true_index,
                    "pred_index": "",
                    "top5_indices": "",
                    "confidence": "",
                    "inference_ms": "",
                    "status": "error",
                    "error": error_message,
                }
            )

            print(
                f"[{index}/{total}] ERROR | "
                f"{true_name} | {video_name} | "
                f"{error_message}",
                flush=True,
            )

        finally:
            gc.collect()

    elapsed = time.perf_counter() - start_all

    if device.type == "cuda":
        torch.cuda.synchronize()
        peak_memory = (
            torch.cuda.max_memory_allocated(device)
            / 1024**2
        )

        print(
            f"\nPeak GPU memory allocated: {peak_memory:.2f} MB",
            flush=True,
        )

    print(
        f"Evaluation processing time: {elapsed / 60:.2f} minutes",
        flush=True,
    )

    generate_reports(
        test_paths,
        test_labels,
        class_names,
        completed,
    )

    print("\nEvaluation finished.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\nEvaluation interrupted. Completed predictions "
            "have been saved and can be resumed.",
            flush=True,
        )
    except Exception as error:
        print(
            f"\nFATAL ERROR: {type(error).__name__}: {error}",
            flush=True,
        )
        raise