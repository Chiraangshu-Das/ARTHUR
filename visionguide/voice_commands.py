from __future__ import annotations
import os
import threading

_MODEL = None
_MODEL_NAME = None
_MODEL_LOCK = threading.Lock()


def _resolve_confirmation_input_device(sd) -> tuple[int, str]:
    """Resolve a validated capture device for confirmation audio.

    An explicit VISIONGUIDE_CONFIRMATION_MIC_DEVICE may be a device index or
    an unambiguous device-name fragment. Otherwise the Windows/system default
    input is used. We intentionally do not fall back to an arbitrary device.
    """
    configured = os.getenv("VISIONGUIDE_CONFIRMATION_MIC_DEVICE", "").strip()
    devices = sd.query_devices()

    if configured and configured.casefold() not in {"default", "system default", "auto"}:
        if configured.isdigit():
            index = int(configured)
            if index < 0 or index >= len(devices):
                raise RuntimeError(
                    f"VISIONGUIDE_CONFIRMATION_MIC_DEVICE={configured} is outside the available device list. "
                    "Run `python -c \"import sounddevice as sd; print(sd.query_devices())\"` and update .env."
                )
        else:
            exact = [i for i, item in enumerate(devices) if str(item.get("name", "")).casefold() == configured.casefold()]
            matches = exact or [
                i for i, item in enumerate(devices)
                if configured.casefold() in str(item.get("name", "")).casefold()
            ]
            if len(matches) != 1:
                if not matches:
                    raise RuntimeError(
                        f"No input device matches VISIONGUIDE_CONFIRMATION_MIC_DEVICE={configured!r}. "
                        "Check `python -c \"import sounddevice as sd; print(sd.query_devices())\"`."
                    )
                options = "; ".join(f"{i}: {devices[i].get('name', 'Unknown device')}" for i in matches)
                raise RuntimeError(
                    f"The microphone name {configured!r} is ambiguous ({options}). "
                    "Set VISIONGUIDE_CONFIRMATION_MIC_DEVICE to the validated numeric device index."
                )
            index = matches[0]
    else:
        default_devices = sd.default.device
        index = default_devices[0] if isinstance(default_devices, (tuple, list)) else default_devices
        if index is None or int(index) < 0:
            raise RuntimeError(
                "Windows has no default input device. Select a microphone in Windows Sound settings "
                "or set VISIONGUIDE_CONFIRMATION_MIC_DEVICE in .env."
            )
        index = int(index)

    info = sd.query_devices(int(index))
    if int(info.get("max_input_channels", 0)) < 1:
        raise RuntimeError(
            f"Selected confirmation device {index} ({info.get('name', 'Unknown')}) has no input channels."
        )
    return int(index), str(info.get("name", f"Input device {index}"))


def transcribe_audio_samples(
    mono_audio,
    model_name: str = "base",
    confirmation: bool = False,
) -> str:
    """Transcribe an already captured mono 16 kHz float waveform with Whisper."""
    import numpy as np
    import whisper

    samples = np.asarray(mono_audio, dtype=np.float32).reshape(-1)
    if samples.size < 1600:
        return ""
    global _MODEL, _MODEL_NAME
    with _MODEL_LOCK:
        if _MODEL is None or _MODEL_NAME != model_name:
            _MODEL = whisper.load_model(model_name)
            _MODEL_NAME = model_name
        model = _MODEL
    language = os.getenv("VISIONGUIDE_SPEECH_LANGUAGE", "en").strip().lower()
    options = {
        "language": None if language == "auto" else language,
        "fp16": False,
        "verbose": False,
    }
    if confirmation:
        # Deterministic, independent decoding is preferable for a short safety
        # decision. No text prompt is supplied, so silence cannot be biased to yes.
        options.update({"temperature": 0, "condition_on_previous_text": False})
    result = model.transcribe(samples, **options)
    transcript = str(result.get("text", "")).strip()
    if confirmation:
        print(f"[Voice confirmation] Whisper transcript: {transcript!r}")
    return transcript


