import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO

# VIOFO_URL = "rtsp://192.168.1.254"
VIOFO_URL = "0"
DEFAULT_CHECKPOINT = Path(__file__).resolve().with_name("best.pt")
WINDOW_NAME = "Pothole Detection"

EMA_ALPHA = 0.5
HOLD_FRAMES = 2
MIN_IOU = 0.2

def box_iou(a, b):
    overlap_width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    overlap_height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = overlap_width * overlap_height

    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def update_tracks(tracks, boxes, show_threshold, keep_threshold):
    unmatched = set(range(len(tracks)))
    next_tracks = []

    # Match stronger detections first. Each track can match only once per frame.
    for detection in sorted(boxes, key=lambda row: row[4], reverse=True):
        x1, y1, x2, y2, score, class_id = detection
        box = (x1, y1, x2, y2)
        class_id = int(class_id)

        candidates = ((box_iou(box, tracks[index]["box"]), index) for index in unmatched if tracks[index]["class_id"] == class_id)
        overlap, index = max(candidates, default=(0.0, -1))

        if overlap >= MIN_IOU:
            unmatched.remove(index)
            previous = tracks[index]
            score = EMA_ALPHA * score + (1 - EMA_ALPHA) * previous["score"]
            visible = score >= (keep_threshold if previous["visible"] else show_threshold)
        else:
            visible = score >= show_threshold

        next_tracks.append({"box": box, "class_id": class_id, "score": score, "visible": visible, "missed": 0})

    for index in sorted(unmatched):
        track = tracks[index]
        if track["visible"] and track["missed"] < HOLD_FRAMES:
            next_tracks.append({**track, "missed": track["missed"] + 1})

    return next_tracks

def draw_tracks(frame, tracks, names):
    for track in tracks:
        x1, y1, x2, y2 = map(int, track["box"])
        label = f"{names[track['class_id']]}: {track['score']:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, max(y1 - 10, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

def main():
    parser = argparse.ArgumentParser(description="Run a YOLO pothole detector on video.")
    parser.add_argument("source", nargs="?", default=VIOFO_URL, help="Webcam index, video filename, RTSP URL, or 'viofo'")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--threshold", type=float, default=0.50)
    parser.add_argument("--headless", action="store_true", help="Run without a preview")
    args = parser.parse_args()

    if not args.checkpoint.is_file():
        parser.error(f"Checkpoint not found: {args.checkpoint}")
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")

    source = VIOFO_URL if args.source == "viofo" else args.source
    if source.isdecimal():
        source = int(source)

    checkpoint = args.checkpoint.resolve()
    print(f"Loading {checkpoint} on CPU. Source: {source}", flush=True)
    model = YOLO(str(checkpoint))
    print(f"Model classes: {model.names}", flush=True)

    keep_threshold = args.threshold * 0.7
    results = model.predict(source=source, device="cpu", conf=keep_threshold, stream=True, stream_buffer=False, verbose=False)
    tracks = []

    frames = 0
    preview_open = False
    try:
        for result in results:
            frames += 1
            boxes = (result.boxes.data.cpu().tolist() if result.boxes is not None else [])
            tracks = update_tracks(tracks, boxes, args.threshold, keep_threshold)
            visible_tracks = [track for track in tracks if track["visible"]]

            if frames == 1 or frames % 30 == 0:
                print(f"Frame {frames}: {len(visible_tracks)} detections", flush=True)

            if not args.headless:
                frame = result.orig_img.copy()
                draw_tracks(frame, visible_tracks, result.names)
                cv2.imshow(WINDOW_NAME, frame)
                preview_open = True
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        return
    finally:
        results.close()
        if preview_open:
            cv2.destroyAllWindows()

    if frames == 0:
        raise SystemExit(f"No frames received from {source}.")

if __name__ == "__main__":
    main()