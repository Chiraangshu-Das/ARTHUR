from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from visionguide.app import ArthurApp
from visionguide.engine import VisionWorker
from visionguide.speech import SpeechOutput


def main() -> None:
    parser = argparse.ArgumentParser(description="Arthur local-first assistive-ai client")
    parser.add_argument("--model", default="models/yolo26n.pt", help="Path to an Ultralytics-compatible .pt model")
    parser.add_argument("--camera", default="0", help="Camera index such as 0/1, or a local HTTP/RTSP stream URL from a phone camera app")
    parser.add_argument("--confidence", type=float, default=0.35, help="Detection confidence in the range 0.05–0.95")
    parser.add_argument("--fps", type=int, default=8, help="Maximum object-detection inference rate")
    parser.add_argument("--no-speech", action="store_true", help="Disable local text-to-speech")
    parser.add_argument("--cpu", action="store_true", help="Force CPU inference even if a supported GPU is available")
    parser.add_argument("--serve-api", action="store_true", help="Run the authenticated FastAPI device/client-server service instead of the Tk desktop UI")
    args = parser.parse_args()

    if not 0.05 <= args.confidence <= 0.95:
        parser.error("--confidence must be between 0.05 and 0.95")
    if args.fps < 1 or args.fps > 30:
        parser.error("--fps must be between 1 and 30")

    load_dotenv()
    if args.serve_api:
        from visionguide.api_server import main as serve_api
        serve_api()
        return

    project_dir = Path(__file__).resolve().parent
    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = project_dir / model_path
    if not model_path.is_file():
        parser.error(f"Model file was not found: {model_path}")

    speech = SpeechOutput(enabled=not args.no_speech)
    try:
        camera_source = int(args.camera)
    except ValueError:
        camera_source = args.camera.strip()
        if not camera_source:
            parser.error("--camera cannot be empty")
    worker = VisionWorker(
        model_path=str(model_path),
        camera_index=camera_source,
        confidence_threshold=args.confidence,
        target_fps=args.fps,
        force_cpu=args.cpu,
    )
    app = ArthurApp(worker=worker, speech=speech, project_dir=project_dir)
    app.run()


if __name__ == "__main__":
    main()
