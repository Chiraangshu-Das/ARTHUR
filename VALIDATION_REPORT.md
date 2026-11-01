# Arthur Validation Report

**Validation date:** 2026-10-28  
**Project location:** `Arthur`  
**Environment:** Linux build/test container; Python 3.13 runtime for this verification pass. The project runtime baseline remains Python 3.11 x64 on Windows for the reference desktop application.

## Automated checks performed

| Check | Result |
|---|---|
| `python -m pytest -q` | **97 passed, 4 warnings** (existing FastAPI `@app.on_event` deprecation warnings) |
| `python -m py_compile main.py visionguide/*.py visionguide/integrations/*.py` | Passed |
| `python -m compileall -q main.py visionguide tools tests clients/python` | Passed |
| `python main.py --help` | Passed |
| Import desktop and FastAPI modules | Passed |
| Google Workspace scope/operation allowlist consistency | Passed (197 extended operations; all present in router schema) |
| Extended state-changing operations confirmation gate | Passed (all 118 extended write operations reject missing confirmation before OAuth/API setup) |

The tests cover existing command/API/memory and integration behavior plus new action history and profile preferences, deterministic voice intents, safe arithmetic, mocked Weather/Routes requests, route-mode parsing, Cloud Vision cache and quota behavior, encoded-polyline helpers, gesture calibration mapping, expanded web aliases, semantic-router operation coverage, scope profiles and confirmation guards.

External providers are mocked in automated tests; they do not prove access to the user's Google Cloud project or account.

## Important code paths in this release

- Gemini function-call routing with automatic tool execution disabled, deterministic command patterns, typed action registry and local safety validation.
- Literal typing versus safe arithmetic; Calculator launch/type workflow with an explicit caveat that its displayed result is not visually verified.
- One system-wide air virtual keyboard, mouse input, camera gesture pointer/pinch-click, vertical scroll and browser-tab swipes; keyboard and gestures are explicit opt-in.
- Consent-based local LBPH face profiles with optional DeepFace embedding fusion; conflicting matches resolve to unknown; per-profile preferences persist locally.
- Product research using OCR, Google Cloud Vision Web Detection and Gemini where configured, after explicit confirmation before camera image upload. Similar images/pages are leads, not identity verification.
- Capped/cached Google Geocoding, Weather and Routes calls plus Cloud Vision Web Detection; caps are local per-install safeguards and do not protect against other apps or project-wide costs.
- Best-effort Windows live-location route guidance with spoken maneuvers and off-route rerouting, subject to live provider/location availability.
- Bounded local action/result history for follow-up requests.
- Indian Sign Language (ISL) isolated-sign recognition using Torchvision Swin3D-S with a 76-class classifier. The checkpoint is loaded from `models/isl/swin3d_s/ISL_best_model.pt`. The recognizer processes 32 video frames and performs local inference. It supports isolated signs only, not continuous sentence translation.

## ISL model evaluation

The Swin3D-S model was independently evaluated using the available ISL dataset.

| Metric | Result |
|---|---:|
| Number of classes | 76 |
| Test samples | 187 |
| Top-1 accuracy | 80.75% (151/187) |
| Top-5 accuracy | 99.47% |
| Macro F1-score | 0.8150 |
| Weighted F1-score | 0.7854 |
| Approximate inference time | 400–410 ms |
| Approximate peak GPU memory | 925 MB |

Evaluation used a stratified random split. It was not signer-independent, so these results do not establish generalization to unseen signers. Some classes have limited test samples. Performance may vary with camera position, lighting, signing speed and individual signing style.

These metrics describe the independent model evaluation and should not be interpreted as proof of end-to-end live-camera recognition accuracy.

## Windows ISL runtime verification

The Windows Python 3.11 virtual environment was separately checked.

| Component | Installed version / result |
|---|---|
| PyTorch | 2.14.1+cu130 |
| Torchvision | 0.29.1+cu130 |
| CUDA availability | True |
| NumPy | 2.2.6 |
| OpenCV package (`opencv-contrib-python`) | 4.14.0.94 |
| Pillow | 13.0.0 |
| Scikit-learn | 1.9.1 |
| `pip check` | No broken requirements found |
| Required ISL package imports | Successful |

The environment satisfies the updated `requirements-signs.txt` dependency constraints. The CUDA-enabled PyTorch installation was retained.

These checks verify dependency availability and import compatibility, not complete live-camera integration or end-to-end recognition.

## Integration checks not run in this container

- Actual Windows GUI focus/paste, non-activating keyboard overlay behaviour, mouse injection, display/audio/network controls, camera gesture operation, webcam calibration and browser tab switching.
- Live location permission and GPS accuracy, real navigation, off-route rerouting and maneuver timing on the target Windows device.
- Actual Google API requests against the user's project, API enablement, key restrictions, billing status, and current account-level quotas/pricing. Tests use mocks; Google free allowances and pricing can change.
- Real Gemini/Cloud Vision image search with a user-approved image; live product pages/manual accuracy.
- Actual recognition metrics with consenting users on the target laptop; DeepFace is an optional heavy dependency and requires first-run model weights.
- Live Google OAuth and Workspace API calls, actual mobile build generation, and continuous sentence-level ISL translation. The current test container does not authenticate to a Google account and does not establish that all external APIs/scopes are enabled or approved.
- End-to-end live-camera Swin3D ISL recognition through Arthur's camera activation, recognition and spoken-output workflow.

These are field/provider acceptance checks, not automated tests. Do not treat passing unit tests as proof of end-to-end desktop operation, identity certainty, route safety, ISL recognition reliability or message delivery.

Before relying on navigation while moving, validate it on-device and keep a safe independent navigation method available.