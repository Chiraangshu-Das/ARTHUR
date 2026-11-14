from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

import visionguide.voice_commands as voice_commands


class FakeSoundDevice:
    def __init__(self, default_input=1):
        self.devices = [
            {"name": "Default Speakers", "max_input_channels": 0},
            {"name": "Microphone Array (AMD Audio Device)", "max_input_channels": 2},
            {"name": "AMD Virtual Microphone", "max_input_channels": 2},
        ]
        self.default = SimpleNamespace(device=(default_input, 0))
        self.last_record_kwargs = None
        self.audio = np.full((int(6 * 16000), 1), 0.01, dtype=np.float32)
        self.checked = None

    def query_devices(self, index=None):
        if index is None:
            return self.devices
        return self.devices[index]

    def check_input_settings(self, **kwargs):
        self.checked = kwargs

    def rec(self, frames, **kwargs):
        self.last_record_kwargs = kwargs
        return self.audio[:frames]


class FakeWhisperModel:
    def __init__(self, text="Yes, I confirm this action."):
        self.text = text
        self.kwargs = None

    def transcribe(self, _samples, **kwargs):
        self.kwargs = kwargs
        return {"text": self.text}


def _install_fake_whisper(monkeypatch, model):
    module = ModuleType("whisper")
    module.load_model = lambda _name: model
    monkeypatch.setitem(sys.modules, "whisper", module)
    monkeypatch.setattr(voice_commands, "_MODEL", model)
    monkeypatch.setattr(voice_commands, "_MODEL_NAME", "base")


def test_confirmation_resolves_windows_default_input(monkeypatch):
    fake_sd = FakeSoundDevice(default_input=1)
    monkeypatch.delenv("VISIONGUIDE_CONFIRMATION_MIC_DEVICE", raising=False)

    index, name = voice_commands._resolve_confirmation_input_device(fake_sd)

    assert index == 1
    assert name == "Microphone Array (AMD Audio Device)"


def test_confirmation_can_use_explicit_validated_device_index(monkeypatch):
    fake_sd = FakeSoundDevice(default_input=1)
    monkeypatch.setenv("VISIONGUIDE_CONFIRMATION_MIC_DEVICE", "2")

    index, name = voice_commands._resolve_confirmation_input_device(fake_sd)

    assert index == 2
    assert name == "AMD Virtual Microphone"


def test_confirmation_rejects_ambiguous_device_name(monkeypatch):
    fake_sd = FakeSoundDevice(default_input=1)
    fake_sd.devices.append({"name": "Microphone Array Secondary", "max_input_channels": 2})
    monkeypatch.setenv("VISIONGUIDE_CONFIRMATION_MIC_DEVICE", "Microphone Array")

    with pytest.raises(RuntimeError, match="ambiguous"):
        voice_commands._resolve_confirmation_input_device(fake_sd)


def test_confirmation_capture_passes_resolved_device_and_transcribes_deterministically(monkeypatch):
    fake_sd = FakeSoundDevice(default_input=1)
    model = FakeWhisperModel()
    _install_fake_whisper(monkeypatch, model)
    monkeypatch.setattr(voice_commands, "_resolve_confirmation_input_device", lambda _sd: (1, "Validated microphone"))
    monkeypatch.setenv("VISIONGUIDE_SPEECH_LANGUAGE", "en")

    with patch.dict(sys.modules, {"sounddevice": fake_sd}):
        transcript = voice_commands.record_and_transcribe(
            duration_seconds=6.0, model_name="base", confirmation=True,
        )

    assert transcript == "Yes, I confirm this action."
    assert fake_sd.last_record_kwargs["device"] == 1
    assert fake_sd.last_record_kwargs["samplerate"] == 16000
    assert fake_sd.checked["device"] == 1
    assert model.kwargs["temperature"] == 0
    assert model.kwargs["condition_on_previous_text"] is False


def test_confirmation_capture_rejects_a_digital_silence_stream(monkeypatch):
    fake_sd = FakeSoundDevice(default_input=1)
    fake_sd.audio = np.zeros((int(6 * 16000), 1), dtype=np.float32)
    model = FakeWhisperModel()
    _install_fake_whisper(monkeypatch, model)
    monkeypatch.setattr(voice_commands, "_resolve_confirmation_input_device", lambda _sd: (1, "Silent endpoint"))

    with patch.dict(sys.modules, {"sounddevice": fake_sd}):
        with pytest.raises(RuntimeError, match="near-silent audio"):
            voice_commands.record_and_transcribe(
                duration_seconds=6.0, model_name="base", confirmation=True,
            )

    assert model.kwargs is None
