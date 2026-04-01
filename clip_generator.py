import random
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg

from clip_registry import get_used_clips, _parse_start_time


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


def _get_used_clips():
    """Return uploaded clip entries from the central registry."""
    return get_used_clips()


def _is_clip_used(clip_path, used_clips):
    """
    Returns True if the clip matches any used clip by exact filename OR by start time.
    """
    name = Path(clip_path).name
    start = _parse_start_time(name)
    for used in used_clips:
        if used["clip_name"] == name:
            return True
        if start is not None and used["start_time"] is not None and start == used["start_time"]:
            return True
    return False


def _get_existing_unused_clip(config, used_clips):
    """
    Returns the path to the most recent cached clip that has not been used in
    an uploaded video, or None if no unused clip exists.
    """
    video_name = config["backgroundVideo"].get("videoName", "")
    clips_dir = Path("background_videos") / Path(video_name).parent / "clips"
    if not clips_dir.exists():
        print(f"  Clips directory does not exist: {clips_dir}")
        return None

    specified = config["backgroundVideo"].get("existingClipName", "")
    if specified:
        path = clips_dir / specified
        if path.exists():
            if _is_clip_used(path, used_clips):
                print(f"  Specified clip '{specified}' has already been used in an upload — falling back to most recent unused.")
            else:
                print(f"  Specified clip found and unused: {path.name}")
                return str(path)
        else:
            print(f"  Specified clip not found: {path} — falling back to most recent.")

    clips = sorted(clips_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    print(f"  Found {len(clips)} cached clip(s) in {clips_dir}")

    for clip in clips:
        if _is_clip_used(clip, used_clips):
            reason = f"start time {_parse_start_time(clip.name)}s" if _parse_start_time(clip.name) is not None else "filename match"
            print(f"  Skipping (already used — {reason}): {clip.name}")
        else:
            print(f"  Selected unused clip: {clip.name}")
            return str(clip)

    return None


def generate_clip(config):
    bg_config = config["backgroundVideo"]
    video_name = bg_config.get("videoName", "")
    clips_dir = Path("background_videos") / Path(video_name).parent / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    used_clips = _get_used_clips()

    if bg_config.get("useExistingClip", True):
        existing = _get_existing_unused_clip(config, used_clips)
        if existing:
            print(f"Using existing clip: {existing}")
            return existing, True, False
        if used_clips:
            print("All cached clips have already been used — generating a new clip.")
        else:
            print("No cached clips found — generating new clip.")

    if not video_name:
        raise ValueError("backgroundVideo.videoName must be set in config.json")

    video_path = Path("background_videos") / video_name
    if not video_path.exists():
        raise FileNotFoundError(f"Background video not found: {video_path}")

    ffmpeg_exe = _find_ffmpeg()

    clip_length = int(bg_config.get("backgroundVideoLength", 60))
    duration = _get_video_duration(ffmpeg_exe, video_path)
    print(f"Source video: {video_path}  |  Duration: {duration:.1f}s  |  Clip length: {clip_length}s")
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

        print(f"Extracting clip: {start_time:.1f}s → {start_time + clip_length:.1f}s  from {video_path.name}")
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
        print(f"Clip saved: {output_path.name}")
        return str(output_path), False, had_collision

    return None, False, had_collision
