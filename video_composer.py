import os
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
)

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def _find_font(font_name):
    candidates = [
        font_name,
        f"C:/Windows/Fonts/{font_name}.ttf",
        f"C:/Windows/Fonts/{font_name.lower()}.ttf",
        f"C:/Windows/Fonts/{font_name}bd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _resize_crop_vertical(clip, target_w=TARGET_WIDTH, target_h=TARGET_HEIGHT):
    clip_ratio = clip.w / clip.h
    target_ratio = target_w / target_h

    if clip_ratio > target_ratio:
        clip = clip.resize(height=target_h)
        x_center = clip.w // 2
        clip = clip.crop(x1=x_center - target_w // 2, x2=x_center + target_w // 2)
    else:
        clip = clip.resize(width=target_w)
        y_center = clip.h // 2
        clip = clip.crop(y1=y_center - target_h // 2, y2=y_center + target_h // 2)

    return clip


def _parse_color_rgba(color_str):
    try:
        rgb = ImageColor.getrgb(color_str)
        return (*rgb[:3], 255)
    except Exception:
        return (255, 255, 255, 255)


def _make_text_frame(text, video_w, video_h, font, font_color):
    img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_width = int(video_w * 0.75)

    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width or not current_line:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    line_spacing = 12
    line_bboxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [b[3] - b[1] for b in line_bboxes]
    total_height = sum(line_heights) + line_spacing * max(0, len(lines) - 1)

    text_color = _parse_color_rgba(font_color)
    outline_color = (0, 0, 0, 220)
    outline_offset = 3

    y = (video_h - total_height) // 2

    for i, line in enumerate(lines):
        text_w = line_bboxes[i][2] - line_bboxes[i][0]
        x = (video_w - text_w) // 2

        for dx in range(-outline_offset, outline_offset + 1):
            for dy in range(-outline_offset, outline_offset + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), line, font=font, fill=outline_color)

        draw.text((x, y), line, font=font, fill=text_color)
        y += line_heights[i] + line_spacing

    return np.array(img)


def _create_text_clip(text, video_w, video_h, font, font_color, start, duration):
    frame = _make_text_frame(text, video_w, video_h, font, font_color)
    rgb = frame[:, :, :3]
    alpha = frame[:, :, 3].astype(float) / 255.0

    clip = ImageClip(rgb, duration=duration).set_start(start)
    mask = ImageClip(alpha, ismask=True, duration=duration).set_start(start)
    return clip.set_mask(mask)


def compose_video(config, clip_path, tts_clips, video_duration):
    tts_config = config["tts"]
    output_config = config["output"]

    print(f"Loading background clip: {clip_path}")
    bg_clip = VideoFileClip(clip_path)
    bg_clip = _resize_crop_vertical(bg_clip)
    bg_clip = bg_clip.subclip(0, min(bg_clip.duration, video_duration))

    video_w, video_h = bg_clip.w, bg_clip.h

    font_name = tts_config.get("font", "Arial")
    font_size = int(tts_config.get("fontSize", 70))
    font_color = tts_config.get("fontColor", "white")
    font_path = _find_font(font_name)

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    audio_clips = []
    text_clips = []

    for clip_info in tts_clips:
        offset = clip_info["offset"]
        audio_path = clip_info["audio_path"]
        chunks = clip_info["tts_data"].get("chunks", [])

        print(f"Loading TTS audio: {audio_path} (offset: {offset:.2f}s)")
        audio = AudioFileClip(audio_path).set_start(offset)
        audio_clips.append(audio)

        for chunk in chunks:
            abs_start = offset + chunk["start"]
            abs_end = offset + chunk["end"]
            if abs_start >= video_duration:
                break
            duration = max(0.05, min(abs_end, video_duration) - abs_start)
            text_clips.append(
                _create_text_clip(chunk["text"], video_w, video_h, font, font_color, abs_start, duration)
            )

    if audio_clips:
        composite_audio = CompositeAudioClip(audio_clips).set_duration(video_duration)
    else:
        composite_audio = None

    final = CompositeVideoClip([bg_clip] + text_clips).set_duration(video_duration)
    if composite_audio:
        final = final.set_audio(composite_audio)

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    output_name = output_config.get("name", "") or "result_"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = results_dir / f"{output_name}{timestamp}.mp4"

    print(f"Writing final video: {output_path}")
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=30,
        logger="bar"
    )

    bg_clip.close()
    for a in audio_clips:
        a.close()

    print(f"Done! Output: {output_path}")
    return str(output_path)
