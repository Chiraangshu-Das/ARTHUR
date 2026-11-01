# Third-Party Notices

Arthur combines separately licensed packages, services, datasets and model files. Each component retains its own licence and use conditions. This inventory is a pointer list, not legal advice; review exact versions, checkpoint licences, dataset consent, attribution requirements and provider terms before redistribution or commercial deployment.

A component being listed here does not necessarily mean that it is bundled with Arthur or enabled at runtime. Research references and potential future integrations are identified separately from active dependencies.

## Runtime packages, tools and services

| Component | Use in Arthur | Licence / terms pointer |
|---|---|---|
| Ultralytics YOLO26 package and supplied `yolo26n.pt` model | Local object detection and tracking | Ultralytics documents AGPL-3.0 and a separate enterprise licence: <https://github.com/ultralytics/ultralytics> |
| Depth Anything V2 Metric Hypersim Small checkpoint | Indoor metric-depth estimates; downloaded separately | Model card lists Apache-2.0: <https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small> |
| Depth Anything V2 upstream source | Depth inference source downloaded by `tools/setup_depth_model.py` | Upstream repository/licence: <https://github.com/DepthAnything/Depth-Anything-V2> |
| MediaPipe | Hand landmarks and gesture control | Google AI Edge / MediaPipe source and licence: <https://github.com/google-ai-edge/mediapipe> |
| OpenCV | Camera capture, image processing and OCR preprocessing | OpenCV licence and Python package notices: <https://github.com/opencv/opencv-python> |
| Tesseract OCR | Local OCR engine; installed separately | <https://github.com/tesseract-ocr/tesseract> |
| OpenAI Whisper | Local speech-to-text | <https://github.com/openai/whisper> |
| PyAutoGUI | Explicit desktop cursor, click and keyboard control | <https://github.com/asweigart/pyautogui> |
| pygetwindow | Enumerating and activating desktop windows | <https://github.com/asweigart/PyGetWindow> |
| screen-brightness-control | Windows display brightness access | <https://pypi.org/project/screen-brightness-control/> |
| Pycaw and comtypes | Windows Core Audio volume/mute control | <https://github.com/AndreMiras/pycaw> and <https://github.com/enthought/comtypes> |
| pyperclip | Clipboard paste for multilingual GUI text | <https://pypi.org/project/pyperclip/> |
| FastAPI / Uvicorn | REST/WebSocket service layer | <https://fastapi.tiangolo.com/> |
| Google Gen AI Python SDK | Gemini function calling, text and visual Q&A | <https://github.com/googleapis/python-genai> |
| SentenceTransformers / all-MiniLM-L6-v2 | Local semantic similarity fallback; model-card licensing applies separately | <https://www.sbert.net/> and <https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2> |
| Pydantic | API request schema validation | <https://docs.pydantic.dev/> |
| Python multipart parser | FastAPI multipart audio uploads | <https://github.com/Kludex/python-multipart> |
| Flutter `http`, `web_socket_channel`, `speech_to_text`, `record`, `path_provider` | Mobile API, notification, speech capture and temporary audio file flows | <https://pub.dev/>; review each pinned package's current licence and platform permission requirements |
| Google API Python client and OAuth libraries | Gmail and Calendar account integrations | <https://github.com/googleapis/google-api-python-client> |
| openWakeWord | Local wake-word runtime; model files have independent terms | <https://github.com/dscripka/openWakeWord> |
| Google Gemini API | Hosted function calling, text response and visual Q&A | Provider API terms, privacy and quotas apply: <https://ai.google.dev/gemini-api/terms> |

## Indian Sign Language (ISL) recognition

Arthur's current isolated-sign recognition pipeline uses Torchvision Swin3D-S rather than the previous MediaPipe Holistic + TensorFlow LSTM architecture.

| Component | Use in Arthur | Licence / terms pointer |
|---|---|---|
| PyTorch | Deep-learning inference for the Swin3D ISL recognizer | <https://github.com/pytorch/pytorch> |
| Torchvision | Swin3D-S video classification architecture and model operations | <https://github.com/pytorch/vision> |
| `ISL_best_model.pt` | Trained 76-class Swin3D-S checkpoint at `models/isl/swin3d_s/ISL_best_model.pt` | Record the checkpoint's training provenance, creator, source, dataset terms and redistribution permission in the model manifest. Do not assume that the framework licence automatically covers the checkpoint. |
| Pillow | Image processing used by the ISL preprocessing pipeline | <https://github.com/python-pillow/Pillow> |
| NumPy | Frame and tensor preprocessing support | <https://github.com/numpy/numpy> |
| scikit-learn | Dataset evaluation and classification metrics | <https://github.com/scikit-learn/scikit-learn> |

The current ISL recognizer uses a 76-class isolated-sign classifier. It does not provide continuous sentence-level ISL translation.

The previous MediaPipe Holistic + TensorFlow LSTM pipeline is not the active Swin3D inference architecture. MediaPipe remains listed above for gesture-control functionality.

### Dataset and research references

The following references concern ISL datasets or research implementations. Their presence in this document does not mean that they are bundled with Arthur or used by the current runtime.

| Resource | Purpose / status | Licence / terms pointer |
|---|---|---|
| Amrita SLR dataset | Isolated-sign ISL training data reference. Verify that this is the actual source of the data used to train the current Swin3D checkpoint before attributing it to the model. | Dataset record lists CC BY 4.0; provide attribution and follow its terms: <https://data.mendeley.com/datasets/dtg9s785v8/1> |
| Sid-V5/isl-translator | Continuous ISL research implementation candidate; not a bundled runtime dependency. | Upstream README identifies MIT; verify the obtained commit, checkpoints and dependencies: <https://github.com/Sid-V5/isl-translator> |
| ISLTranslate | Research dataset for continuous ISL translation; not identified as a current runtime dependency. | <https://aclanthology.org/2023.findings-acl.665/>; verify release terms on the actual dataset |
| ISH-NEWS research | Sentence-level ISL research reference; not identified as a current runtime dependency. | <https://www.nature.com/articles/s41598-026-60893-0>; follow the article's data availability statement |

Before redistributing the Swin3D checkpoint, document:
- The original dataset and dataset version.
- The dataset's licence, attribution and consent requirements.
- Any preprocessing, filtering or augmentation applied.
- The checkpoint creator and training provenance.
- Whether redistribution or commercial use of the trained weights is permitted.
- The checkpoint checksum and model evaluation details.

## Downloaded and separately installed assets

The following assets are not necessarily included in the project archive:

- `vendor/Depth-Anything-V2/` is downloaded by the depth-model setup script.
- `models/depth_anything_v2_metric_hypersim_vits.pth` is downloaded separately.
- Tesseract OCR is installed as a separate system dependency.
- Other model weights may be downloaded or generated during setup.

The supplied `yolo26n.pt` is retained in the archive.

No trained continuous-ISL sentence checkpoint or custom wake-word ONNX file is bundled.

## Licence and redistribution considerations

- Review the exact licence for every pinned package version and downloaded model checkpoint.
- Some packages and models may impose obligations beyond those of the Python package that loads them.
- Hosted services such as Gemini and Google APIs are governed by provider terms, privacy policies, quotas and billing conditions.
- Dataset licences may require attribution, impose restrictions on redistribution or require additional consent for derived model weights.
- Do not assume that a publicly accessible repository or model download automatically permits commercial use or redistribution.
- Keep third-party notices, licence texts and required attribution with redistributed builds where applicable.

Record any later-added model's checksum, source, licence, dataset, creator and evaluation details in its model manifest.