
import cv2
import time
import queue
import threading
import pyttsx3
from ultralytics import YOLO

speech_queue = queue.Queue(maxsize=1)


def speech_worker():
    engine = pyttsx3.init()
    engine.setProperty("rate", 165)

    while True:
        message = speech_queue.get()

        if message is None:
            break

        try:
            print("Speaking aloud:", message)
            engine.say(message)
            engine.runAndWait()
        except Exception as error:
            print("TTS error:", error)

    engine.stop()


def announce(message):
    # Replace outdated pending announcements with the latest one.
    try:
        while True:
            speech_queue.get_nowait()
    except queue.Empty:
        pass

    try:
        speech_queue.put_nowait(message)
    except queue.Full:
        pass


def main():
    model = YOLO("yolo26n.pt")

    speech_thread = threading.Thread(
        target=speech_worker,
        daemon=True
    )
    speech_thread.start()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Could not open webcam.")
        announce("Could not open camera")
        speech_queue.put(None)
        return

    previous_detections = {}
    last_announcement = 0
    announcement_interval = 3

    print("Arthur AI running. Press Q to quit.")

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break

            height, width = frame.shape[:2]

            results = model.predict(frame, conf=0.30, verbose=False)
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    name = model.names[class_id]

                    print(f"Detected: {name} ({confidence:.2f})")
            current_detections = {}

            for box in results[0].boxes:
                class_id = int(box.cls[0])
                label = model.names[class_id]

                x1, y1, x2, y2 = map(
                    int, box.xyxy[0].tolist()
                )

                center_x = (x1 + x2) / 2

                if center_x < width / 3:
                    direction = "left"
                elif center_x > 2 * width / 3:
                    direction = "right"
                else:
                    direction = "centre"

                key = (label, direction)
                current_detections[key] = (
                    current_detections.get(key, 0) + 1
                )

                text = f"{label} {direction}"

                cv2.rectangle(
                    frame, (x1, y1), (x2, y2),
                    (0, 255, 0), 2
                )
                cv2.putText(
                    frame, text,
                    (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 2
                )

            now = time.time()

            # Announce a new object/direction, then repeat
            # the current scene periodically if nothing changes.
            new_items = [
                key for key in current_detections
                if key not in previous_detections
            ]

            if new_items and now - last_announcement >= announcement_interval:
                label, direction = new_items[0]
                announce(f"{label} on your {direction}")
                last_announcement = now

            elif (
                current_detections
                and now - last_announcement >= 6
            ):
                label, direction = max(
                    current_detections,
                    key=current_detections.get
                )
                announce(f"{label} at the {direction}")
                last_announcement = now

            previous_detections = current_detections

            cv2.imshow("Arthur AI", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        announce("Arthur stopped")
        # Allow queued speech to finish before shutting down.
        speech_queue.join if False else None
        speech_queue.put(None)
        speech_thread.join(timeout=10)


if __name__ == "__main__":
    main()
