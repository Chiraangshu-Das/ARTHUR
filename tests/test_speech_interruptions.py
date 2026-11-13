from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from visionguide.app import ArthurApp
from visionguide.speech import SpeechOutput
from visionguide.speech_renderer import render_for_speech, split_speech_segments
from visionguide.voice_interrupts import parse_speech_interrupt


class SpeechRenderingTests(unittest.TestCase):
    def test_latex_integral_is_spoken_as_plain_language(self):
        source = r"""The antiderivative is \[\int x^{k}\,dx = \frac{x^{k+1}}{k+1}+C.\]"""
        spoken = render_for_speech(source).casefold()
        self.assertIn("integral of", spoken)
        self.assertIn("to the power k plus 1", spoken)
        self.assertIn("divided by k plus 1", spoken)
        self.assertIn("a constant", spoken)
        self.assertNotIn("\\frac", spoken)
        self.assertNotIn("\\int", spoken)
        self.assertNotIn("\\[", spoken)

    def test_markdown_bullets_and_links_do_not_read_formatting(self):
        source = "## Examples\n\n* **First:** [Python](https://python.org) is useful.\n* Second item."
        spoken = render_for_speech(source)
        self.assertIn("First:", spoken)
        self.assertIn("Python is useful", spoken)
        self.assertNotIn("https://", spoken)
        self.assertNotIn("**", spoken)

    def test_trigonometric_and_square_root_notation_is_rendered(self):
        spoken = render_for_speech(r"\sin(x) + \sqrt{x^2}")
        self.assertIn("sine of", spoken)
        self.assertIn("square root of", spoken)
        self.assertNotIn(r"\sin", spoken)
        self.assertNotIn(r"\sqrt", spoken)

    def test_code_blocks_are_not_read_as_raw_source(self):
        spoken = render_for_speech("Example:\n```python\nprint('hello')\n```")
        self.assertIn("Code is shown in the output panel", spoken)
        self.assertNotIn("print(", spoken)

    def test_plain_prose_is_not_rewritten_as_latex(self):
        source = "This is a well-known method. It is not difficult."
        self.assertEqual(render_for_speech(source), source)

    def test_resume_position_advances_past_current_word(self):
        status = SimpleNamespace(InputWordPos=8, InputWordLen=1)
        self.assertEqual(
            SpeechOutput._remaining_after_current_word("This is a longer answer", status),
            "longer answer",
        )

    def test_invalid_resume_position_falls_back_to_current_sentence(self):
        status = SimpleNamespace(InputWordPos=2, InputWordLen=1)
        self.assertEqual(
            SpeechOutput._remaining_after_current_word("This is a longer answer", status),
            "This is a longer answer",
        )

    def test_long_responses_split_at_sentence_boundaries(self):
        segments = split_speech_segments("First sentence. Second sentence. Third sentence.")
        self.assertEqual(segments, ["First sentence.", "Second sentence.", "Third sentence."])


