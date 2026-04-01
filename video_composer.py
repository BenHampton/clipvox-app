import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg

from background_audio import BackgroundAudio
from clip_registry import add_pending_entry

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def _find_font(font_name):
    candidates = [
        font_name,
        f"C:/Windows/Fonts/{font_name}.ttf",
        f"C:/Windows/Fonts/{font_name.lower()}.ttf",
        f"C:/Windows/Fonts/{font_name}bd.ttf"
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _find_ffmpeg():
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    raise RuntimeError("FFmpeg not found. Install imageio-ffmpeg or add ffmpeg to PATH.")


def _escape_text(text):
    """Escape text for FFmpeg drawtext filter using backslash escaping (no surrounding quotes)."""
    text = text.replace("\\", "\\\\")
    text = text.replace("%", "%%")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace(",", "\\,")
    text = text.replace(";", "\\;")
    return text


def _font_opts(path):
    """
    Build FFmpeg drawtext fontfile option, stripping the Windows drive letter
    so the path contains no colon (e.g. "C:/Windows/..." -> "/Windows/...").
    On Windows, paths starting with "/" resolve to the current drive root.
    """
    fp = str(path).replace("\\", "/")
    if len(fp) >= 2 and fp[1] == ":":
        fp = fp[2:]
    return f"fontfile={fp}"


def compose_video(config, clip_path, tts_clips, video_duration):
    tts_config = config["tts"]
    output_config = config["output"]
    ba_config = config.get("backgroundAudio", {})

    font_name = tts_config.get("font", "Arial")
    font_size = int(tts_config.get("fontSize", 70))
    font_color = tts_config.get("fontColor", "white")
    preset = output_config.get("encodingPreset") or "medium"
    threads = int(output_config.get("threads", 0))

    include_audio = ba_config.get("includeAudio", False)
    bg_audio_path = None
    bg_audio_from_cache = None
    if include_audio:
        print("\n--- Background Audio ---")
        bg_audio_path, bg_audio_from_cache = BackgroundAudio(config).get_trimmed_audio(video_duration)

    font_path = _find_font(font_name)
    ffmpeg_exe = _find_ffmpeg()

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    output_name = output_config.get("name", "") or "result_"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = results_dir / f"{output_name}{timestamp}.mp4"

    # inputs: background video, TTS audio files, then background audio (if enabled)
    inputs = [clip_path] + [c["audio_path"] for c in tts_clips]
    if bg_audio_path:
        inputs.append(bg_audio_path)

    filter_parts = []

    # video: scale to cover TARGET_WIDTH x TARGET_HEIGHT, then center-crop
    video_chain = (
        f"[0:v]"
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}:(iw-{TARGET_WIDTH})/2:(ih-{TARGET_HEIGHT})/2"
    )

    # chain drawtext filter for each caption chunk
    if font_path:
        font_opt = _font_opts(font_path)
    else:
        font_opt = f"font={font_name}"

    for clip_info in tts_clips:
        offset = clip_info["offset"]
        for chunk in clip_info["tts_data"].get("chunks", []):
            abs_start = offset + chunk["start"]
            abs_end = min(offset + chunk["end"], video_duration)
            if abs_start >= video_duration:
                break
            video_chain += (
                f",drawtext={font_opt}"
                f":text={_escape_text(chunk['text'])}"
                f":fontcolor={font_color}"
                f":fontsize={font_size}"
                f":x=(w-text_w)/2:y=(h-text_h)/2"
                f":borderw=3:bordercolor=black@0.86"
                f":enable=between(t\\,{abs_start:.3f}\\,{abs_end:.3f})"
            )

    video_chain += "[vout]"
    filter_parts.append(video_chain)

    # audio: adelay each TTS clip to its offset, then mix
    audio_map_args = []
    tts_mix_label = "tts_amix" if (include_audio and bg_audio_path) else "amix"

    if tts_clips:
        if len(tts_clips) == 1:
            offset_ms = int(tts_clips[0]["offset"] * 1000)
            filter_parts.append(f"[1:a]adelay={offset_ms}|{offset_ms}[{tts_mix_label}]")
        else:
            labels = []
            for i, clip_info in enumerate(tts_clips):
                offset_ms = int(clip_info["offset"] * 1000)
                label = f"a{i}"
                filter_parts.append(f"[{i + 1}:a]adelay={offset_ms}|{offset_ms}[{label}]")
                labels.append(f"[{label}]")
            n = len(labels)
            filter_parts.append(
                f"{''.join(labels)}amix=inputs={n}:duration=longest:normalize=0[{tts_mix_label}]"
            )

    if include_audio and bg_audio_path:
        bg_input_idx = len(tts_clips) + 1
        tts_vol = float(ba_config.get("ttsAudioVolume", 1.0))
        bg_vol = float(ba_config.get("backgroundAudioVolume", 0.3))
        if tts_clips:
            filter_parts.append(f"[tts_amix]volume={tts_vol}[tts_vol]")
            filter_parts.append(f"[{bg_input_idx}:a]volume={bg_vol}[bg_vol]")
            filter_parts.append(
                f"[tts_vol][bg_vol]amix=inputs=2:duration=longest:normalize=0[amix]"
            )
        else:
            filter_parts.append(f"[{bg_input_idx}:a]volume={bg_vol}[amix]")

    if tts_clips or (include_audio and bg_audio_path):
        audio_map_args = ["-map", "[amix]", "-c:a", "aac"]

    filter_complex = ";".join(filter_parts)

    # build and run FFmpeg command
    # Global options (-y, -loglevel, -threads) must come before any -i inputs
    cmd = [ffmpeg_exe, "-y", "-loglevel", "error"]
    if threads > 0:
        cmd += ["-threads", str(threads)]
    for inp in inputs:
        cmd += ["-i", str(inp)]
    cmd += ["-map", "[vout]"]
    cmd += audio_map_args
    cmd += ["-c:v", "libx264", "-preset", preset]
    cmd += ["-stats", "-t", f"{video_duration:.3f}", str(output_path)]

    print(f"Writing final video: {output_path}")
    print(f"Filter complex:\n{filter_complex}\n")

    # Write filter_complex to a file to avoid Windows command-line length limits.
    # Use results/ (not the system temp dir) and forward slashes so FFmpeg can open it.
    fc_path = results_dir / "fc_tmp.txt"
    fc_path.write_text(filter_complex, encoding="utf-8")
    fc_path_str = str(fc_path.resolve()).replace("\\", "/")
    try:
        insert_at = cmd.index("-map")
        cmd_with_fc = cmd[:insert_at] + ["-filter_complex_script", fc_path_str] + cmd[insert_at:]
        result = subprocess.run(cmd_with_fc)
    finally:
        fc_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode}) — see output above.")

    add_pending_entry(clip_path, output_path.name)
    print(f"Done! Output: {output_path}")
    return str(output_path), bg_audio_from_cache
