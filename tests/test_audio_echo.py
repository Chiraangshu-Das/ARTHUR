from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from visionguide.audio_echo import EchoCancelledCapture


class EchoCancelledCaptureTests(unittest.TestCase):
    def test_downsample_converts_48khz_frames_to_16khz_float_audio(self):
        samples = np.arange(12, dtype=np.float32)
        result = EchoCancelledCapture.downsample_48k_to_16k(samples)
        self.assertEqual(result.shape, (4,))
        np.testing.assert_allclose(result, [1.0, 4.0, 7.0, 10.0])
        self.assertEqual(result.dtype, np.float32)

    def test_record_samples_discards_frames_until_echo_path_is_ready(self):
        capture = EchoCancelledCapture()
        capture._started = True
        capture._capture = SimpleNamespace(raise_if_failed=lambda: None)
        capture._frames.put((np.ones(320, dtype=np.float32), False))
        capture._frames.put((np.full(320, 0.25, dtype=np.float32), True))
        capture._frames.put((np.full(320, 0.5, dtype=np.float32), True))

        samples = capture.record_samples(0.04, require_echo_ready=True)
        self.assertEqual(samples.size, 640)
        np.testing.assert_allclose(samples[:320], 0.25)
        np.testing.assert_allclose(samples[320:], 0.5)
        capture.stop()

    def test_record_samples_returns_clean_mic_audio_when_not_gated_by_readiness(self):
        capture = EchoCancelledCapture()
        capture._started = True
        capture._capture = SimpleNamespace(raise_if_failed=lambda: None)
        capture._frames.put((np.full(320, 0.2, dtype=np.float32), False))
        samples = capture.record_samples(0.02, require_echo_ready=False)
        self.assertEqual(samples.size, 320)
        np.testing.assert_allclose(samples, 0.2)
        capture.stop()

    def test_echoff_failure_is_reported_without_raw_audio_fallback(self):
        capture = EchoCancelledCapture()
        with patch.dict(sys.modules, {"echoff": None}):
            with self.assertRaisesRegex(RuntimeError, "Acoustic echo cancellation is unavailable"):
                capture.start()
        self.assertFalse(capture.is_running)

    def test_capture_is_marked_ready_only_from_echoff_state(self):
        module = types.ModuleType("echoff")
        captured = {}

        class FakeConfig:
            def __init__(self, **kwargs):
                captured["config"] = kwargs

        class FakeCapture:
            def __init__(self, config, **kwargs):
                captured["kwargs"] = kwargs
                self.kwargs = kwargs

            def start(self):
                self.kwargs["on_frame"](SimpleNamespace(
                    microphone_clean=[0.1] * 960,
                    state=SimpleNamespace(echo_path_ready=True),
                ))

            def raise_if_failed(self):
                return None

            def stop(self):
                return None

            def status(self):
                return SimpleNamespace(to_dict=lambda: {"running": True})

        module.AecConfig = FakeConfig
        module.AecCapture = FakeCapture
        with patch.dict(sys.modules, {"echoff": module}):
            capture = EchoCancelledCapture()
            capture.start()
            self.assertTrue(capture.is_running)
            self.assertTrue(capture.echo_path_ready)
            self.assertEqual(captured["config"]["echo_path_warmup_s"], 7.5)
            self.assertEqual(capture.record_samples(0.02, require_echo_ready=True).size, 320)
            capture.stop()


if __name__ == "__main__":
    unittest.main()
