import random
from datetime import datetime
from pathlib import Path

from PIL import Image
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import VideoFileClip


def _get_existing_clip(config):
    clips_dir = Path("background_videos/clips")
    if not clips_dir.exists():
        return None

    specified = config["backgroundVideo"].get("existingClipName", "")
    if specified:
        path = clips_dir / specified
        if path.exists():
            return str(path)
        print(f"Specified clip not found: {path}, falling back to most recent.")

    clips = sorted(clips_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if clips:
        return str(clips[0])

    return None


def generate_clip(config):
    bg_config = config["backgroundVideo"]
    clips_dir = Path("background_videos/clips")
    clips_dir.mkdir(parents=True, exist_ok=True)

    if bg_config.get("useExistingClip", True):
        existing = _get_existing_clip(config)
        if existing:
            print(f"Using existing clip: {existing}")
            return existing
        print("No existing clips found, generating new clip...")

    video_name = bg_config.get("videoName", "")
    if not video_name:
        raise ValueError("backgroundVideo.videoName must be set in config.json")

    video_path = Path("background_videos") / video_name
    if not video_path.exists():
        raise FileNotFoundError(f"Background video not found: {video_path}")

    print(f"Loading video: {video_path}")
    video = VideoFileClip(str(video_path))

    clip_length = 60
    if video.duration < clip_length:
        raise ValueError(
            f"Background video is too short ({video.duration:.1f}s). Must be at least 60 seconds."
        )

    max_start = video.duration - clip_length
    start_time = random.uniform(0, max_start)
    end_time = start_time + clip_length

    print(f"Extracting clip: {start_time:.1f}s to {end_time:.1f}s")
    clip = video.subclip(start_time, end_time).without_audio()

    clip_name = bg_config.get("clipName", "") or "saved_clip_"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = clips_dir / f"{clip_name}{timestamp}.mp4"

    print(f"Saving clip to: {output_path}")
    clip.write_videofile(
        str(output_path),
        codec="libx264",
        audio=False,
        logger="bar"
    )

    video.close()
    clip.close()

    return str(output_path)
