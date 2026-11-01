from __future__ import annotations

import threading

_MODEL = None
_MODEL_NAME = None
_MODEL_LOCK = threading.Lock()


def record_and_transcribe(
    duration_seconds: float = 5.0,
    model_name: str = "base",
    stop_event: threading.Event | None = None,
) -> str:
    """Record only when requested, optionally allowing the caller to interrupt capture."""
    if not 1 <= duration_seconds <= 12:
        raise ValueError("Recording duration must be between 1 and 12 seconds.")
    try:
        import numpy as np
        import sounddevice as sd
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "Voice commands require integration packages. Run `pip install -r requirements-integrations.txt`."
        ) from exc

    global _MODEL, _MODEL_NAME
    sample_rate = 16000
    if stop_event is not None and stop_event.is_set():
        return ""
    print(f"[Voice] Recording up to {duration_seconds:.0f} seconds. Speak clearly.")
    total_frames = int(duration_seconds * sample_rate)
    if stop_event is None:
        audio = sd.rec(total_frames, samplerate=sample_rate,
                       channels=1, dtype="float32", blocking=True)
        mono_audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    else:
        # Chunked capture lets the master OFF toggle or sleep command interrupt recording promptly.
        chunks = []
        captured = 0
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=1024) as stream:
            while captured < total_frames and not stop_event.is_set():
                frames = min(1024, total_frames - captured)
                chunk, _overflow = stream.read(frames)
                chunks.append(np.asarray(chunk, dtype=np.float32).reshape(-1))
                captured += frames
        if stop_event.is_set():
            return ""
        mono_audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    with _MODEL_LOCK:
        if _MODEL is None or _MODEL_NAME != model_name:
            _MODEL = whisper.load_model(model_name)
            _MODEL_NAME = model_name
        model = _MODEL
    result = model.transcribe(mono_audio, fp16=False, verbose=False)
    return str(result.get("text", "")).strip()


def transcribe_audio_file(file_path: str, model_name: str = "base") -> str:
    """Transcribe a locally received audio file with Whisper; files are handled by the caller."""
    if model_name not in {"tiny", "base", "small", "medium", "large", "turbo"}:
        raise ValueError("Whisper model must be one of tiny, base, small, medium, large, or turbo.")
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("Whisper transcription requires openai-whisper and ffmpeg. Install requirements-integrations.txt and the ffmpeg executable.") from exc
    global _MODEL, _MODEL_NAME
    with _MODEL_LOCK:
        if _MODEL is None or _MODEL_NAME != model_name:
            _MODEL = whisper.load_model(model_name)
            _MODEL_NAME = model_name
        model = _MODEL
    result = model.transcribe(str(file_path), fp16=False, verbose=False)
    return str(result.get("text", "")).strip()
