from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def is_lfs_pointer(path: Path) -> bool:
    try:
        head = path.read_bytes()[:256]
    except OSError:
        return False
    return head.startswith(b"version https://git-lfs.github.com/spec/v1")


def check_file(label: str, relative: str, minimum_bytes: int) -> bool:
    path = ROOT / relative
    if not path.is_file():
        print(f"[MISSING] {label}: {relative}")
        return False
    if is_lfs_pointer(path):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        expected = next((line.split(" ", 1)[1] for line in text.splitlines() if line.startswith("size ")), "unknown")
        print(f"[GIT LFS POINTER] {label}: {relative} (expected bytes: {expected})")
        return False
    size = path.stat().st_size
    if size < minimum_bytes:
        print(f"[TOO SMALL] {label}: {relative} ({size:,} bytes; expected at least {minimum_bytes:,})")
        return False
    print(f"[OK] {label}: {relative} ({size:,} bytes)")
    return True


def check_isl_labels() -> bool:
    candidates = [
        ROOT / "models/isl/swin3d_s/labels.json",
        ROOT / "models/isl/swin3d_s/class_names.json",
        ROOT / "models/isl_labels.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                labels = raw
            elif isinstance(raw, dict) and all(str(k).isdigit() for k in raw):
                labels = [raw[k] for k in sorted(raw, key=lambda x: int(x))]
            elif isinstance(raw, dict) and all(isinstance(v, int) for v in raw.values()):
                labels = [k for k, _ in sorted(raw.items(), key=lambda pair: pair[1])]
            else:
                labels = []
            if len(labels) == 76:
                print(f"[OK] ISL label map: {path.relative_to(ROOT)} (76 classes)")
                return True
            print(f"[INVALID] ISL label map: {path.relative_to(ROOT)} ({len(labels)} classes; expected 76)")
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            print(f"[INVALID] ISL label map: {path.relative_to(ROOT)} ({exc})")

    dataset = ROOT / "data/isl_dataset/ProcessedData_vivit"
    count = sum(1 for p in dataset.iterdir() if p.is_dir()) if dataset.is_dir() else 0
    if count == 76:
        print(f"[OK] ISL labels can be reconstructed from {dataset.relative_to(ROOT)}")
        return True
    print(f"[MISSING] ISL 76-class label map (or dataset with exactly 76 class folders): {dataset.relative_to(ROOT)}; found {count}")
    return False


def main() -> int:
    print("ARTHUR runtime asset verification")
    checks = [
        check_file("YOLO object-detection weights", "models/yolo26n.pt", 1_000_000),
        check_file("MediaPipe Hand Landmarker model", "models/hand_landmarker.task", 1_000_000),
        check_file("ISL Swin3D-S checkpoint", "models/isl/swin3d_s/ISL_best_model.pt", 10_000_000),
        check_isl_labels(),
    ]
    passed = sum(checks)
    print(f"\n{passed}/{len(checks)} runtime asset checks passed.")
    if passed != len(checks):
        print("Some hardware/vision features will remain unavailable until the missing assets are installed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