def record_and_transcribe(
    duration_seconds: float = 5.0,
    model_name: str = "base",
    stop_event: threading.Event | None = None,
    confirmation: bool = False,
) -> str:
    """Record and transcribe microphone audio.

    Confirmation captures explicitly resolve and validate the selected input
    endpoint, report signal levels, and reject a digitally silent stream before
    Whisper can turn an empty buffer into an ambiguous decision. Other voice
    capture call sites retain their previous device-selection behaviour.
    """
    if not 1 <= duration_seconds <= 12:
        raise ValueError("Recording duration must be between 1 and 12 seconds.")
    try:
        import numpy as np
        import sounddevice as sd
        import whisper  # noqa: F401 - dependency check before opening the microphone
    except ImportError as exc:
        raise RuntimeError(
            "Voice commands require integration packages. Run `pip install -r requirements-integrations.txt`."
        ) from exc

    if stop_event is not None and stop_event.is_set():
        return ""

    sample_rate = 16000
    device_index = None
    device_name = "system default"
    if confirmation:
        device_index, device_name = _resolve_confirmation_input_device(sd)
        try:
            sd.check_input_settings(
                device=device_index, channels=1, samplerate=sample_rate, dtype="float32"
            )
        except Exception as exc:
            raise RuntimeError(
                f"Microphone {device_index} ({device_name}) cannot provide mono 16 kHz audio: {exc}"
            ) from exc
        print(
            f"[Voice confirmation] Recording {duration_seconds:.1f}s from input "
            f"{device_index}: {device_name} at {sample_rate} Hz."
        )
    else:
        print(f"[Voice] Recording up to {duration_seconds:.0f} seconds. Speak clearly.")

    total_frames = int(duration_seconds * sample_rate)
    if stop_event is None:
        kwargs = {
            "samplerate": sample_rate,
            "channels": 1,
            "dtype": "float32",
            "blocking": True,
        }
        if confirmation:
            kwargs["device"] = device_index
        audio = sd.rec(total_frames, **kwargs)
        mono_audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    else:
        # Chunked capture lets the master OFF toggle or sleep command interrupt recording promptly.
        chunks = []
        captured = 0
        stream_kwargs = {
            "samplerate": sample_rate,
            "channels": 1,
            "dtype": "float32",
            "blocksize": 1024,
        }
        if confirmation:
            stream_kwargs["device"] = device_index
        with sd.InputStream(**stream_kwargs) as stream:
            while captured < total_frames and not stop_event.is_set():
                frames = min(1024, total_frames - captured)
                chunk, _overflow = stream.read(frames)
                chunks.append(np.asarray(chunk, dtype=np.float32).reshape(-1))
                captured += frames
        if stop_event.is_set():
            return ""
        mono_audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    if confirmation:
        rms = float(np.sqrt(np.mean(np.square(mono_audio, dtype=np.float64)))) if mono_audio.size else 0.0
        peak = float(np.max(np.abs(mono_audio))) if mono_audio.size else 0.0
        rms_db = 20.0 * np.log10(max(rms, 1e-10))
        peak_db = 20.0 * np.log10(max(peak, 1e-10))
        print(
            f"[Voice confirmation] Input levels: RMS {rms_db:.1f} dBFS, "
            f"peak {peak_db:.1f} dBFS."
        )
        # The previously tested silent AMD virtual endpoint returned exact zeros
        # (-200 dBFS in the diagnostic). This catches a dead route without
        # rejecting ordinary quiet-room recordings or low-volume speech.
        if peak < 1e-7 or rms < 1e-8:
            raise RuntimeError(
                f"Microphone {device_index} ({device_name}) returned near-silent audio. "
                "Check the Windows input level/default microphone and set "
                "VISIONGUIDE_CONFIRMATION_MIC_DEVICE to the working device index if needed."
            )

    return transcribe_audio_samples(
        mono_audio, model_name=model_name, confirmation=confirmation,
    )


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
    language = os.getenv("VISIONGUIDE_SPEECH_LANGUAGE", "en").strip().lower()
    result = model.transcribe(
        str(file_path),
        language=None if language == "auto" else language,
        fp16=False,
        verbose=False,
    )
    return str(result.get("text", "")).strip()