class VoiceConfirmationParsingTests(unittest.TestCase):
    def test_clear_yes_answers_are_accepted(self):
        for phrase in ("yes", "yeah", "yep", "confirm", "go ahead", "okay"):
            with self.subTest(phrase=phrase):
                self.assertIs(ArthurApp._parse_voice_confirmation(phrase), True)

    def test_clear_no_answers_are_rejected(self):
        for phrase in ("no", "nope", "cancel", "not now", "decline"):
            with self.subTest(phrase=phrase):
                self.assertIs(ArthurApp._parse_voice_confirmation(phrase), False)

    def test_ambiguous_or_empty_answers_fail_closed(self):
        for phrase in ("maybe", "I think so", "", "the answer is not obvious"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(ArthurApp._parse_voice_confirmation(phrase))




class ConversationCaptureSafetyTests(unittest.TestCase):
    def test_normal_microphone_recording_waits_until_sapi_is_idle(self):
        class FakeSpeech:
            def __init__(self):
                self.is_busy = True
                self.is_paused = False
                self.wait_called = False

            def wait_until_idle(self, timeout=None):
                self.wait_called = True
                self.is_busy = False
                return True

        app = object.__new__(ArthurApp)
        app.speech = FakeSpeech()
        app._aec_starting = threading.Event()
        app._aec_audio = None

        def fake_record(**kwargs):
            self.assertTrue(app.speech.wait_called)
            self.assertFalse(app.speech.is_busy)
            return "mic capture after playback"

        with patch("visionguide.voice_commands.record_and_transcribe", side_effect=fake_record), \
             patch("time.sleep"):
            result = ArthurApp._record_conversation_text(app, 3.0)
        self.assertEqual(result, "mic capture after playback")


class VoiceConfirmationCaptureSafetyTests(unittest.TestCase):
    def test_confirmation_closes_aec_and_waits_for_output_before_raw_mic(self):
        import queue

        class FakeSpeech:
            def __init__(self):
                self.is_busy = False
                self.cancelled = False
                self.wait_calls = 0

            def cancel(self):
                self.cancelled = True
                self.is_busy = False

            def wait_until_idle(self, timeout=None):
                self.wait_calls += 1
                self.is_busy = False
                return True

        class FakeAec:
            def __init__(self):
                self.stopped = False

            def stop(self):
                self.stopped = True

        class FakeStatus:
            def set(self, _value):
                return None

        app = object.__new__(ArthurApp)
        app.conversation_active = True
        app.speech = FakeSpeech()
        app._aec_audio = FakeAec()
        aec = app._aec_audio
        app._async_messages = queue.Queue()
        app.status_var = FakeStatus()
        app._append_output = lambda _message: None
        app._stop_speech_interrupt_listener = lambda: None

        def fake_say(_text, **_kwargs):
            app.speech.is_busy = True

        app._say = fake_say

        def fake_record(**kwargs):
            self.assertEqual(kwargs["duration_seconds"], 6.0)
            self.assertFalse(app.speech.is_busy, "raw microphone must open only after SAPI is idle")
            self.assertIsNone(app._aec_audio, "AEC input must be closed before sounddevice opens")
            self.assertTrue(aec.stopped)
            return "yes"

        with patch("visionguide.voice_commands.record_and_transcribe", side_effect=fake_record), \
             patch("time.sleep"):
            accepted = ArthurApp._ask_yes_no(app, "Test action", "Full details on screen")

        self.assertTrue(accepted)
        self.assertTrue(app.speech.cancelled)
        self.assertGreaterEqual(app.speech.wait_calls, 2)


    def test_active_tts_without_aec_never_opens_raw_microphone(self):
        import queue

        class FakeSpeech:
            is_busy = True
            is_paused = False

        app = object.__new__(ArthurApp)
        app.conversation_active = True
        app._closed = False
        app.speech = FakeSpeech()
        app._speech_interrupt_stop = threading.Event()
        app._speech_interrupt_done = threading.Event()
        app._aec_audio = None
        app._async_messages = queue.Queue()

        with patch("visionguide.voice_commands.record_and_transcribe") as raw_record, \
             patch("visionguide.voice_commands.transcribe_audio_samples") as aec_transcribe:
            ArthurApp._speech_interrupt_loop(app)

        raw_record.assert_not_called()
        aec_transcribe.assert_not_called()
        self.assertTrue(app._speech_interrupt_done.is_set())



class SpeechInterruptParsingTests(unittest.TestCase):
    def test_stop_and_pause_are_recognized_only_when_addressed_to_arthur(self):
        self.assertEqual(parse_speech_interrupt("Arthur, stop speaking").kind, "pause")
        self.assertEqual(parse_speech_interrupt("Hey Arthur, pause").kind, "pause")
        self.assertIsNone(parse_speech_interrupt("stop speaking"))

    def test_continue_and_resume(self):
        self.assertEqual(parse_speech_interrupt("Arthur continue from where you left off").kind, "resume")
        self.assertEqual(parse_speech_interrupt("Hey Arthur, resume").kind, "resume")
        self.assertEqual(parse_speech_interrupt("ok now continue", allow_unaddressed_resume=True).kind, "resume")
        self.assertEqual(parse_speech_interrupt("continue it", allow_unaddressed_resume=True).kind, "resume")
        self.assertIsNone(parse_speech_interrupt("ok now continue"))

    def test_cancel_response(self):
        self.assertEqual(parse_speech_interrupt("Arthur cancel that response").kind, "cancel")

    def test_new_command_is_returned_without_the_address_phrase(self):
        parsed = parse_speech_interrupt("Arthur, what is the weather in Kolkata?")
        self.assertEqual(parsed.kind, "command")
        self.assertEqual(parsed.command, "what is the weather in kolkata")


if __name__ == "__main__":
    unittest.main()
