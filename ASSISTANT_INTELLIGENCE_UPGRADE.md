# Arthur Conversational Intelligence Upgrade

This patch adds session-scoped conversational context and a more consistent spoken response style while preserving Arthur's existing typed command router and permissioned action executors.

## Files

### Replace
- `visionguide/app.py`
- `visionguide/semantic_router.py`
- `visionguide/cloud_ai.py`
- `visionguide/speech.py` (replaces the failing pyttsx3 playback path with native SAPI5; `comtypes` is already listed in the integration requirements)
- `.env.example` (merge the new setting into your existing `.env`; do not overwrite your real secrets)

### Add
- `visionguide/conversation.py`
- `visionguide/voice_responses.py`
- `tests/test_conversation.py`

No dependency changes are required.

## Context privacy

Arthur keeps the latest eight voice turns in memory only. They are discarded when the application exits and are not written to SQLite.

In `.env.example`, this setting defaults to disabled:

```dotenv
VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=0
```

Keep it at `0` to retain context locally without sending it to Groq. Set it to `1` only when you want recent conversation turns included in Groq function-call routing and text-only responses. Ordinary text-only questions and tasks are sent directly to Groq without a second confirmation prompt. The current command text is sent; prior conversation context remains local unless this setting is enabled. Do not put API keys or other secrets in conversation commands.

## Behaviour

- Existing deterministic command patterns still take priority over Groq.
- Groq receives recent context only when the explicit setting above is enabled.
- The router can use context to resolve clear follow-ups such as “open it”; ambiguous references should result in a clarification rather than a guessed action.
- Context does not grant permission for external messages, calendar changes, image uploads, or other sensitive operations.
- Ordinary text-only requests are sent directly to Groq; no “send to Groq?” dialog or “local command not found” narration is shown.
- Tool actions that save, update, delete, submit, send, publish, change network settings, or upload camera/screen content retain their separate confirmation gates.
- General Groq answers use a calm, concise assistant voice and may use approved recent context.
- Browser/app launch confirmations are shorter and more conversational. The complete operation result remains in the UI.
- Existing local memory, action history, tool allowlists, and confirmation gates are retained.

## Apply

1. Back up the current project folder.
2. Copy the replacement files into the matching paths and add the new files.
3. Merge the new `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT` setting into your real `.env`; do not replace `.env` with `.env.example`.
4. Restart Arthur.
5. Test: “Open YouTube” → “Open it” (the second command can use context only when sharing is enabled), then ask a follow-up question.
6. Run the test suite with `python -m unittest discover -s tests -v`.

The speech replacement uses native Windows SAPI5 from a single COM-initialized worker thread. It retains the existing `say()`, priority queue, `wait_until_idle()`, and `close()` interface. It does not require a new dependency; `comtypes` is already present in `requirements-integrations.txt`.
