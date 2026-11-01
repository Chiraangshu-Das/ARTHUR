# Arthur — public research and architecture decisions

Research pass performed on 24 October 2026 using official product support pages, model cards, upstream GitHub repositories, a public ISL dataset catalogue, and official API documentation. This is a targeted engineering review, not a systematic benchmark or a review of every forum thread. No physical-scene accuracy test has been performed with the user's camera.

## What existing products already do

| Product | Capabilities documented by the vendor | Design implication for Arthur |
|---|---|---|
| Microsoft Seeing AI | Focused channels for text/documents, products, scenes and enrolled people, plus richer scene descriptions and document chat. | Keep user-triggered tasks and focused modes; OCR should be a separate operation from general scene description. |
| Google Lookout | Text, documents, currency, food labels, image descriptions and a Find-object mode; Explore is explicitly marked beta/less accurate in current help. | Make object search a first-class command and avoid claiming all scene perception is equally reliable. |
| Envision Glasses | Scan text, batch scan, describe scene, find objects/people, face teaching, colours and companion/agent workflows. | Model personal memory as explicit user-controlled data; have a distinct scene-Q&A workflow. |
| OrCam MyEye 3 Pro | Reads printed/screen text, recognises enrolled faces and products, finds requested words, and includes interactive AI magnification features. | Build OCR word lookup as a first-class capability, rather than treating a page as just an image caption. |
| Ray-Ban Meta | Hands-free visual Q&A and creative/general assistant use; the official FAQ describes cloud processing of camera images. | Make cloud uploads explicit and disclose when image frames or text are sent off-device. |
| Aira | Live human visual interpretation by trained agents through a phone camera, rather than an all-AI model. | Human assistance is a valuable fallback for high-stakes/ambiguous navigation, but is outside this offline prototype. |

Official links:

- Seeing AI: <https://blogs.microsoft.com/accessibility/seeing-ai-app-launches-on-android-including-new-and-updated-features-and-new-languages/>
- Lookout: <https://support.google.com/accessibility/android/answer/9031274>
- Envision scene description and follow-up: <https://support.letsenvision.com/hc/en-us/articles/7603823400849-Describe-Scene>
- Envision Professional Edition features: <https://shop.letsenvision.com/en-in/products/glasses-professional>
- OrCam MyEye 3 Pro: <https://www.orcam.com/en-gb/orcam-myeye-3-pro>
- Ray-Ban Meta FAQ: <https://india.ray-ban.com/ray-ban-meta-faq>
- Aira human assistance: <https://www.aira.io/>

These feature pages do **not** establish that any product offers a single, general, validated system that combines monocular metric distance, collision prediction, free-form air keyboard, and general sign-language translation. Product features and availability vary by hardware, software version, country, language and subscription.

## Upstream open-source components applied

### 1. Depth Anything V2 Metric Small — indoor Hypersim

- Upstream code: <https://github.com/DepthAnything/Depth-Anything-V2/tree/main/metric_depth>
- Metric indoor Small checkpoint: <https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small>
- The model card lists Apache-2.0 for the Small metric checkpoint and a 99.2 MB file. The corresponding model is intended for indoor metric-depth estimation from the Hypersim training setup; a different model exists for outdoor Virtual KITTI 2 scenes.
- Applied: model setup/downloader, depth map inference, robust median sampling in the interior of detected object boxes, one-point scale calibration, and temporal radial-depth-change heuristic.
- Not claimed: a camera-calibration guarantee, accurate steps for every user, reliable outdoor estimates or a validated safety system. The prototype's single-point scale factor cannot correct every object- and scene-dependent model error.

### 2. MediaPipe Hand Landmarker

- Official guide: <https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer>
- Applied: hand landmarks for explicit air-mouse cursor control and gesture-based interaction with the unified air virtual keyboard. Gesture control is an opt-in interaction mode with activation and disable controls.
- The current air-gesture implementation includes pointer movement, pinch-click, scrolling, browser-tab swipes, smoothing and calibration. The virtual keyboard is integrated into the desktop interaction workflow.
- Not claimed: a complete gesture vocabulary, sign-language understanding or reliable focus preservation in every third-party application. Gesture tracking is not the same task as recognizing a natural sign language.
- MediaPipe is not the active ISL inference architecture. The current ISL classifier uses a separate video-based Swin3D model.

### 3. Current Indian Sign Language classifier — Swin3D-S

