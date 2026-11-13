# ARTHUR — Live preferred-name personalization

This update connects the preferred-name value stored against an enrolled face profile to ARTHUR's live response pipeline.

## Behaviour

1. When face enrollment completes, that profile becomes the active profile for the current session.
2. Say: `Arthur, I prefer you to call me Chiraangshu.` The local semantic router now recognizes this exact phrase and routes it to `profile_preference_set`.
3. ARTHUR stores the preference in the existing local SQLite preferences table in `data/action_history.sqlite3`, keyed by the enrolled profile's stable slug.
4. ARTHUR immediately refreshes its in-memory active preferred name. No restart is required.
5. All application speech is routed through the personalization layer. Direct-address uses of `sir` are replaced with the stored preferred name; short assistant replies are naturally addressed to that name. Long read-aloud content such as OCR/document/memory text is not prefixed.
6. When face recognition later identifies that enrolled profile, ARTHUR reloads the preference from SQLite. Face recognition is privacy-controlled and must be enabled after restart for automatic profile recognition.

## Multiple profiles

If exactly one face profile is enrolled, ARTHUR uses that profile for the preference command. If multiple profiles exist and no face is active, ARTHUR asks which profile should receive the preference (by voice during an active voice conversation, otherwise through a dialog).

## Privacy and scope

- The preferred name and face profile link are stored locally.
- This feature does not send face images or saved preferences to Groq.
- It does not hardcode any person's name in application source.
- The helper only replaces `sir` when it appears as a direct salutation (for example, `Yes, sir?`); it does not rewrite titles such as `Sir Isaac Newton`.
- Automated tests verify the exact natural-language preference phrase, salutation replacement, duplicate-name avoidance, and preservation of raw content.

## Test

From the project root, in the active virtual environment:

```powershell
python -m compileall -q visionguide tests
python -m pytest -q
```
