# ARTHUR — YouTube Context Playback Add-on

This add-on is designed for the ARTHUR source after applying `ARTHUR_Complete_Repair_Patch_v2.zip`.

## Install

1. Close ARTHUR.
2. Back up your current ARTHUR project folder.
3. Extract this ZIP.
4. Copy the extracted files into the existing ARTHUR project root, preserving the folder structure and allowing the included source files to be replaced.
5. Do not replace `.env`, `.venv`, `data/`, `models/`, `credentials/`, or downloaded model files.

No dependency-manifest changes are required. The feature uses the existing `requests` dependency already declared by the project.

## Use

1. Say: `Search YouTube for Taylor Swift songs`.
2. Then say: `Play the first video` or `Play the second video`.
3. Other supported selection forms include `Open result number 3`, `Watch video number 2`, and `Play a video` (which selects result 1).
4. After a video opens, say `Pause it`, `Play it`, `Skip forward 30 seconds`, or `Go back 10 seconds`.

ARTHUR remembers only the most recent YouTube search it launched during the current running session. A manually typed search or a search from before ARTHUR was restarted is not used for result selection.

The feature retrieves the public YouTube search-result page, extracts the ordered video IDs/titles, and opens the selected watch page with `autoplay=1`. YouTube/browser autoplay policy can still block automatic playback; in that case, click the player once. ARTHUR does not attempt to bypass autoplay policy.

## Validation

From the ARTHUR project root in its activated virtual environment:

```powershell
python -m compileall -q visionguide tests
python -m pytest -q
```

The merged source tree was validated with 127 passing tests and four existing FastAPI lifecycle deprecation warnings. Live YouTube responses and autoplay behavior still need to be validated on the target browser/network.
