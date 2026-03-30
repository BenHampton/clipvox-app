"""Background audio trimmer and cache manager for ClipVox."""

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


class BackgroundAudio:
    """Trims a source MP3 to match the final video duration, with caching."""

    def __init__(self, config):
        self._config = config.get("backgroundAudio", {})

    def get_trimmed_audio(self, video_duration):
        """
        Returns the path to a trimmed audio file matching video_duration.
        Checks background_sounds/trimmed_audio/ for a cache hit (source filename +
        duration) before creating a new trim.
        """
        audio_path = Path(self._config.get("audioPath", ""))
        if not audio_path.exists():
            raise FileNotFoundError(
                f"Background audio file not found: {audio_path}\n"
                f"Set backgroundAudio.audioPath in config.json."
            )

        start_time = float(self._config.get("audioStartTime", 0))
        duration = round(video_duration, 3)
        stop_time = round(start_time + duration, 3)

        trimmed_dir = audio_path.parent / "trimmed_audio"
        trimmed_dir.mkdir(parents=True, exist_ok=True)

        cached = self._find_cached(trimmed_dir, audio_path.stem, duration)
        if cached:
            print(f"Using cached trimmed audio: {cached.name}")
            return str(cached), True

        # No cache hit — trim source audio and save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = (
            f"{audio_path.stem}_{duration:.3f}_{start_time:.3f}"
            f"_{stop_time:.3f}_{timestamp}.mp3"
        )
        output_path = trimmed_dir / output_name

        ffmpeg_exe = _find_ffmpeg()
        result = subprocess.run([
            ffmpeg_exe, "-y",
            "-i", str(audio_path),
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:a", "copy",
            "-loglevel", "error",
            str(output_path),
        ])
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed to trim background audio (exit {result.returncode})."
            )

        print(f"Trimmed audio saved: {output_path.name}")
        return str(output_path), False

    def _find_cached(self, trimmed_dir, source_stem, duration):
        """
        Returns a cached trimmed audio Path whose source filename and duration
        match, or None if no suitable file exists.
        """
        for cached in trimmed_dir.glob(f"{source_stem}_*.mp3"):
            suffix = cached.stem[len(source_stem) + 1:]
            parts = suffix.split("_")
            if not parts:
                continue
            try:
                if abs(float(parts[0]) - duration) < 0.01:
                    return cached
            except ValueError:
                continue
        return None
