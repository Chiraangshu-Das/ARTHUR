# Indian Sign Language (ISL) Architecture

## Scope

Arthur's sign-language scope is Indian Sign Language only. The current isolated-sign classifier pipeline remains a supported component. The architecture also defines distinct adapters for continuous ISL-to-text translation and text-to-ISL presentation.

Sign recognition and sign generation are separate machine-learning problems and must use ISL-specific datasets, models, annotation conventions, validation and language expertise. A sequence of isolated labels is not automatically a grammatical ISL sentence.

The current isolated-sign classifier is a video-based Swin3D-S model. Continuous ISL-to-text translation and text-to-ISL presentation remain separate architectural capabilities and must not be represented as implemented merely because their adapter contracts are documented.

## 1. Isolated-sign classifier pipeline

The existing Python sign module, `visionguide/sign_language.py`, is the initial isolated-sign integration path.

### Current implementation

- **Architecture:** Torchvision Swin3D-S video classifier.
- **Class count:** 76 isolated-sign classes.
- **Checkpoint:** `models/isl/swin3d_s/ISL_best_model.pt`.
- **Dataset directory:** `data/isl_dataset/ProcessedData_vivit`.
- **Inference input:** A temporal clip of 32 frames, rather than a single still image.
- **Processing:** Resize the shortest edge to 256 pixels while preserving aspect ratio, center-crop to 224 × 224, convert to RGB, and normalize pixel values to the `[-1, 1]` range.
- **Tensor layout:** `[B, C, T, H, W]`.
- **Execution:** Local PyTorch/Torchvision inference.

The checkpoint uses a 76-class classification head. Its `classification_head.0.` parameters are mapped to the Torchvision model's `head.` parameters during loading.

### Intended inference workflow

1. Capture a bounded sequence of camera frames.
2. Prepare a 32-frame clip using the preprocessing configuration associated with the trained checkpoint.
3. Run Swin3D-S inference locally.
4. Return the predicted class label and confidence.
5. Return `unknown/reject` when confidence is below the configured threshold.
6. Display the predicted label and allow the user to correct it. Speak only when the user has enabled speech output for sign recognition.

The current integration uses a background inference worker that collects frames and schedules predictions. The application handles repeated-label suppression and sign-mode state.

### Dataset and model requirements

Maintain a model manifest containing:

- Dataset name, source URL and provenance.
- Dataset licence and permitted uses.
- Signer consent and relevant data restrictions.
- Class names and versioned label map.
- Checkpoint hash and model architecture.
- Preprocessing configuration and version.
- Training and evaluation split methodology.
- Device requirements and dependency versions.
- Last validation date and known limitations.

Dataset labels describe the collected vocabulary. They must not imply that the model understands arbitrary connected signing, facial grammar or context unless those behaviours are explicitly trained and evaluated.

The current 76-class classifier supports isolated-sign recognition only. It is not a continuous sentence translator.

## 2. Continuous ISL-to-text adapter

Continuous ISL-to-text translation is a separate model and integration path. It must not be implemented by simply concatenating predictions from the isolated-sign classifier.

The stable interface accepts a bounded sequence from the client camera and returns structured output:

```json
{
  "task_id": "string",
  "language": "ISL",
  "text": "recognized/translated text",
  "gloss_sequence": ["..."],
  "confidence": 0.0,
  "alternatives": [],
  "model_id": "string",
  "warnings": [],
  "needs_correction": false
}
```

`gloss_sequence` may be empty when the model produces text directly. Values must never be fabricated merely to fill a field. Preserve timestamps where the model provides alignment.

The client must show confidence and uncertainty, allow correction, and distinguish a raw recognized gloss sequence from a translated natural-language sentence.

### Research and data sources

- **ISLTranslate** describes ISL-English sentence/phrase pairs and translation benchmarks: <https://aclanthology.org/2023.findings-acl.665/>. Treat this as a research dataset/benchmark and confirm the applicable dataset conditions before use.
- **ISH-NEWS** describes ISL sentence-video research and a transformer baseline: <https://www.nature.com/articles/s41598-026-60893-0>. Source-video redistribution and dataset-use restrictions must be reviewed independently.
- **Sid-V5/isl-translator** describes a continuous ISL recognition pipeline: <https://github.com/Sid-V5/isl-translator>. Evaluate its current code, checkpoint availability, licence, dependency constraints and GPU requirements before integrating it. Do not equate a repository description or published metric with validation on the Arthur client.

These are research references, not proof that their models or datasets are already integrated into Arthur.

The project must keep a model manifest recording checkpoint hash, source URL, licence, training/evaluation datasets, preprocessing version, device requirements and last validation date. Research metrics must be reproduced or cited accurately and must not be presented as real-world guarantees.

## 3. Text-to-ISL presentation adapter

Text-to-sign requires its own ISL-appropriate linguistic pipeline and rendering output, for example, a validated signer video sequence or a signing avatar.

It must not simply map every English word to a sign clip or reuse material from another sign language. The adapter contract should accept target text plus the chosen output mode, then return ISL-specific clip/pose/sequence metadata and clear limitations.

Validate translations with fluent ISL signers and Deaf-community reviewers. Preserve grammar, non-manual signals, two-handed articulation and spatial agreement where the representation supports them.

When no supported signing is available, ask for a simpler rephrasing or state that the requested expression is not represented. Do not invent a sign.

Text-to-ISL generation is a separate capability; the existence of the isolated-sign recognition model does not provide this functionality.

## 4. Evaluation and user experience

- Split evaluation by signer, not just by randomly shuffled clips, to measure generalization to unseen signers.
- Test natural connected signing, different lighting/backgrounds, signing speed, occlusion, one- and two-handed signs, clothing, camera distance and front-facing/side angle.
- Report word error rate or sentence-level metrics when suitable; document vocabulary coverage, signer count, environment and failure categories.
- For isolated-sign classification, report top-1/top-5 accuracy, macro and weighted F1, per-class performance, confusion patterns and inference latency.
- Add correction and retry controls. Do not automatically send a predicted sign translation to another person without showing the user what will be sent.
- Keep video local unless a chosen service requires a remote transfer and the user confirms it.
- Do not advertise the system as a certified interpreter or safety-critical communication service solely because a model produces text.

### Current isolated-classifier evaluation limitations

The previously reported Swin3D-S evaluation recorded:

| Metric | Reported result |
|---|---:|
| Top-1 accuracy | 80.75% |
| Top-5 accuracy | 99.47% |
| Macro F1 | 0.8150 |
| Weighted F1 | 0.7854 |
| Inference time | Approximately 400–410 ms |
| Peak GPU memory | Approximately 925 MB |

These results came from a stratified random split, not a signer-held-out evaluation. They therefore do not establish generalization to unseen signers. Some classes also have very small test samples.

These are isolated-classifier evaluation results, not continuous translation metrics or evidence of live-camera integration.

## 5. Relationship to other vision components

ISL recognition and gesture control may share camera infrastructure, but they have different capture requirements and interaction semantics.

- The current ISL classifier uses the Swin3D-S temporal video pipeline.
- MediaPipe remains part of Arthur's gesture-control pipeline; it is not the current Swin3D ISL inference model.
- Gesture mouse and sign recognition must have separate mode handling.
- A hand-click event must not trigger sign classification unintentionally.
- Hand-landmark debug output must never be exposed as a sign translation.
- Use a single capture broker with explicit modes and mutual exclusion where simultaneous camera consumers are unsupported.

The application must make the active camera mode clear and release camera resources when the corresponding mode is stopped.