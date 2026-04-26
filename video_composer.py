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


def _pick_encoder(ffmpeg_exe):
    try:
        result = subprocess.run(
            [ffmpeg_exe, "-hide_banner", "-encoders"],
            capture_output=True, text=True
        )
        if "h264_nvenc" in result.stdout:
            return "h264_nvenc"
    except Exception:
        pass
    return "libx264"


_COLOR_MAP = {
    "white":   "FFFFFF",
    "yellow":  "00FFFF",
    "red":     "0000FF",
    "blue":    "FF0000",
    "green":   "00FF00",
    "black":   "000000",
    "cyan":    "FFFF00",
    "magenta": "FF00FF",
    "orange":  "0080FF",
}


def _color_to_ass(color):
    name = color.lower().strip()
    if name in _COLOR_MAP:
        return f"&H00{_COLOR_MAP[name]}"
    if name.startswith("#") and len(name) == 7:
        r, g, b = name[1:3], name[3:5], name[5:7]
        return f"&H00{b}{g}{r}".upper()
    return "&H00FFFFFF"


def _ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    if cs == 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _write_ass(tts_clips, video_duration, font_name, font_size, font_color, output_dir):
    primary = _color_to_ass(font_color)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {TARGET_WIDTH}",
        f"PlayResY: {TARGET_HEIGHT}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{primary},&H000000FF,&H24000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,5,10,10,10,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for clip_info in tts_clips:
        offset = clip_info["offset"]
        for chunk in clip_info["tts_data"].get("chunks", []):
            abs_start = offset + chunk["start"]
            abs_end = min(offset + chunk["end"], video_duration)
            if abs_start >= video_duration:
                break
            text = chunk["text"].replace("\\", "\\\\").replace("{", "\\{")
            lines.append(
                f"Dialogue: 0,{_ass_time(abs_start)},{_ass_time(abs_end)},Default,,0,0,0,,{text}"
            )
    ass_path = output_dir / "captions_tmp.ass"
    ass_path.write_text("\n".join(lines), encoding="utf-8")
    return ass_path


def compose_video(config, clip_path, tts_clips, video_duration):
    tts_config = config["tts"]
    output_config = config["output"]
    ba_config = config.get("backgroundAudio", {})
    speed = float(config.get("backgroundVideo", {}).get("speed", 1.0))

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
    encoder = _pick_encoder(ffmpeg_exe)
    use_gpu = encoder == "h264_nvenc"

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

    # video: optionally speed up, scale to cover TARGET_WIDTH x TARGET_HEIGHT, then center-crop
    speed_filter = f"setpts={1.0 / speed:.6f}*PTS," if speed != 1.0 else ""
    if use_gpu:
        video_chain = (
            f"[0:v]"
            f"{speed_filter}"
            f"hwupload,"
            f"scale_cuda={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
            f"hwdownload,format=nv12,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}:(iw-{TARGET_WIDTH})/2:(ih-{TARGET_HEIGHT})/2"
        )
    else:
        video_chain = (
            f"[0:v]"
            f"{speed_filter}"
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}:(iw-{TARGET_WIDTH})/2:(ih-{TARGET_HEIGHT})/2"
        )

    ass_path = None
    if tts_clips:
        ass_path = _write_ass(tts_clips, video_duration, font_name, font_size, font_color, results_dir)
        ass_path_str = str(ass_path.resolve()).replace("\\", "/")
        if len(ass_path_str) >= 2 and ass_path_str[1] == ":":
            ass_path_str = ass_path_str[2:]
        video_chain += f",subtitles={ass_path_str}"

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
    if use_gpu:
        cmd += ["-hwaccel", "cuda"]
    cmd += ["-i", str(inputs[0])]
    for inp in inputs[1:]:
        cmd += ["-i", str(inp)]
    cmd += ["-map", "[vout]"]
    cmd += audio_map_args
    cmd += ["-c:v", encoder, "-preset", preset]
    if use_gpu:
        cmd += ["-rc:v", "vbr", "-cq:v", "23", "-b:v", "0"]
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
        if ass_path:
            ass_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode}) — see output above.")

    add_pending_entry(clip_path, output_path.name)
    print(f"Done! Output: {output_path}")
    return str(output_path), bg_audio_from_cache, encoder
