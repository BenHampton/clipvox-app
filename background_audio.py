"""Background audio trimmer and cache manager for ClipVox."""

import shutil
import subprocess
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
        Returns the path to a trimmed audio file suitable for video_duration.
        Cache key is (source filename + start_time) — duration is excluded so the
        same cached file is reused across videos of any length. The video composer's
        -t flag handles the actual cutoff.
        """
        audio_path = Path(self._config.get("audioPath", ""))
        if not audio_path.exists():
            raise FileNotFoundError(
                f"Background audio file not found: {audio_path}\n"
                f"Set backgroundAudio.audioPath in config.json."
            )

        start_time = float(self._config.get("audioStartTime", 0))

        trimmed_dir = audio_path.parent / "trimmed_audio"
        trimmed_dir.mkdir(parents=True, exist_ok=True)

        output_name = f"{audio_path.stem}_{start_time:.3f}.mp3"
        output_path = trimmed_dir / output_name

        if output_path.exists():
            print(f"Using cached trimmed audio: {output_path.name}")
            return str(output_path), True

        ffmpeg_exe = _find_ffmpeg()
        result = subprocess.run([
            ffmpeg_exe, "-y",
            "-i", str(audio_path),
            "-ss", str(start_time),
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
