from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split
from tensorflow.keras import layers, models, callbacks

PROJECT = Path(__file__).resolve().parents[1]
SEQUENCE_LENGTH = 32


def extract_video(path: Path, holistic) -> np.ndarray | None:
    capture = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok: break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = holistic.process(rgb)
        values = []
        if result.pose_landmarks:
            for p in result.pose_landmarks.landmark:
                values.extend([p.x, p.y, p.z, p.visibility])
        else: values.extend([0.0] * 132)
        for hand in (result.left_hand_landmarks, result.right_hand_landmarks):
            if hand:
                for p in hand.landmark: values.extend([p.x, p.y, p.z])
            else: values.extend([0.0] * 63)
        frames.append(values)
    capture.release()
    if len(frames) < 8: return None
    indices = np.linspace(0, len(frames)-1, SEQUENCE_LENGTH).astype(int)
    return np.asarray([frames[i] for i in indices], dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description="Train an isolated-sign ISL vocabulary classifier")
    parser.add_argument("--data", default="data/isl_videos", help="Folder containing one label subfolder per sign")
    parser.add_argument("--epochs", type=int, default=70)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    data_dir = Path(args.data)
    if not data_dir.is_absolute(): data_dir = PROJECT / data_dir
    if not data_dir.is_dir():
        raise SystemExit(f"Dataset folder does not exist: {data_dir}\nExpected data/isl_videos/<SIGN_LABEL>/*.mp4")
    classes = sorted(p for p in data_dir.iterdir() if p.is_dir())
    if len(classes) < 2: raise SystemExit("At least two sign-label folders are needed.")

    all_samples, all_labels = [], []
    holistic = mp.solutions.holistic.Holistic(static_image_mode=True, model_complexity=0,
        enable_segmentation=False, refine_face_landmarks=False, min_detection_confidence=0.5)
    try:
        for label_index, folder in enumerate(classes):
            videos = [p for p in folder.rglob('*') if p.suffix.lower() in {'.mp4','.avi','.mov','.mkv'}]
            print(f"{folder.name}: {len(videos)} videos")
            for video_path in videos:
                features = extract_video(video_path, holistic)
                if features is not None:
                    all_samples.append(features)
                    all_labels.append(label_index)
    finally:
        holistic.close()
    if len(all_samples) < max(20, len(classes) * 4):
        raise SystemExit("Too few usable videos. Need multiple varied samples per sign; do not use this for real-world safety-critical translation.")

    X = np.asarray(all_samples, dtype=np.float32)
    y = np.asarray(all_labels, dtype=np.int32)
    counts = np.bincount(y, minlength=len(classes))
    if np.any(counts < 2):
        raise SystemExit("Every sign class needs at least two usable video samples to split train/validation.")
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    model = models.Sequential([
        layers.Input(shape=(SEQUENCE_LENGTH, 258)),
        layers.Masking(mask_value=0.0),
        layers.LSTM(96, return_sequences=True),
        layers.Dropout(0.25),
        layers.LSTM(64),
        layers.Dropout(0.25),
        layers.Dense(64, activation='relu'),
        layers.Dense(len(classes), activation='softmax'),
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    model_dir = PROJECT / 'models'
    model_dir.mkdir(parents=True, exist_ok=True)
    callback_list = [callbacks.EarlyStopping(monitor='val_accuracy', patience=12, restore_best_weights=True)]
    model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=args.epochs,
              batch_size=args.batch_size, callbacks=callback_list, verbose=1, shuffle=True)
    loss, accuracy = model.evaluate(X_val, y_val, verbose=0)
    model.save(model_dir / 'isl_lstm.keras')
    (model_dir / 'isl_labels.json').write_text(json.dumps([p.name for p in classes], indent=2), encoding='utf-8')
    print(f"Saved {model_dir / 'isl_lstm.keras'} and labels; held-out split accuracy={accuracy:.3f}")
    print("Important: this random video split is a development check, not signer-independent or production validation.")

if __name__ == '__main__': main()
