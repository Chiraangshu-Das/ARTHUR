from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT = Path(__file__).resolve().parents[1]
VENDOR = PROJECT / "vendor" / "Depth-Anything-V2"
CHECKPOINT = PROJECT / "models" / "depth_anything_v2_metric_hypersim_vits.pth"
SOURCE_URL = "https://codeload.github.com/DepthAnything/Depth-Anything-V2/zip/refs/heads/main"
WEIGHTS_URL = "https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small/resolve/main/depth_anything_v2_metric_hypersim_vits.pth?download=true"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading {destination.name} ...")
    request = Request(url, headers={"User-Agent": "Arthur-setup/1.0"})
    with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            if total:
                print(f"\r  {downloaded / total:6.1%}", end="", flush=True)
    print()
    if temporary.stat().st_size < 1024:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded file appears too small: {url}")
    temporary.replace(destination)


def setup_source() -> None:
    expected = VENDOR / "metric_depth" / "depth_anything_v2" / "dpt.py"
    if expected.is_file():
        print("Depth Anything V2 source already exists.")
        return
    archive = PROJECT / "vendor" / "depth-anything-v2-source.zip"
    download(SOURCE_URL, archive)
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.namelist()
        root_member = next((n for n in members if n.endswith("/metric_depth/depth_anything_v2/dpt.py")), None)
        if root_member is None:
            raise RuntimeError("Downloaded GitHub archive does not contain expected metric_depth source.")
        prefix = root_member.split("/metric_depth/depth_anything_v2/dpt.py")[0] + "/"
        for name in members:
            if not name.startswith(prefix):
                continue
            relative = name[len(prefix):]
            if not (relative == "LICENSE" or relative.startswith("metric_depth/depth_anything_v2/")):
                continue
            target = VENDOR / relative
            if name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            # Ignore path traversal entries in remote archives.
            if ".." in Path(relative).parts:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))
    archive.unlink(missing_ok=True)
    if not expected.is_file():
        raise RuntimeError("Failed to install depth model source files.")
    # Upstream infer_image chooses CUDA merely from device availability. Use the actual
    # model device so a CPU fallback works on machines with an unsupported/low-memory GPU.
    source_text = expected.read_text(encoding="utf-8")
    source_text = source_text.replace(
        "DEVICE = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'\n        image = image.to(DEVICE)",
        "DEVICE = next(self.parameters()).device\n        image = image.to(DEVICE)",
    )
    expected.write_text(source_text, encoding="utf-8")
    print("Installed upstream metric-depth source and its license.")


def main() -> int:
    try:
        setup_source()
        if not CHECKPOINT.is_file():
            download(WEIGHTS_URL, CHECKPOINT)
        print("\nDepth model files are ready.")
        print("Next: install integration dependencies with `pip install -r requirements-depth.txt` if PyTorch/torchvision are missing.")
        print("In Arthur, click Enable metric depth estimates.")
        return 0
    except Exception as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        print("Check internet access and retry. The model is ~100 MB and is downloaded from official project hosting.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
