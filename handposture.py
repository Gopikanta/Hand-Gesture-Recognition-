import cv2
import mediapipe as mp
import time
import os
import urllib.request

# ── Download model if not present ────────────────────────────────────────────
MODEL_PATH = "hand_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print("Downloading hand landmark model... please wait")
    url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    urllib.request.urlretrieve(url, MODEL_PATH)
    print("Model downloaded successfully!")

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

FINGER_TIPS = [4, 8, 12, 16, 20]
FINGER_PIPS = [3, 6, 10, 14, 18]

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17)
]

def get_label_from_position(landmarks):
    """
    When palm faces camera and frame is mirrored:
    - Right hand → thumb appears on LEFT side of screen
    - Left hand  → thumb appears on RIGHT side of screen
    So we flip the logic: thumb LEFT = Right hand.
    """
    thumb_base = landmarks[2].x
    pinky_base = landmarks[18].x
    if thumb_base < pinky_base:
        return "Right"   # thumb on left side of screen = right hand (palm facing)
    else:
        return "Left"    # thumb on right side of screen = left hand (palm facing)

def count_fingers(landmarks, label):
    up = []
    # Thumb
    if label == "Right":
        up.append(1 if landmarks[4].x < landmarks[3].x else 0)
    else:
        up.append(1 if landmarks[4].x > landmarks[3].x else 0)
    # Four fingers
    for tip, pip in zip(FINGER_TIPS[1:], FINGER_PIPS[1:]):
        up.append(1 if landmarks[tip].y < landmarks[pip].y else 0)
    return up

def get_gesture(fingers):
    gestures = {
        (0,0,0,0,0): "Fist",
        (1,1,1,1,1): "Open Hand",
        (0,1,0,0,0): "Index Up",
        (0,1,1,0,0): "Peace",
        (1,0,0,0,1): "Call Me",
        (1,1,0,0,1): "Rock On",
        (1,0,0,0,0): "Thumbs Up",
        (0,0,0,0,1): "Pinky Up",
        (0,1,1,1,1): "Four Fingers",
        (1,1,1,1,0): "Four + Thumb",
    }
    return gestures.get(tuple(fingers), "Custom")

def draw_landmarks(frame, landmarks, h, w):
    points = []
    for lm in landmarks:
        cx, cy = int(lm.x * w), int(lm.y * h)
        points.append((cx, cy))
        cv2.circle(frame, (cx, cy), 5, (0, 255, 180), -1)
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, points[a], points[b], (255, 255, 255), 2)

def run():
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    detector = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    prev_time = 0
    print("Hand Tracker running... Press Q to quit.")

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect(mp_image)

        cur_time = time.time()
        fps = 1 / (cur_time - prev_time + 1e-9)
        prev_time = cur_time

        cv2.rectangle(frame, (0, 0), (w, 60), (15, 15, 15), -1)
        cv2.putText(frame, "Hand Tracker", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 180), 2)
        cv2.putText(frame, f"FPS: {int(fps)}", (w - 130, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 180), 2)

        if result.hand_landmarks:
            for hand_lm in result.hand_landmarks:

                label = get_label_from_position(hand_lm)
                color = (0, 255, 180) if label == "Right" else (255, 120, 0)

                draw_landmarks(frame, hand_lm, h, w)

                fingers = count_fingers(hand_lm, label)
                gesture = get_gesture(fingers)
                count   = sum(fingers)

                xs = [lm.x * w for lm in hand_lm]
                ys = [lm.y * h for lm in hand_lm]
                x1 = max(0, int(min(xs)) - 20)
                y1 = max(0, int(min(ys)) - 20)
                x2 = min(w, int(max(xs)) + 20)
                y2 = min(h, int(max(ys)) + 20)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                panel_y = max(y1 - 10, 70)
                cv2.putText(frame,
                            f"{label}: {gesture}  [{count} fingers]",
                            (x1, panel_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

                dot_labels = ["T", "I", "M", "R", "P"]
                for fi, (up, lbl) in enumerate(zip(fingers, dot_labels)):
                    dot_x = x1 + fi * 28 + 10
                    dot_y = y2 + 22
                    dot_color = color if up else (60, 60, 60)
                    cv2.circle(frame, (dot_x, dot_y), 10, dot_color, -1)
                    cv2.putText(frame, lbl, (dot_x - 5, dot_y + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                                (255, 255, 255), 1)
        else:
            cv2.putText(frame, "No hands detected", (20, h - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2)

        cv2.imshow("Hand Tracker  |  Press Q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.close()

if __name__ == "__main__":
    run()