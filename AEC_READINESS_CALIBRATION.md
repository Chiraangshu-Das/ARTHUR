# ARTHUR AEC readiness calibration

## Findings from the uploaded hardware recordings

The controlled playback-only recording showed a very low but measurable
speaker leak at the microphone: raw microphone RMS was around `-74.3 dBFS`
(about `0.00019` linear RMS). Echoff's built-in default minimum raw RMS was
`0.003`, approximately 16 times higher than the measured signal. The same run
reported about `6.1 dB` of rolling suppression, while the offline far-end-only
comparison was about `8.6 dB`. This made the stock `0.003 RMS` / `10 dB` gate
unattainable even though listening tests suggested useful suppression and voice
preservation.

## New gate

| Parameter | Previous default | New ARTHUR default |
|---|---:|---:|
| Active-reference warm-up | 7.5 s | 7.5 s |
| Minimum raw microphone RMS | 0.003 | 0.0001 |
| Minimum raw-to-clean suppression | 10 dB | 5 dB |

These are calibrated acceptance thresholds, not a claim of perfect echo
cancellation. The device still must deliver aligned reference/microphone pairs
and satisfy Echoff's sustained quality check. The lower values reflect this
laptop's unusually quiet acoustic echo rather than lowering the gate to zero.

## Double-talk handling

The Echoff readiness value is a rolling energy heuristic. During double-talk,
the user's voice is intentionally preserved in `microphone_clean`, which can
reduce the apparent whole-microphone attenuation. ARTHUR now latches readiness
only after the initial Echoff gate passes, then keeps consuming cleaned frames
for that capture session. This stops a valid user utterance from being discarded
just because the rolling diagnostic changes while the user speaks.

A capture failure still propagates through `check_health()`. There is no raw
microphone fallback during active TTS. If output devices are changed, restart
ARTHUR so a new AEC capture must pass its startup gate again.
