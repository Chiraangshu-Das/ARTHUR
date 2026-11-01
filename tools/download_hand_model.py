from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import requests

URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "models" / "hand_landmarker.task"


def main() -> int:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and DEST.stat().st_size > 1_000_000:
        print(f"Model already exists: {DEST}")
        return 0
    print("Downloading the official MediaPipe Hand Landmarker task model…")
    try:
        response = requests.get(URL, timeout=60, stream=True)
        response.raise_for_status()
        temporary = DEST.with_suffix(".download")
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)
        if temporary.stat().st_size < 1_000_000:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Downloaded model is unexpectedly small; refusing to keep it.")
        temporary.replace(DEST)
        digest = hashlib.sha256(DEST.read_bytes()).hexdigest()
        print(f"Downloaded: {DEST}\nSize: {DEST.stat().st_size:,} bytes\nSHA-256: {digest}")
        print("The model remains local. Air mouse stays disabled until you enable it in the app.")
        return 0
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
