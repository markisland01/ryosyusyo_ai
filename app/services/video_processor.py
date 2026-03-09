import cv2
import numpy as np

from app.config import FRAME_SAMPLE_FPS, OUTPUT_DIR


def extract_frames(video_path: str) -> list[dict]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    frame_interval = max(1, int(fps / FRAME_SAMPLE_FPS))

    frames = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            frames.append(
                {
                    "frame_number": frame_idx,
                    "image": frame,
                    "timestamp": frame_idx / fps,
                }
            )
        frame_idx += 1

    cap.release()
    return frames


def calculate_blur_score(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def frame_difference(frame1: np.ndarray, frame2: np.ndarray) -> float:
    g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    g1 = cv2.resize(g1, (320, 240))
    g2 = cv2.resize(g2, (320, 240))
    diff = cv2.absdiff(g1, g2)
    return float(np.mean(diff)) / 255.0


def detect_scenes(frames: list[dict], threshold: float = 0.08) -> list[list[dict]]:
    if not frames:
        return []

    scenes: list[list[dict]] = [[frames[0]]]
    for i in range(1, len(frames)):
        diff = frame_difference(frames[i - 1]["image"], frames[i]["image"])
        if diff > threshold:
            scenes.append([frames[i]])
        else:
            scenes[-1].append(frames[i])
    return scenes


def pick_best_frame(scene: list[dict], min_blur: float = 30.0) -> dict | None:
    if not scene:
        return None

    best = None
    best_score = -1.0
    for frame_data in scene:
        score = calculate_blur_score(frame_data["image"])
        if score > best_score:
            best_score = score
            best = frame_data

    if best_score < min_blur:
        return None
    return best


def pick_segment_frames(scene: list[dict], max_segments: int = 3) -> list[dict]:
    if not scene:
        return []

    if len(scene) <= 2:
        best = pick_best_frame(scene, min_blur=30.0)
        return [best] if best is not None else []

    segment_count = min(max_segments, len(scene))
    step = max(1, len(scene) // segment_count)
    picked: list[dict] = []

    for segment_index in range(segment_count):
        start = segment_index * step
        end = len(scene) if segment_index == segment_count - 1 else min(len(scene), (segment_index + 1) * step)
        bucket = scene[start:end]
        best = pick_best_frame(bucket, min_blur=30.0)
        if best is not None:
            picked.append(best)

    deduped: list[dict] = []
    seen_frames: set[int] = set()
    for frame in picked:
        if frame["frame_number"] in seen_frames:
            continue
        seen_frames.add(frame["frame_number"])
        deduped.append(frame)
    return deduped


def merge_similar_candidates(
    candidates: list[dict],
    similarity_threshold: float = 0.06,
    min_frame_gap: int = 4,
    max_time_gap_seconds: float = 1.5,
) -> list[dict]:
    if not candidates:
        return []

    merged = [candidates[0]]
    for candidate in candidates[1:]:
        previous = merged[-1]
        frame_gap = candidate["frame_number"] - previous["frame_number"]
        time_gap = candidate["timestamp"] - previous["timestamp"]
        visual_diff = frame_difference(previous["representative_image"], candidate["representative_image"])

        if ((frame_gap <= min_frame_gap and visual_diff < similarity_threshold) or time_gap <= max_time_gap_seconds):
            if candidate["blur_score"] > previous["blur_score"]:
                merged[-1] = candidate
            continue
        merged.append(candidate)

    return merged


def save_receipt_image(image: np.ndarray, video_id: int, receipt_index: int) -> str:
    output_dir = OUTPUT_DIR / str(video_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"receipt_{receipt_index:03d}.png"
    filepath = output_dir / filename
    cv2.imwrite(str(filepath), image)
    return str(filepath)


def save_receipt_segment_image(image: np.ndarray, video_id: int, receipt_index: int, segment_index: int) -> str:
    output_dir = OUTPUT_DIR / str(video_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"receipt_{receipt_index:03d}_seg_{segment_index:02d}.png"
    filepath = output_dir / filename
    cv2.imwrite(str(filepath), image)
    return str(filepath)


def process_video(video_path: str, video_id: int) -> list[dict]:
    frames = extract_frames(video_path)
    if not frames:
        return []

    scenes = detect_scenes(frames, threshold=0.08)
    candidates = []

    for scene in scenes:
        best = pick_best_frame(scene, min_blur=30.0)
        if best is None:
            continue

        segment_frames = pick_segment_frames(scene, max_segments=3)
        if not segment_frames:
            segment_frames = [best]

        candidates.append(
            {
                "representative_image": best["image"],
                "segment_frames": segment_frames,
                "scene_start_frame": scene[0]["frame_number"],
                "scene_start_timestamp": scene[0]["timestamp"],
                "frame_number": best["frame_number"],
                "timestamp": best["timestamp"],
                "blur_score": calculate_blur_score(best["image"]),
            }
        )

    if not candidates and frames:
        fallback = max(frames, key=lambda frame: calculate_blur_score(frame["image"]))
        candidates.append(
            {
                "representative_image": fallback["image"],
                "segment_frames": [fallback],
                "scene_start_frame": fallback["frame_number"],
                "scene_start_timestamp": fallback["timestamp"],
                "frame_number": fallback["frame_number"],
                "timestamp": fallback["timestamp"],
                "blur_score": calculate_blur_score(fallback["image"]),
            }
        )

    candidates = merge_similar_candidates(candidates)

    results = []
    for receipt_idx, candidate in enumerate(candidates):
        segment_image_paths: list[str] = []
        segment_frame_numbers: list[int] = []

        for segment_index, segment in enumerate(candidate["segment_frames"]):
            if segment_index == 0:
                image_path = save_receipt_image(segment["image"], video_id, receipt_idx)
            else:
                image_path = save_receipt_segment_image(segment["image"], video_id, receipt_idx, segment_index)
            segment_image_paths.append(image_path)
            segment_frame_numbers.append(segment["frame_number"])

        results.append(
            {
                "image_path": segment_image_paths[0],
                "segment_image_paths": segment_image_paths,
                "segment_frame_numbers": segment_frame_numbers,
                "scene_start_frame": candidate["scene_start_frame"],
                "frame_number": candidate["frame_number"],
                "blur_score": candidate["blur_score"],
            }
        )

    return results
