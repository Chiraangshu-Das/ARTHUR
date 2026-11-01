# “Hey Arthur” Wake-Word Setup

Wake-word activation is a standard speech-input mode. It is disarmed at startup to preserve privacy and is only armed after the user explicitly enables it. After the phrase is detected, the system captures a bounded command clip and transcribes it with local Whisper.

## Configure

1. Create and activate the project's Python 3.11 environment.
2. Install the integration dependencies:

   ```powershell
   pip install -r requirements-integrations.txt
   ```

   Or install the runtime-only packages in a prepared environment:

   ```powershell
   pip install -r requirements-wakeword.txt
   ```

3. Provide an ONNX model trained for the exact phrase **“Hey Arthur”** at `models/wakeword/hey_arthur.onnx`, or set `WAKE_WORD_MODEL` in `.env` to its absolute path.
4. Review the model's source, licence, training data and intended use. Do not use a model trained for a different phrase and label it as “Hello Arthur.”
5. Set `WAKE_WORD_THRESHOLD` from `0.10` to `0.99` as required by local evaluation. A low threshold may increase false activations; a high threshold may miss the phrase.
6. Start Arthur and use **Wake word mode…** to arm the listener. Say the phrase and then issue a command. The listener pauses while Whisper records/transcribes that command and re-arms after handling it.
7. Use **Wake word mode…** again or say “disable wake word” to stop listening.

## Privacy and reliability

- The local wake detector processes the listening stream locally. The detector itself does not upload the audio.
- After phrase detection, command audio is separately captured for Whisper; the capture duration is bounded.
- Show a microphone indicator while armed. Provide a direct UI stop control and respect the user's stop command.
- Evaluate false accepts/rejects at realistic distance, background noise and speaking volume before daily use. Wake-word recognition is not guaranteed to be error-free.
