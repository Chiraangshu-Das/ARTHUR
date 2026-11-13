ARTHUR — AEC Readiness Calibration Patch
========================================

PURPOSE
-------
This is a small overlay for the existing ARTHUR Echoff AEC integration. It
updates the startup quality thresholds to match the measured acoustic level of
your Realtek speaker-loopback / AMD microphone setup, and prevents the rolling
readiness diagnostic from discarding your speech during double-talk.

WHAT CHANGES
------------
1. Echoff minimum raw microphone RMS is calibrated from 0.003 to 0.0001.
   Your far-end-only microphone recording was approximately 0.00019 RMS, so
   the old threshold was about 16 times higher than the signal your hardware
   actually produces.
2. Minimum measured suppression is calibrated from 10 dB to 5 dB. Your clean
   playback-only test measured about 6.1 dB on Echoff's rolling diagnostic and
   about 8.6 dB in the offline far-end-only analysis.
3. The 7.5-second active-reference warm-up remains in place. The suppression
   requirement must still pass Echoff's rolling quality window and stable-time
   check before ARTHUR accepts barge-in audio.
4. Once Echoff first reports its path ready, ARTHUR latches readiness for that
   AEC capture session. Echoff's rolling metric can dip when you speak because
   your preserved voice raises the clean microphone energy. Such a dip must not
   cause ARTHUR to throw away the user's cleaned speech frames.
5. Status now distinguishes the live Echoff readiness value from ARTHUR's
   latched session readiness.

This does NOT bypass the startup gate. If the speaker reference is not active,
AEC does not pass its quality check, no paired frames arrive, or the capture
fails, ARTHUR continues to fail closed: raw microphone audio is not sent to
Whisper during active SAPI playback. Once ready, only Echoff's microphone_clean
frames are used for speech interruption.

INSTALLATION
------------
1. Close ARTHUR completely.
2. Extract this ZIP into the ARTHUR project root (the folder containing main.py).
   The archive creates the folder arthur_aec_readiness_patch.
3. Open PowerShell in the ARTHUR project root and run:

   powershell -ExecutionPolicy Bypass -File .\arthur_aec_readiness_patch\install_patch.ps1

4. Activate the existing environment:

   .\.venv\Scripts\Activate.ps1

5. Validate:

   python -m compileall -q visionguide tests
   python -m pytest -q

6. Start ARTHUR:

   python main.py

The installer creates timestamped .bak backups of the two replaced files. It
does not modify .env, .venv, requirements files, credentials, models, databases,
or any other project files. Echoff dependencies are unchanged; this patch
assumes the earlier requirements-aec.txt installation is already complete.

OPTIONAL .ENV OVERRIDES
-----------------------
The calibrated defaults are already applied. You normally do not need to add
these variables. They are available for later tuning:

   VISIONGUIDE_AEC_MIN_SUPPRESSION_DB=5.0
   VISIONGUIDE_AEC_MIN_RAW_RMS=0.0001
   VISIONGUIDE_AEC_WARMUP_SECONDS=7.5

Values are bounded by the integration. Minimum suppression cannot be configured
below 3 dB, raw RMS cannot be configured below 0.00001, and warm-up cannot be
configured below 1 second or above 7.5 seconds.

TESTING AFTER INSTALL
---------------------
A. Start ARTHUR and ask it to speak a long answer (at least 10–15 seconds).
B. Wait for the AEC startup period, then say: "Arthur, stop speaking."
C. While paused, say: "Continue."
D. While speaking, try a new addressed command: "Arthur, what is 25 multiplied
   by 48?"
E. Confirm a yes/no action. ARTHUR should finish its short prompt and tone
   before opening the microphone answer window.

If readiness is not reached, the app should still fail safely. Pause speech or
press Escape rather than expecting raw-microphone barge-in during TTS.

VALIDATION
----------
Built against the ARTHUR source archive available in this session.
Results:
   python -m compileall -q visionguide tests  -> passed
   python -m pytest -q                         -> 205 passed, 20 subtests passed
   4 existing FastAPI on_event deprecation warnings

Automated tests cannot prove the behaviour of your specific speakers, room,
Windows audio endpoints, or Whisper transcription. Continue with the hardware
and manual tests above.