- Architecture: Torchvision `swin3d_s`, configured for 76 output classes.
- Checkpoint: `models/isl/swin3d_s/ISL_best_model.pt`.
- Dataset directory used by the current training/evaluation workflow: `data/isl_dataset/ProcessedData_vivit`.
- Inference uses a 32-frame video clip, with local preprocessing and model execution.
- Applied: an isolated-sign classification pipeline with a local checkpoint and a limited vocabulary. The current inference path is separate from MediaPipe gesture tracking.
- Not claimed: continuous sentence interpretation, ISL grammar translation, signer-independent generalization, or communication-grade performance. A 76-class isolated-sign classifier is not a continuous ISL translation system.
- Independent evaluation results should be reported with their methodology and limitations. A random stratified video split is not equivalent to a signer-held-out evaluation and does not establish generalization to unseen signers.

**Dataset provenance limitation:** The Amrita SLR dataset catalogue below is a research reference, but its presence in this document does not establish that the current Swin3D checkpoint was trained on that dataset. Confirm the actual checkpoint training data, source, licensing and preprocessing provenance before attributing the current model to a particular dataset.

### 4. Amrita SLR — Real Time ISL Dataset (research reference)

- Dataset page: <https://data.mendeley.com/datasets/dtg9s785v8/1>
- Dataset record lists 50 common ISL signs, approximately 16 recordings per class and seven signers; it is about 1.36 GB and licensed CC BY 4.0 according to the record.
- This is a potentially relevant public dataset reference for ISL research. It should not be represented as the confirmed source of the current Swin3D checkpoint without training records or other provenance evidence.
- The earlier landmark-sequence/LSTM approach is not the current ISL inference architecture.

### 5. OpenCV, Tesseract, SQLite and Whisper

- OpenCV packaging/licensing: <https://github.com/opencv/opencv-python>
- Tesseract OCR: <https://github.com/tesseract-ocr/tesseract>
- Whisper: <https://github.com/openai/whisper>
- Applied: camera/video capture, image preprocessing and perspective-correction attempt, local OCR wrapper, local notes memory using SQLite, and locally run Whisper transcription.
- These components serve distinct functions. OpenCV handles image/video processing, Tesseract provides OCR, SQLite stores local notes, and Whisper handles speech transcription. Their presence does not by itself establish end-to-end accuracy or reliability.

### 6. YOLO26 / Ultralytics license

- Upstream repository: <https://github.com/ultralytics/ultralytics>
- Ultralytics currently describes AGPL-3.0 and a separate enterprise license. The user's existing `yolo26n.pt` file is preserved for continuity.
- A permissively licensed end-to-end application cannot be assumed while relying on this component; confirm current terms for redistribution/commercial use.

## Specific engineering changes from research

1. **User-commanded speech:** The app has no startup spoken greeting or continuous narration. Online image requests and microphone recording require separate user actions; image sharing requires confirmation.
2. **Separate local and online reasoning:** Local YOLO summaries work without an API key; Gemini can describe visual details and answer general questions only after an explicit request. Text-only AI does not attach a camera image.
3. **Depth separated from detection:** Depth is an opt-in model because it is large and can be slow. Calibration is stored separately and marked approximate.
4. **Safety logic is cautious:** Depth alerts require several temporal samples, plausible closing motion, range limits and a cooldown. This is a heuristic and remains off by default; it is not a validated collision predictor.
5. **Personal memory is local and explicit:** User notes are written to SQLite only when requested, searchable, and deletable. Face recognition is limited to consented local enrollment; no stranger face-search service is called.
6. **Hand control is opt-in:** Air mouse and air keyboard are explicit interaction modes. The unified virtual keyboard is integrated with the desktop control workflow. Focus preservation and safe interaction with arbitrary third-party applications remain validation requirements.
7. **Sign-language claims are constrained:** The current code provides a Swin3D-based training/inference pipeline for a limited isolated ISL vocabulary. It requires the dataset and model assets to be available locally. MediaPipe hand landmarks alone do not produce sign-language translation, and the current isolated-label classifier does not provide continuous sentence translation.

## What still requires empirical research and validation

- Real-world distance error distributions over indoor/outdoor scenes and different camera lenses; comparison against a physical tape measure or calibrated range sensor.
- Motion prediction under camera motion, occlusion, track swaps and intersecting vs non-intersecting trajectories.
- Human-subject usability review with blind and low-vision users and orientation-and-mobility professionals.
- Signer-separated validation and review by fluent ISL users before sign predictions are used in conversation.
- Verification of the current Swin3D checkpoint's dataset provenance, training procedure, license and signer distribution.
- Native phone/Android/iOS/smart-glasses client, latency/power measurements and offline speech output suited to the eventual hardware.
- Privacy, consent, retention, security and regional legal review before any release that stores biometric or location-related data.