import re
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg


def _find_ffmpeg():
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    raise RuntimeError("FFmpeg not found. Install imageio-ffmpeg or add ffmpeg to PATH.")


def _get_video_duration(ffmpeg_exe, video_path):
    result = subprocess.run(
        [ffmpeg_exe, "-i", str(video_path)],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if not match:
        raise RuntimeError(f"Could not determine duration of {video_path}")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def _get_existing_clip(config):
    video_name = config["backgroundVideo"].get("videoName", "")
    clips_dir = Path("background_videos") / Path(video_name).parent / "clips"
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
    video_name = bg_config.get("videoName", "")
    clips_dir = Path("background_videos") / Path(video_name).parent / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    if bg_config.get("useExistingClip", True):
        existing = _get_existing_clip(config)
        if existing:
            print(f"Using existing clip: {existing}")
            return existing, True, False
        print("No existing clips found, generating new clip...")

    if not video_name:
        raise ValueError("backgroundVideo.videoName must be set in config.json")

    video_path = Path("background_videos") / video_name
    if not video_path.exists():
        raise FileNotFoundError(f"Background video not found: {video_path}")

    ffmpeg_exe = _find_ffmpeg()

    clip_length = int(bg_config.get("backgroundVideoLength", 60))
    duration = _get_video_duration(ffmpeg_exe, video_path)
    if duration < clip_length:
        raise ValueError(
            f"Background video is too short ({duration:.1f}s). Must be at least {clip_length} seconds."
        )

    max_start = duration - clip_length
    clip_name = bg_config.get("clipName", "") or "saved_clip_"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    max_attempts = 3
    had_collision = False
    for attempt in range(1, max_attempts + 1):
        start_time = random.uniform(0, max_start)
        output_path = clips_dir / f"{clip_name}{timestamp}_start_time_{int(start_time)}.mp4"

        if output_path.exists():
            had_collision = True
            if attempt < max_attempts:
                print(f"Clip name collision, retrying ({attempt}/{max_attempts - 1})...")
                continue
            print(f"Warning: could not find a unique clip name after {max_attempts} attempts. Overwriting {output_path}.")

        print(f"Extracting clip: {start_time:.1f}s to {start_time + clip_length:.1f}s")
        print(f"Saving clip to: {output_path}")
        subprocess.run(
            [
                ffmpeg_exe,
                "-ss", str(start_time),
                "-i", str(video_path),
                "-t", str(clip_length),
                "-c:v", "copy",
                "-an",
                str(output_path),
            ],
            check=True,
        )
        return str(output_path), False, had_collision

    return None, False, had_collision
